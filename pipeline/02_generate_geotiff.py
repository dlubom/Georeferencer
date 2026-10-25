#!/usr/bin/env python3
"""02_generate_geotiff.py — YAML → .tfw + GeoTIFF.

Powtarzalny skrypt: czyta meta.yaml, przelicza parametry A-F,
generuje World File (.tfw) i GeoTIFF przez gdal_translate.

Użycie:
    python pipeline/02_generate_geotiff.py --cave 001131 --output-dir /tmp/georeferencer-results
    python pipeline/02_generate_geotiff.py --cave 001131 \
        --gps-kataster-best-measurements data/coordinate-source/best-measurements-v1.3.1.csv \
        --gps-kataster-strict
    python pipeline/02_generate_geotiff.py --all \
        --gps-kataster-best-measurements data/coordinate-source/best-measurements-v1.3.1.csv \
        --gps-kataster-strict
    python pipeline/02_generate_geotiff.py --changed \
        --gps-kataster-best-measurements data/coordinate-source/best-measurements-v1.3.1.csv \
        --gps-kataster-strict
    python pipeline/02_generate_geotiff.py --all --force \
        --gps-kataster-best-measurements data/coordinate-source/best-measurements-v1.3.1.csv \
        --gps-kataster-strict
"""
import argparse
import copy
import hashlib
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from pyproj import Transformer

from gps_kataster_coordinates import (
    GpsKatasterCoordinateError,
    load_best_measurements,
)

from coordinate_source import DEFAULT_MANIFEST, read_manifest, read_rows, sha256, verify
from geotiff_output import input_hashes, publish_run, validate_output_dir
from validation import ValidationError, fail, read_registry, validate_plan

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
    p.add_argument("--output-dir", type=Path,
                   help="Jawny katalog wyników bez zmiany źródeł (--cave lub --all)")
    p.add_argument(
        "--gps-kataster-best-measurements",
        help=(
            "CSV best-measurements zgodny z przypiętym source.json; "
            "współrzędne zawsze z jawnego object_id"
        ),
    )
    p.add_argument(
        "--gps-kataster-strict",
        action="store_true",
        help="Zachowany dla zgodności; pełna walidacja obowiązuje zawsze",
    )
    p.add_argument("--image-registry", type=Path,
                   help="Wersjonowany rejestr tożsamości obrazów (domyślnie data/validation/images-v1.json)")
    return p.parse_args()


def compute_world_file(meta):
    """Oblicz parametry World File z danych YAML (replikacja index.html:2277-2370)."""
    lat = float(meta["coordinates"]["lat"])
    lon = float(meta["coordinates"]["lon"])
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


def validate_gps_kataster_object_id(meta, gps_kataster_index):
    """Niskopoziomowa kontrola jawnego ID; bez resolvera migracyjnego."""
    coordinates = meta.get("coordinates") or {}
    object_id = coordinates.get("gps_kataster_object_id")
    if (not isinstance(object_id, str) or not object_id
            or gps_kataster_index is None
            or object_id not in gps_kataster_index.by_object_id):
        raise GpsKatasterCoordinateError(
            f"coordinates.gps_kataster_object_id: brak lub niedozwolony obiekt {object_id}")


def prepare_cave(cave_dir, gps_kataster_index, image_registry=None, meta_text=None):
    source_meta, resolved_meta = validate_plan(cave_dir, gps_kataster_index, image_registry, meta_text)
    try:
        params = compute_world_file(resolved_meta)
        if not all(math.isfinite(value) for value in params.values()):
            fail(cave_dir.name, "coordinates/scale", "parametry transformacji muszą być skończone")
    except (ArithmeticError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        fail(cave_dir.name, "coordinates/scale", f"niepoprawna transformacja: {exc}")
    return source_meta, params


def process_prepared(cave_dir, source_meta, params):
    """Przejściowy zapis w miejscu, zachowany dla dotychczasowych odbiorców do T10."""
    write_tfw(cave_dir, params)
    update_computed_section(source_meta, params)
    yaml.add_representer(float, represent_float)
    with open(cave_dir / "meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(source_meta, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False, width=120)
    return generate_geotiff(cave_dir)


def process_output(caves, output_dir, data_dir, coordinates_path=None, registry_path=None):
    """Nowy tryb: pin + preflight całej partii + sprawdzona publikacja poza źródłami."""
    output_dir = validate_output_dir(output_dir, data_dir, caves)
    pipeline_dir = Path(__file__).resolve().parent
    registry_path = Path(registry_path) if registry_path else pipeline_dir.parent / 'data/validation/images-v1.json'
    # Hash, walidacja, indeks i rekord manifestu używają tych samych bajtów.
    # Osobne odczyty oryginału mogłyby przy edycji A→B→A związać hash A z obliczeniem B.
    pin_bytes = DEFAULT_MANIFEST.read_bytes()
    with tempfile.TemporaryDirectory(prefix='georeferencer-inputs-') as temporary:
        snapshot_dir = Path(temporary)
        pin_snapshot = snapshot_dir / 'source.json'
        pin_snapshot.write_bytes(pin_bytes)
        pin = read_manifest(pin_snapshot)
        coordinates_path = Path(coordinates_path) if coordinates_path else DEFAULT_MANIFEST.parent / pin['snapshot']
        csv_bytes = coordinates_path.read_bytes()
        registry_bytes = registry_path.read_bytes()
        csv_snapshot = snapshot_dir / 'best-measurements.csv'
        csv_snapshot.write_bytes(csv_bytes)
        registry_snapshot = snapshot_dir / 'images.json'
        registry_snapshot.write_bytes(registry_bytes)
        verify(manifest=pin_snapshot, csv_path=csv_snapshot)
        index = load_best_measurements(csv_snapshot)
        rows = read_rows(csv_snapshot)
        registry = read_registry(registry_snapshot)
    guarded_paths = [DEFAULT_MANIFEST, coordinates_path, registry_path,
                     *(pipeline_dir / name for name in (
                         '02_generate_geotiff.py', 'geotiff_output.py', 'validation.py',
                         'coordinate_source.py', 'gps_kataster_coordinates.py', 'meta-schema-v1.json'))]
    guarded = {str(p.resolve()): sha256(p) for p in guarded_paths}
    for p, raw in ((DEFAULT_MANIFEST, pin_bytes), (coordinates_path, csv_bytes),
                   (registry_path, registry_bytes)):
        guarded[str(p.resolve())] = hashlib.sha256(raw).hexdigest()
    output_dir = validate_output_dir(output_dir, data_dir, caves, guarded_paths)
    plans = []
    for cave_dir in caves:
        raw_meta = (cave_dir / 'meta.yaml').read_bytes()
        before = input_hashes(cave_dir)
        before['meta.yaml'] = hashlib.sha256(raw_meta).hexdigest()
        meta, params = prepare_cave(cave_dir, index, registry, meta_text=raw_meta.decode('utf-8'))
        computed_meta = copy.deepcopy(meta)
        update_computed_section(computed_meta, params)
        plans.append({'source_directory': cave_dir, 'inputs': before, 'params': params,
                      'computed': computed_meta['computed'],
                      'measurement': rows[meta['coordinates']['gps_kataster_object_id']]})
    provenance = {
        'coordinate_source': {**pin,
                              'manifest_sha256': guarded[str(DEFAULT_MANIFEST.resolve())]},
        'image_registry': {'path': str(registry_path.resolve()),
                           'sha256': guarded[str(registry_path.resolve())]},
        'implementation': {p.name: guarded[str(p.resolve())] for p in guarded_paths[3:]},
        'guarded_files': guarded,
    }
    return publish_run(output_dir, plans, provenance, write_tfw)


def process_cave(cave_dir, gps_kataster_index=None, gps_kataster_strict=False,
                 image_registry=None):
    """API niskopoziomowe także dla syntetycznych danych; CLI dodatkowo weryfikuje pin."""
    try:
        source_meta, params = prepare_cave(cave_dir, gps_kataster_index, image_registry)
    except (ValueError, OSError) as exc:
        return False, str(exc)
    return process_prepared(cave_dir, source_meta, params)


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
    if args.output_dir and args.changed:
        sys.exit('BŁĄD: --output-dir obsługuje --cave lub --all; tryb --changed należy do T10')
    try:
        # Także jawny argument musi odpowiadać przypiętym bajtom. Brak argumentu
        # oznacza wersjonowany snapshot, nigdy liczby z YAML ani latest.
        path = verify(csv_path=args.gps_kataster_best_measurements)
        gps_kataster_index = load_best_measurements(path)
        registry = read_registry(args.image_registry) if args.image_registry else read_registry()
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(f"BŁĄD katalogu/obrazu: {exc}")

    if args.cave:
        caves = [data_dir / args.cave]
    elif args.all:
        caves = find_caves(data_dir)
    else:  # --changed
        caves = find_caves(data_dir, changed_only=True)

    if not caves:
        print("Brak jaskiń do przetworzenia.")
        return

    if args.output_dir:
        try:
            destination = process_output(caves, args.output_dir, data_dir, path, args.image_registry)
        except (ValueError, OSError) as exc:
            sys.exit(f'BŁĄD generacji wyników: {exc}')
        print(f'Gotowe: {len(caves)} OK; kompletny przebieg: {destination}')
        return

    # Preflight całego wybranego zestawu przed pierwszym zapisem artefaktu.
    prepared = []
    errors = []
    for cave_dir in caves:
        try:
            prepared.append((cave_dir, *prepare_cave(cave_dir, gps_kataster_index, registry)))
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    if errors:
        for message in errors:
            print(f"BŁĄD {message}", file=sys.stderr)
        sys.exit(1)

    print(f"Przetwarzanie {len(prepared)} jaskiń...")
    failures = 0
    for cave_dir, meta, params in prepared:
        ok, message = process_prepared(cave_dir, meta, params)
        if not ok:
            print(f"BŁĄD {cave_dir.name}: {message}", file=sys.stderr)
            failures += 1
    print(f"Gotowe: {len(prepared) - failures} OK, {failures} błędów")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
