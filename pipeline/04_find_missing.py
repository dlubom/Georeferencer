#!/usr/bin/env python3
"""Znajduje jaskinie tatrzańskie z JSONL, które nie są w data/caves/.

Porównuje rejestr PIG (JSONL) z istniejącymi katalogami jaskiń.
Wypisuje brakujące jaskinie z planami, posortowane po długości malejąco.
"""

import csv
import json
from pathlib import Path

JSONL_PATH = Path.home() / "projects/Jaskiniowy-Kataster-Tatr-Zachodnich/doc/jaskinie_polski_pig_dump.jsonl"
CAVES_DIR = Path(__file__).resolve().parent.parent / "data" / "caves"
REPORT_DIR = CAVES_DIR / "_reports"


def load_jsonl_tatry(path: Path) -> list[dict]:
    """Ładuje jaskinie tatrzańskie z JSONL."""
    caves = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("region") == "Tatry":
                caves.append(rec)
    return caves


def count_plans(images: list[dict]) -> int:
    """Liczy obrazy typu 'plan' (nie przekroje)."""
    return sum(
        1 for img in images
        if img.get("metadata", {}).get("graphics_type_name") == "plan"
    )


def parse_float(val) -> float:
    """Parsuje wartość na float, zwraca 0.0 dla brakujących."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def main():
    # Ładuj jaskinie tatrzańskie z JSONL
    tatry = load_jsonl_tatry(JSONL_PATH)
    print(f"Jaskinie tatrzańskie w JSONL: {len(tatry)}")

    # Istniejące katalogi w data/caves/
    existing_ids = {
        d.name for d in CAVES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    }
    print(f"Istniejące katalogi w data/caves/: {len(existing_ids)}")

    # Znajdź brakujące z planami
    missing = []
    missing_no_plan = 0
    for cave in tatry:
        cave_id = cave["cave_id"]
        if cave_id in existing_ids:
            continue

        images = cave.get("images") or []
        n_plans = count_plans(images)

        if n_plans == 0:
            missing_no_plan += 1
            continue

        missing.append({
            "cave_id": cave_id,
            "inventory_number": cave.get("inventory_number", ""),
            "name": cave.get("name", ""),
            "length_m": parse_float(cave.get("length_m")),
            "depth_m": parse_float(cave.get("depth_m")),
            "lat": parse_float(cave.get("latitude")),
            "lon": parse_float(cave.get("longitude")),
            "n_plans": n_plans,
            "n_images_total": len(images),
        })

    # Sortuj po długości malejąco
    missing.sort(key=lambda c: c["length_m"], reverse=True)

    print(f"Brakujące z planami: {len(missing)}")
    print(f"Brakujące bez planów: {missing_no_plan}")
    print()

    # Wyświetl tabelę
    header = f"{'cave_id':>8}  {'nr_inw':<25}  {'nazwa':<40}  {'dł[m]':>7}  {'gł[m]':>6}  {'planów':>6}"
    print(header)
    print("-" * len(header))
    for c in missing:
        name = c["name"][:40]
        inv = c["inventory_number"][:25]
        print(
            f"{c['cave_id']:>8}  {inv:<25}  {name:<40}  "
            f"{c['length_m']:>7.0f}  {c['depth_m']:>6.0f}  {c['n_plans']:>6}"
        )

    # Zapisz CSV
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORT_DIR / "missing_tatry.csv"
    fields = ["cave_id", "inventory_number", "name", "length_m", "depth_m", "lat", "lon", "n_plans", "n_images_total"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(missing)

    print(f"\nZapisano: {csv_path}")


if __name__ == "__main__":
    main()
