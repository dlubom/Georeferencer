#!/usr/bin/env python3
"""05_add_cave.py — Ręczne dodanie brakującej jaskini.

Tworzy katalog z meta.yaml i kopiuje obrazy ze scrapera.
Dane georeferencji (otwór, skala, kąt północy) podaje się z konsoli
Georeferencer UI (blok "DANE DO META.YAML").

Użycie:
    python pipeline/05_add_cave.py --cave 000490 \\
        --entrance-x 1234.56 --entrance-y 789.01 \\
        --pixels-per-meter 12.35 \\
        --north-angle 5.67

    # Podgląd bez zapisu:
    python pipeline/05_add_cave.py --cave 000490 --dry-run

    # Automatyczne wyszukanie obrazu planu:
    python pipeline/05_add_cave.py --cave 000490 \\
        --entrance-x 100 --entrance-y 200 \\
        --pixels-per-meter 50 --north-angle 0
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

SCRAPER_DIR = Path.home() / "projects" / "Polish-Cave-Data-Scraper"
JSONL_PATH = Path.home() / "projects" / "Jaskiniowy-Kataster-Tatr-Zachodnich" / "doc" / "jaskinie_polski_pig_dump.jsonl"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "caves"


def load_cave_from_jsonl(cave_id: str) -> dict | None:
    """Znajdź jaskinię w JSONL po cave_id."""
    with open(JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("cave_id") == cave_id:
                return rec
    return None


def find_plan_image(cave_id: str, cave_data: dict) -> tuple[str, dict] | None:
    """Znajdź obraz planu (nie przekrój) w scraperze.

    Zwraca (filename, metadata) lub None.
    """
    images = cave_data.get("images") or []
    plans = [
        img for img in images
        if img.get("metadata", {}).get("graphics_type_name") == "plan"
    ]
    if not plans:
        return None

    # Weź pierwszy plan
    plan = plans[0]
    meta = plan["metadata"]
    graphics_id = meta["graphics_id"]
    filename = f"image_{graphics_id}_zoom_10"

    # Sprawdź czy plik istnieje w scraperze
    mono_path = SCRAPER_DIR / "caves_mono" / cave_id / f"{filename}.tif"
    if not mono_path.exists():
        # Fallback: szukaj dowolnego .tif w caves_mono
        mono_dir = SCRAPER_DIR / "caves_mono" / cave_id
        if mono_dir.exists():
            tifs = list(mono_dir.glob("*.tif"))
            if tifs:
                filename = tifs[0].stem
                return filename, meta
        return None

    return filename, meta


def get_image_dimensions(cave_id: str, filename: str) -> tuple[int, int]:
    """Odczytaj wymiary obrazu mono (to na nim wykonano kliki)."""
    tif_path = SCRAPER_DIR / "caves_mono" / cave_id / f"{filename}.tif"
    with Image.open(tif_path) as img:
        return img.width, img.height


def copy_images(cave_id: str, filename: str, cave_dir: Path):
    """Kopiuj obrazy ze scrapera do katalogu jaskini."""
    copies = [
        (SCRAPER_DIR / "caves_mono" / cave_id / f"{filename}.tif", cave_dir / "image.tif"),
        (SCRAPER_DIR / "caves_upscaled" / cave_id / f"{filename}.jpg", cave_dir / "image_upscaled.jpg"),
        (SCRAPER_DIR / "caves" / cave_id / f"{filename}.jpg", cave_dir / "image_original.jpg"),
    ]
    for src, dst in copies:
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Skopiowano: {dst.name}")
        else:
            print(f"  Pominięto (brak): {src}")


def build_meta_yaml(cave_data: dict, image_meta: dict, filename: str,
                    width: int, height: int,
                    entrance_x: float, entrance_y: float,
                    pixels_per_meter: float, north_angle: float,
                    declination: float) -> dict:
    """Zbuduj strukturę meta.yaml."""
    graphics_id = image_meta["graphics_id"]

    return {
        "cave": {
            "inventory_number": cave_data.get("inventory_number", ""),
            "dir_id": cave_data["cave_id"],
            "name": cave_data.get("name", ""),
            "n_submissions": 0,
        },
        "image": {
            "filename": f"{filename}.tif",
            "image_id": graphics_id,
            "width": width,
            "height": height,
        },
        "coordinates": {
            "lat": float(cave_data.get("latitude", 0)),
            "lon": float(cave_data.get("longitude", 0)),
        },
        "entrance": {
            "x": entrance_x,
            "y": entrance_y,
        },
        "scale": {
            "pixels_per_meter": pixels_per_meter,
        },
        "north": {
            "angle_deg": north_angle,
            "all_skipped": north_angle == 0.0,
        },
        "declination_deg": declination,
        "computed": {},
        "quality": {
            "ppm_cv": 0.0,
            "ppm_values": [pixels_per_meter],
            "entrance_std_px": 0.0,
            "outliers_removed": 0,
            "flag": "manual",
        },
    }


def represent_float(dumper, value):
    """YAML float — unikaj notacji naukowej."""
    if value != value:
        return dumper.represent_scalar("tag:yaml.org,2002:null", "null")
    text = f"{value:.10f}" if abs(value) < 1 and value != 0 else str(value)
    return dumper.represent_scalar("tag:yaml.org,2002:float", text)


def parse_args():
    p = argparse.ArgumentParser(description="Dodaj brakującą jaskinię ręcznie")
    p.add_argument("--cave", required=True, help="Cave ID (dir_id), np. 000490")
    p.add_argument("--entrance-x", type=float, help="X otworu w pikselach (orig)")
    p.add_argument("--entrance-y", type=float, help="Y otworu w pikselach (orig)")
    p.add_argument("--pixels-per-meter", type=float, help="Piksele na metr")
    p.add_argument("--north-angle", type=float, default=0.0, help="Kąt północy [°]")
    p.add_argument("--declination", type=float, default=0.0, help="Deklinacja [°]")
    p.add_argument("--dry-run", action="store_true", help="Tylko podgląd, bez zapisu")
    p.add_argument("--image-id", type=int, help="Graphics ID (jeśli wiele planów)")
    return p.parse_args()


def main():
    args = parse_args()
    cave_id = args.cave

    # 1. Znajdź jaskinię w JSONL
    cave_data = load_cave_from_jsonl(cave_id)
    if not cave_data:
        print(f"Błąd: Jaskinia {cave_id} nie znaleziona w JSONL")
        sys.exit(1)

    print(f"Jaskinia: {cave_data.get('name')} ({cave_data.get('inventory_number')})")
    print(f"  Współrzędne: {cave_data.get('latitude')}, {cave_data.get('longitude')}")
    print(f"  Długość: {cave_data.get('length_m')} m, głębokość: {cave_data.get('depth_m')} m")

    # 2. Znajdź obraz planu
    result = find_plan_image(cave_id, cave_data)
    if not result:
        print("Błąd: Brak obrazu planu w scraperze")
        sys.exit(1)

    filename, image_meta = result
    print(f"  Plan: {filename} (graphics_id: {image_meta['graphics_id']})")

    # 3. Wymiary obrazu mono
    width, height = get_image_dimensions(cave_id, filename)
    print(f"  Wymiary mono: {width}×{height} px")

    # 4. Sprawdź czy parametry georeferencji podane
    if args.entrance_x is None or args.entrance_y is None or args.pixels_per_meter is None:
        print(f"\n  Otwórz plan w Georeferencer UI, zaznacz punkty, skopiuj dane z konsoli.")
        print(f"  Potem uruchom ponownie z parametrami --entrance-x/y --pixels-per-meter --north-angle")
        print(f"\n  Obraz mono: {SCRAPER_DIR / 'caves_mono' / cave_id / (filename + '.tif')}")
        if args.dry_run:
            return
        sys.exit(0)

    # 5. Zbuduj meta.yaml
    meta = build_meta_yaml(
        cave_data, image_meta, filename, width, height,
        args.entrance_x, args.entrance_y,
        args.pixels_per_meter, args.north_angle,
        args.declination,
    )

    print(f"\n  entrance: ({args.entrance_x}, {args.entrance_y})")
    print(f"  pixels_per_meter: {args.pixels_per_meter}")
    print(f"  north_angle: {args.north_angle}°")
    print(f"  declination: {args.declination}°")

    if args.dry_run:
        print("\n--- meta.yaml (dry-run) ---")
        yaml.add_representer(float, represent_float)
        yaml.dump(meta, sys.stdout, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return

    # 6. Utwórz katalog i zapisz
    cave_dir = DATA_DIR / cave_id
    cave_dir.mkdir(parents=True, exist_ok=True)

    # Kopiuj obrazy
    copy_images(cave_id, filename, cave_dir)

    # Zapisz meta.yaml
    yaml_path = cave_dir / "meta.yaml"
    yaml.add_representer(float, represent_float)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"  Zapisano: {yaml_path}")

    # 7. Wygeneruj .tfw i GeoTIFF
    print(f"\n  Teraz uruchom:")
    print(f"    python pipeline/02_generate_geotiff.py --cave {cave_id}")


if __name__ == "__main__":
    main()
