#!/usr/bin/env python3
"""03_report.py — Raport QA z danych meta.yaml.

Generuje:
  - data/caves/_reports/summary.csv   — podsumowanie wszystkich jaskiń
  - data/caves/_reports/flagged.csv   — jaskinie z problemami jakościowymi
  - data/caves/_reports/missing.csv   — jaskinie bez obrazów lub z brakującymi danymi

Użycie:
    python pipeline/03_report.py
"""
import csv
from pathlib import Path

import yaml

DATA_DIR = Path("data/caves")
REPORTS_DIR = DATA_DIR / "_reports"


def load_all_meta():
    """Wczytaj wszystkie meta.yaml."""
    metas = []
    for yaml_path in sorted(DATA_DIR.glob("*/meta.yaml")):
        if yaml_path.parent.name.startswith("_"):
            continue
        with open(yaml_path, encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        meta["_dir"] = yaml_path.parent.name
        meta["_has_tif"] = (yaml_path.parent / "image.tif").exists()
        meta["_has_tfw"] = (yaml_path.parent / "image.tfw").exists()
        meta["_has_georef"] = (yaml_path.parent / "image_georef.tif").exists()
        metas.append(meta)
    return metas


def write_summary(metas):
    """Zapisz summary.csv."""
    path = REPORTS_DIR / "summary.csv"
    fields = [
        "dir_id", "inventory_number", "name", "n_submissions",
        "lat", "lon", "pixels_per_meter", "north_angle_deg",
        "ppm_cv", "entrance_std_px", "flag",
        "has_tif", "has_tfw", "has_georef",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in metas:
            quality = m.get("quality", {})
            w.writerow({
                "dir_id": m.get("cave", {}).get("dir_id", ""),
                "inventory_number": m.get("cave", {}).get("inventory_number", ""),
                "name": m.get("cave", {}).get("name", ""),
                "n_submissions": m.get("cave", {}).get("n_submissions", 0),
                "lat": m.get("coordinates", {}).get("lat", ""),
                "lon": m.get("coordinates", {}).get("lon", ""),
                "pixels_per_meter": m.get("scale", {}).get("pixels_per_meter", ""),
                "north_angle_deg": m.get("north", {}).get("angle_deg", ""),
                "ppm_cv": quality.get("ppm_cv", ""),
                "entrance_std_px": quality.get("entrance_std_px", ""),
                "flag": quality.get("flag", ""),
                "has_tif": m["_has_tif"],
                "has_tfw": m["_has_tfw"],
                "has_georef": m["_has_georef"],
            })
    print(f"  summary.csv: {len(metas)} jaskiń")


def write_flagged(metas):
    """Zapisz flagged.csv — jaskinie z quality.flag != null."""
    flagged = [m for m in metas if m.get("quality", {}).get("flag")]
    path = REPORTS_DIR / "flagged.csv"
    fields = ["dir_id", "inventory_number", "name", "flag", "ppm_cv", "entrance_std_px"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in flagged:
            quality = m.get("quality", {})
            w.writerow({
                "dir_id": m.get("cave", {}).get("dir_id", ""),
                "inventory_number": m.get("cave", {}).get("inventory_number", ""),
                "name": m.get("cave", {}).get("name", ""),
                "flag": quality.get("flag", ""),
                "ppm_cv": quality.get("ppm_cv", ""),
                "entrance_std_px": quality.get("entrance_std_px", ""),
            })
    print(f"  flagged.csv: {len(flagged)} jaskiń")


def write_missing(metas):
    """Zapisz missing.csv — jaskinie bez obrazu lub tfw."""
    missing = [m for m in metas if not m["_has_tif"] or not m["_has_tfw"]]
    path = REPORTS_DIR / "missing.csv"
    fields = ["dir_id", "inventory_number", "name", "has_tif", "has_tfw", "has_georef"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in missing:
            w.writerow({
                "dir_id": m.get("cave", {}).get("dir_id", ""),
                "inventory_number": m.get("cave", {}).get("inventory_number", ""),
                "name": m.get("cave", {}).get("name", ""),
                "has_tif": m["_has_tif"],
                "has_tfw": m["_has_tfw"],
                "has_georef": m["_has_georef"],
            })
    print(f"  missing.csv: {len(missing)} jaskiń")


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Wczytywanie meta.yaml...")
    metas = load_all_meta()
    if not metas:
        print("Brak danych — uruchom najpierw 01_extract_yaml.py")
        return

    print(f"Znaleziono {len(metas)} jaskiń. Generowanie raportów...")
    write_summary(metas)
    write_flagged(metas)
    write_missing(metas)
    print("\nRaporty w:", REPORTS_DIR)


if __name__ == "__main__":
    main()
