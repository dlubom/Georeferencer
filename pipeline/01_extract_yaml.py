#!/usr/bin/env python3
"""01_extract_yaml.py — Parquet → YAML + kopiowanie obrazów źródłowych.

Jednorazowy skrypt ekstrakcji danych crowdsourcingowych do edytowalnych YAML-i.
Kopiuje obrazy z Polish-Cave-Data-Scraper do data/caves/{dir_id}/.

Użycie:
    python pipeline/01_extract_yaml.py
    python pipeline/01_extract_yaml.py --scraper-dir ../Polish-Cave-Data-Scraper
    python pipeline/01_extract_yaml.py --min-submissions 5
    python pipeline/01_extract_yaml.py --no-copy-images
"""
import argparse
import json
import math
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # Wyłącz limit — nasze TIFFy są bezpieczne
from pyproj import Transformer


def parse_args():
    p = argparse.ArgumentParser(description="Ekstrakcja YAML z danych crowdsourcingowych")
    p.add_argument("--parquet-dir", default="parquet", help="Katalog z plikami parquet")
    p.add_argument("--scraper-dir", default="../Polish-Cave-Data-Scraper",
                    help="Katalog Polish-Cave-Data-Scraper")
    p.add_argument("--output-dir", default="data/caves", help="Katalog wyjściowy")
    p.add_argument("--min-submissions", type=int, default=5,
                    help="Minimalna liczba zgłoszeń (domyślnie 5)")
    p.add_argument("--no-copy-images", action="store_true",
                    help="Pomiń kopiowanie obrazów")
    p.add_argument("--force", action="store_true",
                    help="Nadpisz istniejące YAML-e")
    return p.parse_args()


def remove_iqr_outliers(values):
    """Usuń outlierów metodą IQR i zwróć przefiltrowane wartości."""
    if len(values) < 4:
        return values
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    filtered = [v for v in values if lower <= v <= upper]
    return filtered if filtered else values


def extract_dir_id(image_used_path):
    """Wyciągnij dir_id z image_used_path, np. 'caves_mono/001131/image_631...' → '001131'."""
    m = re.search(r'/(\d{6})/', image_used_path)
    return m.group(1) if m else None


def extract_image_filename(image_used_path):
    """Wyciągnij nazwę pliku z image_used_path."""
    return Path(image_used_path).name


def aggregate_cave(cave_id, subs, caves_df):
    """Agreguj zgłoszenia dla jednej jaskini → dict z danymi do YAML."""
    first = subs.iloc[0]
    dir_id = extract_dir_id(first["image_used_path"])
    if not dir_id:
        print(f"  UWAGA: Nie można wyciągnąć dir_id dla {cave_id}, pomijam")
        return None

    image_filename = extract_image_filename(first["image_used_path"])
    image_id = int(first["image_id"])

    # --- Entrance (mediana x, y) ---
    entrance_xs = []
    entrance_ys = []
    for _, row in subs.iterrows():
        points = json.loads(row["points_orig_json"])
        if points:
            entrance_xs.append(points[0]["x"])
            entrance_ys.append(points[0]["y"])

    entrance_x = float(np.median(entrance_xs))
    entrance_y = float(np.median(entrance_ys))
    entrance_std = float(np.sqrt(
        np.std(entrance_xs) ** 2 + np.std(entrance_ys) ** 2
    ))

    # --- Scale (pixels_per_meter) — mediana z IQR outlier removal ---
    ppm_values = subs["pixels_per_meter"].dropna().tolist()
    ppm_filtered = remove_iqr_outliers(ppm_values)
    outliers_removed = len(ppm_values) - len(ppm_filtered)
    ppm_median = float(np.median(ppm_filtered))
    ppm_cv = float(np.std(ppm_filtered) / np.mean(ppm_filtered)) if np.mean(ppm_filtered) > 0 else 0.0

    # --- North angle (mediana z non-skip) ---
    north_subs = subs[subs["skipNorth"] == False]  # noqa: E712
    if len(north_subs) > 0:
        north_values = north_subs["north_deg"].dropna().tolist()
        north_angle = float(np.median(north_values)) if north_values else 0.0
        all_skipped = False
    else:
        north_angle = 0.0
        all_skipped = True

    # --- Coordinates (lat/lon) — z pierwszego zgłoszenia (identyczne) ---
    lat = float(first["lat_input"])
    lon = float(first["lon_input"])

    # --- Cave name z CAVES.parquet ---
    cave_row = caves_df[caves_df["cave_id"] == cave_id]
    cave_name = cave_row.iloc[0]["name"] if len(cave_row) > 0 else ""
    n_submissions = len(subs)

    # --- Wylicz A-F ---
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    world_x, world_y = transformer.transform(lon, lat)

    mpp = 1.0 / ppm_median
    lambda0 = 19.0
    convergence_deg = (lambda0 - lon) * math.sin(math.radians(lat))
    declination = 0.0
    total_deg = north_angle + declination + convergence_deg
    rot = math.radians(total_deg)

    cos_r = math.cos(rot)
    sin_r = math.sin(rot)
    A = mpp * cos_r
    D = mpp * sin_r
    B = mpp * sin_r
    E = -mpp * cos_r
    C = world_x - (A * entrance_x + B * entrance_y)
    F = world_y - (D * entrance_x + E * entrance_y)

    # --- Quality flag ---
    flag = None
    if ppm_cv > 0.1:
        flag = "high_ppm_cv"
    elif entrance_std > 10.0:
        flag = "high_entrance_std"

    return {
        "dir_id": dir_id,
        "image_filename": image_filename,
        "image_id": image_id,
        "yaml_data": {
            "cave": {
                "inventory_number": cave_id,
                "dir_id": dir_id,
                "name": cave_name,
                "n_submissions": n_submissions,
            },
            "image": {
                "filename": image_filename,
                "image_id": image_id,
                "width": None,   # Uzupełnione po odczycie obrazu
                "height": None,
            },
            "coordinates": {
                "lat": round(lat, 6),
                "lon": round(lon, 6),
            },
            "entrance": {
                "x": round(entrance_x, 2),
                "y": round(entrance_y, 2),
            },
            "scale": {
                "pixels_per_meter": round(ppm_median, 2),
            },
            "north": {
                "angle_deg": round(north_angle, 3),
                "all_skipped": all_skipped,
            },
            "declination_deg": declination,
            "computed": {
                "convergence_deg": round(convergence_deg, 4),
                "total_rotation_deg": round(total_deg, 4),
                "A": round(A, 10),
                "D": round(D, 10),
                "B": round(B, 10),
                "E": round(E, 10),
                "C": round(C, 6),
                "F": round(F, 6),
            },
            "quality": {
                "ppm_cv": round(ppm_cv, 3),
                "ppm_values": [round(v, 2) for v in ppm_values],
                "entrance_std_px": round(entrance_std, 2),
                "outliers_removed": outliers_removed,
                "flag": flag,
            },
        },
    }


def copy_images(dir_id, image_filename, scraper_dir, output_dir):
    """Skopiuj obrazy ze scrapera do data/caves/{dir_id}/."""
    cave_dir = output_dir / dir_id
    cave_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(image_filename).stem  # np. image_631_zoom_10

    copies = [
        (scraper_dir / "caves_mono" / dir_id / image_filename, cave_dir / "image.tif"),
        (scraper_dir / "caves_upscaled" / dir_id / f"{stem}.jpg", cave_dir / "image_upscaled.jpg"),
        (scraper_dir / "caves" / dir_id / f"{stem}.jpg", cave_dir / "image_original.jpg"),
    ]

    for src, dst in copies:
        if src.exists():
            if not dst.exists():
                shutil.copy2(src, dst)
        else:
            print(f"  BRAK: {src}")


def get_image_dimensions(dir_id, output_dir):
    """Odczytaj wymiary obrazu TIFF."""
    tif_path = output_dir / dir_id / "image.tif"
    if tif_path.exists():
        with Image.open(tif_path) as img:
            return img.width, img.height
    return None, None


def represent_float(dumper, value):
    """YAML float representation — unikaj notacji naukowej."""
    if value != value:  # NaN
        return dumper.represent_scalar("tag:yaml.org,2002:null", "null")
    text = f"{value:.10f}" if abs(value) < 1 and value != 0 else str(value)
    return dumper.represent_scalar("tag:yaml.org,2002:float", text)


def main():
    args = parse_args()
    parquet_dir = Path(args.parquet_dir)
    scraper_dir = Path(args.scraper_dir)
    output_dir = Path(args.output_dir)

    # Wczytaj dane
    print("Wczytywanie danych...")
    subs = pd.read_parquet(parquet_dir / "SUBMISSIONS.parquet")
    caves = pd.read_parquet(parquet_dir / "CAVES.parquet")

    # Filtruj NORMAL submissions
    subs = subs[subs["submit_type"] == "NORMAL"].copy()
    print(f"  Zgłoszenia NORMAL: {len(subs)}")

    # Grupuj po cave_id i filtruj min submissions
    groups = subs.groupby("cave_id")
    eligible = {cid: g for cid, g in groups if len(g) >= args.min_submissions}
    print(f"  Jaskinie z >= {args.min_submissions} zgłoszeniami: {len(eligible)}")

    # Przetwarzaj jaskinie
    created = 0
    skipped = 0
    errors = 0

    yaml.add_representer(float, represent_float)

    for cave_id, cave_subs in sorted(eligible.items()):
        result = aggregate_cave(cave_id, cave_subs, caves)
        if not result:
            errors += 1
            continue

        dir_id = result["dir_id"]
        cave_dir = output_dir / dir_id
        yaml_path = cave_dir / "meta.yaml"

        if yaml_path.exists() and not args.force:
            skipped += 1
            continue

        # Kopiuj obrazy
        if not args.no_copy_images:
            copy_images(dir_id, result["image_filename"], scraper_dir, output_dir)

        # Odczytaj wymiary obrazu
        width, height = get_image_dimensions(dir_id, output_dir)
        if width and height:
            result["yaml_data"]["image"]["width"] = width
            result["yaml_data"]["image"]["height"] = height
        else:
            print(f"  UWAGA: Brak obrazu TIFF dla {dir_id}, wymiary nieznane")

        # Zapisz YAML
        cave_dir.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(result["yaml_data"], f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False, width=120)

        created += 1

    print(f"\nGotowe: utworzono {created}, pominięto {skipped}, błędów {errors}")


if __name__ == "__main__":
    main()
