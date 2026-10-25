"""Przypięte, weryfikowane wejście współrzędnych i jawny raport aktualizacji."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data/coordinate-source/source.json"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(path):
    pin = json.loads(Path(path).read_text(encoding="utf-8"))
    if (pin["schema_version"] != 1
            or pin["repository"] != "dlubom/gps-kataster-obiektow-tatr"
            or not re.fullmatch(r"v[0-9][A-Za-z0-9._-]*", pin["release"])
            or pin["asset"] != "best-measurements.csv"
            or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])):
        raise ValueError("Niepoprawny opis przypiętego źródła współrzędnych")
    snapshot = Path(pin["snapshot"])
    if snapshot.is_absolute() or ".." in snapshot.parts:
        raise ValueError("Snapshot musi być ścieżką względną w katalogu opisu źródła")
    return pin


def check_bytes(data, expected):
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f"Niezgodny SHA-256: oczekiwano {expected}, otrzymano {actual}")


def verify(manifest=DEFAULT_MANIFEST, csv_path=None):
    pin = read_manifest(manifest)
    path = Path(csv_path) if csv_path else Path(manifest).parent / pin["snapshot"]
    actual = sha256(path)
    if actual != pin["sha256"]:
        raise ValueError(f"Niezgodny SHA-256 {path}: oczekiwano {pin['sha256']}, otrzymano {actual}")
    return path


def write_verified(data, expected, output):
    check_bytes(data, expected)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Weryfikacja odbywa się przed jakimkolwiek zapisem docelowego pliku.
    output.write_bytes(data)


def fetch(manifest, output):
    pin = read_manifest(manifest)
    url = f"https://github.com/{pin['repository']}/releases/download/{pin['release']}/{pin['asset']}"
    with urlopen(url, timeout=60) as response:
        data = response.read()
    write_verified(data, pin["sha256"], output)


def read_rows(path):
    rows = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            object_id = row["object_id"]
            if not object_id or object_id in rows:
                raise ValueError(f"Brak lub powtórzony object_id={object_id}")
            rows[object_id] = row
    return rows


def compare(before, after, plans):
    links = {}
    for plan in plans:
        links.setdefault(plan["object_id"], []).append(plan["dir_id"])
    changes = []
    affected = set()
    for object_id in sorted(before.keys() | after.keys()):
        old, new = before.get(object_id, {}), after.get(object_id, {})
        fields = {key: {"before": old.get(key), "after": new.get(key)}
                  for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)}
        if not fields:
            continue
        plan_ids = sorted(links.get(object_id, []))
        affected.update(plan_ids)
        changes.append({"object_id": object_id, "plans": plan_ids, "fields": fields,
                        "before": old or None, "after": new or None,
                        "position_changed": bool({"lat", "lon"} & fields.keys())})
    return {"affected_plans": sorted(affected), "changes": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    commands = parser.add_subparsers(dest="command", required=True)
    verify_parser = commands.add_parser("verify", help="Sprawdź lokalny snapshot lub wskazany CSV")
    verify_parser.add_argument("--csv", type=Path)
    for name in ("fetch", "copy"):
        command = commands.add_parser(name, help="Odtwórz zweryfikowany CSV z release lub snapshotu")
        command.add_argument("--output", type=Path, required=True)
    impact = commands.add_parser("impact", help="Porównaj jawnie dwa przypięte snapshoty")
    impact.add_argument("--candidate", type=Path, required=True, help="Opis nowego źródła")
    impact.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            print(verify(args.manifest, args.csv))
        elif args.command == "fetch":
            fetch(args.manifest, args.output)
        elif args.command == "copy":
            pin = read_manifest(args.manifest)
            write_verified(verify(args.manifest).read_bytes(), pin["sha256"], args.output)
        else:
            from catalogue_baseline import capture_plans, coordinate_impact
            before = read_rows(verify(args.manifest))
            after = read_rows(verify(args.candidate))
            plans = capture_plans(ROOT, before)
            report = compare(before, after, plans)
            report.update({"before_source": read_manifest(args.manifest),
                           "after_source": read_manifest(args.candidate),
                           "geometry": coordinate_impact(ROOT, plans, args.manifest, args.candidate)})
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"BŁĄD źródła współrzędnych: {exc}\n")


if __name__ == "__main__":
    main()
