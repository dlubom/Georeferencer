#!/usr/bin/env python3
"""02_generate_geotiff.py — YAML → .tfw + GeoTIFF.

Powtarzalny skrypt: czyta meta.yaml, przelicza parametry A-F,
generuje World File (.tfw) i GeoTIFF przez gdal_translate.

Użycie:
    python pipeline/02_generate_geotiff.py --cave 001131
    python pipeline/02_generate_geotiff.py --all
    python pipeline/02_generate_geotiff.py --changed
    python pipeline/02_generate_geotiff.py --all --force
"""
import argparse
import math
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
from pyproj import Transformer

DATA_DIR = Path("data/caves")
TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


def parse_args():
    p = argparse.ArgumentParser(description="Generacja GeoTIFF z meta.yaml")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--cave", help="Dir ID jaskini (np. 001131)")
    group.add_argument("--all", action="store_true", help="Przetwórz wszystkie")
    group.add_argument("--changed", action="store_true",
                       help="Przetwórz tylko zmienione (meta.yaml nowszy niż .tfw)")
    p.add_argument("--force", action="store_true", help="Wymuszaj regenerację")
    p.add_argument("--data-dir", default="data/caves", help="Katalog danych")
    return p.parse_args()


def compute_world_file(meta):
    """Oblicz parametry World File z danych YAML (replikacja index.html:2277-2370)."""
    lat = meta["coordinates"]["lat"]
    lon = meta["coordinates"]["lon"]
    ppm = meta["scale"]["pixels_per_meter"]
    north_angle = meta["north"]["angle_deg"]
    declination = meta.get("declination_deg", 0.0)
    entrance_x = meta["entrance"]["x"]
    entrance_y = meta["entrance"]["y"]

    # Projekcja WGS84 → PL-1992
    world_x, world_y = TRANSFORMER.transform(lon, lat)

    # Skala
    mpp = 1.0 / ppm

    # Zbieżność południków
    lambda0 = 19.0
    convergence_deg = (lambda0 - lon) * math.sin(math.radians(lat))

    # Całkowita rotacja
    total_deg = north_angle + declination + convergence_deg
    rot = math.radians(total_deg)

    # Parametry World File
    cos_r = math.cos(rot)
    sin_r = math.sin(rot)
    A = mpp * cos_r
    D = mpp * sin_r
    B = mpp * sin_r
    E = -mpp * cos_r
    C = world_x - (A * entrance_x + B * entrance_y)
    F = world_y - (D * entrance_x + E * entrance_y)

    return {
        "A": A, "D": D, "B": B, "E": E, "C": C, "F": F,
        "convergence_deg": convergence_deg,
        "total_rotation_deg": total_deg,
    }


def verify_image_dimensions(meta, cave_dir):
    """Sprawdź czy wymiary obrazu zgadzają się z YAML. Zwraca (ok, message)."""
    tif_path = cave_dir / "image.tif"
    if not tif_path.exists():
        return False, f"Brak pliku {tif_path}"

    yaml_w = meta["image"].get("width")
    yaml_h = meta["image"].get("height")
    if not yaml_w or not yaml_h:
        return True, "Brak wymiarów w YAML — pomijam weryfikację"

    with Image.open(tif_path) as img:
        actual_w, actual_h = img.width, img.height

    if actual_w != yaml_w or actual_h != yaml_h:
        return False, (
            f"Obraz ma inną rozdzielczość ({actual_w}×{actual_h}) niż ta, "
            f"na której wykonano kliki ({yaml_w}×{yaml_h}). "
            f"Wymień obraz na oryginalny lub wykonaj nowe kliknięcia."
        )
    return True, "OK"


def write_tfw(cave_dir, params):
    """Zapisz World File (.tfw)."""
    tfw_path = cave_dir / "image.tfw"
    lines = [
        f"{params['A']:.10f}",
        f"{params['D']:.10f}",
        f"{params['B']:.10f}",
        f"{params['E']:.10f}",
        f"{params['C']:.6f}",
        f"{params['F']:.6f}",
    ]
    tfw_path.write_text("\n".join(lines) + "\n")
    return tfw_path


def update_computed_section(meta, params):
    """Zaktualizuj sekcję computed w meta dict."""
    meta["computed"] = {
        "convergence_deg": round(params["convergence_deg"], 4),
        "total_rotation_deg": round(params["total_rotation_deg"], 4),
        "A": round(params["A"], 10),
        "D": round(params["D"], 10),
        "B": round(params["B"], 10),
        "E": round(params["E"], 10),
        "C": round(params["C"], 6),
        "F": round(params["F"], 6),
    }


def generate_geotiff(cave_dir):
    """Generuj GeoTIFF przez gdal_translate."""
    tif_path = cave_dir / "image.tif"
    tfw_path = cave_dir / "image.tfw"
    georef_path = cave_dir / "image_georef.tif"

    if not tif_path.exists() or not tfw_path.exists():
        return False, "Brak image.tif lub image.tfw"

    cmd = [
        "gdal_translate", "-of", "GTiff",
        "-a_srs", "EPSG:2180",
        "-co", "COMPRESS=CCITTFAX4",
        str(tif_path), str(georef_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"gdal_translate error: {result.stderr.strip()}"
    return True, str(georef_path)


def represent_float(dumper, value):
    """YAML float — unikaj notacji naukowej."""
    if value != value:
        return dumper.represent_scalar("tag:yaml.org,2002:null", "null")
    text = f"{value:.10f}" if abs(value) < 1 and value != 0 else str(value)
    return dumper.represent_scalar("tag:yaml.org,2002:float", text)


def process_cave(cave_dir):
    """Przetwórz jedną jaskinię. Zwraca (success, message)."""
    yaml_path = cave_dir / "meta.yaml"
    if not yaml_path.exists():
        return False, "Brak meta.yaml"

    with open(yaml_path, encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    # Weryfikacja wymiarów
    ok, msg = verify_image_dimensions(meta, cave_dir)
    if not ok:
        return False, msg

    # Oblicz World File
    params = compute_world_file(meta)

    # Zapisz .tfw
    write_tfw(cave_dir, params)

    # Zaktualizuj computed w YAML
    update_computed_section(meta, params)
    yaml.add_representer(float, represent_float)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False, width=120)

    # Generuj GeoTIFF
    ok, msg = generate_geotiff(cave_dir)
    return ok, msg


def find_caves(data_dir, changed_only=False):
    """Znajdź katalogi jaskiń do przetworzenia."""
    caves = []
    for yaml_path in sorted(data_dir.glob("*/meta.yaml")):
        cave_dir = yaml_path.parent
        if cave_dir.name.startswith("_"):
            continue

        if changed_only:
            tfw_path = cave_dir / "image.tfw"
            if tfw_path.exists() and tfw_path.stat().st_mtime >= yaml_path.stat().st_mtime:
                continue

        caves.append(cave_dir)
    return caves


def main():
    args = parse_args()
    data_dir = Path(args.data_dir)

    if args.cave:
        caves = [data_dir / args.cave]
    elif args.all:
        caves = find_caves(data_dir)
    else:  # --changed
        caves = find_caves(data_dir, changed_only=True)

    if not caves:
        print("Brak jaskiń do przetworzenia.")
        return

    print(f"Przetwarzanie {len(caves)} jaskiń...")

    success = 0
    errors = 0
    for cave_dir in caves:
        dir_id = cave_dir.name
        ok, msg = process_cave(cave_dir)
        if ok:
            success += 1
        else:
            print(f"  BŁĄD {dir_id}: {msg}")
            errors += 1

    print(f"\nGotowe: {success} OK, {errors} błędów")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
