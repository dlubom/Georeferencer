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
import sys
import tempfile
from pathlib import Path

from pyproj import Transformer

from gps_kataster_coordinates import (
    GpsKatasterCoordinateError,
    load_best_measurements,
)

from coordinate_source import DEFAULT_MANIFEST, read_manifest, read_rows, sha256, verify
from geotiff_output import input_hashes, publish_run, validate_output_dir
from validation import ValidationError, fail, read_registry, validate_plan
import orientation
import build_identity

DATA_DIR = Path("data/caves")
TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
GEOMETRY = {
    'model': 't06-local-similarity-v1',
    'pixel': 'UI/GDAL: corner (0,0); first centre (0.5,0.5); TFW: first centre (0,0)',
    'scale': '1/pixels_per_meter in EPSG:2180 metres',
}


def parse_args():
    p = argparse.ArgumentParser(description="Generacja GeoTIFF z meta.yaml")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--cave", help="Dir ID jaskini (np. 001131)")
    group.add_argument("--all", action="store_true", help="Przetwórz wszystkie")
    group.add_argument("--changed", action="store_true",
                       help="Pełny katalog z cache według treści wejść")
    p.add_argument("--force", action="store_true", help="Wymuszaj regenerację")
    p.add_argument("--data-dir", default="data/caves", help="Katalog danych")
    p.add_argument("--output-dir", type=Path, default=Path("build/geotiff"),
                   help="Katalog wyników bez zmiany źródeł (domyślnie build/geotiff)")
    p.add_argument("--selection-file", type=Path, help="Konserwatywny zakres Git z build_changes.py")
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


def compute_world_file(meta, orientation_context=None):
    """Bieżąca skala/otwór, modele T06 lub wyłącznie historyczny kąt T05."""
    lat = float(meta["coordinates"]["lat"])
    lon = float(meta["coordinates"]["lon"])
    ppm = meta["scale"]["pixels_per_meter"]
    entrance_x = meta["entrance"]["x"]
    entrance_y = meta["entrance"]["y"]

    # Projekcja WGS84 → PL-1992
    world_x, world_y = TRANSFORMER.transform(lon, lat)

    # Skala
    mpp = 1.0 / ppm

    total_deg = orientation.rotation(meta, orientation_context)
    rot = math.radians(total_deg)

    # Parametry World File
    cos_r = math.cos(rot)
    sin_r = math.sin(rot)
    A = mpp * cos_r
    D = mpp * sin_r
    B = mpp * sin_r
    E = -mpp * cos_r
    # UI/GDAL: (0,0) jest narożnikiem. C,F TFW opisują środek (.5,.5).
    # Dlatego kliknięcie ma indeksy (x-.5,y-.5) w układzie środków TFW.
    C = world_x - (A * (entrance_x - 0.5) + B * (entrance_y - 0.5))
    F = world_y - (D * (entrance_x - 0.5) + E * (entrance_y - 0.5))

    return {
        "A": A, "D": D, "B": B, "E": E, "C": C, "F": F,
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
        "total_rotation_deg": round(params["total_rotation_deg"], 4),
        "A": round(params["A"], 10),
        "D": round(params["D"], 10),
        "B": round(params["B"], 10),
        "E": round(params["E"], 10),
        "C": round(params["C"], 6),
        "F": round(params["F"], 6),
        "orientation": orientation.summary(meta),
        "geometry": copy.deepcopy(GEOMETRY),
    }


def validate_gps_kataster_object_id(meta, gps_kataster_index):
    """Niskopoziomowa kontrola jawnego ID; bez resolvera migracyjnego."""
    coordinates = meta.get("coordinates") or {}
    object_id = coordinates.get("gps_kataster_object_id")
    if (not isinstance(object_id, str) or not object_id
            or gps_kataster_index is None
            or object_id not in gps_kataster_index.by_object_id):
        raise GpsKatasterCoordinateError(
            f"coordinates.gps_kataster_object_id: brak lub niedozwolony obiekt {object_id}")


def prepare_cave(cave_dir, gps_kataster_index, image_registry=None, meta_text=None, orientation_context=None, identity_text=None):
    source_meta, resolved_meta = validate_plan(cave_dir, gps_kataster_index, image_registry, meta_text, orientation_context, identity_text)
    try:
        params = compute_world_file(resolved_meta, orientation_context)
        if not all(math.isfinite(value) for value in params.values()):
            fail(cave_dir.name, "coordinates/scale", "parametry transformacji muszą być skończone")
    except (ArithmeticError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        fail(cave_dir.name, "coordinates/scale", f"niepoprawna transformacja: {exc}")
    return source_meta, params


def process_output(caves, output_dir, data_dir, coordinates_path=None, registry_path=None, *, force=False, changed_plans=(), selection=None, full_catalogue=True):
    """Nowy tryb: pin + preflight całej partii + sprawdzona publikacja poza źródłami."""
    output_dir = validate_output_dir(output_dir, data_dir, caves)
    catalogue_snapshot = None
    if full_catalogue:
        catalogue_snapshot = (str(Path(data_dir).resolve()), [p.name for p in find_caves(data_dir)])
        if catalogue_snapshot[1] != sorted(p.name for p in caves):
            raise ValueError('Zbiór katalogów zmienił się przed preflight pełnego buildu')
    pipeline_dir = Path(__file__).resolve().parent
    registry_path = Path(registry_path) if registry_path else pipeline_dir.parent / 'data/validation/images-v1.json'
    # Hash, walidacja, indeks i rekord manifestu używają tych samych bajtów.
    # Osobne odczyty oryginału mogłyby przy edycji A→B→A związać hash A z obliczeniem B.
    orientation_paths = [orientation.BASELINE, orientation.ARCHIVE]
    validate_output_dir(output_dir, data_dir, caves, orientation_paths)
    orientation_bytes = [p.read_bytes() for p in orientation_paths]
    orientation_context = orientation.load_context(*orientation_bytes)
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
    implementation = build_identity.implementation()
    guarded_paths = [DEFAULT_MANIFEST, coordinates_path, registry_path,
                     *(pipeline_dir.parent / name for name in implementation), *orientation_paths]
    guarded = {str(p.resolve()): sha256(p) for p in guarded_paths}
    for p, raw in ((DEFAULT_MANIFEST, pin_bytes), (coordinates_path, csv_bytes),
                   (registry_path, registry_bytes)):
        guarded[str(p.resolve())] = hashlib.sha256(raw).hexdigest()
    for p, raw in zip(orientation_paths, orientation_bytes):
        guarded[str(p.resolve())] = hashlib.sha256(raw).hexdigest()
    output_dir = validate_output_dir(output_dir, data_dir, caves, guarded_paths)
    plans = []
    for cave_dir in caves:
        raw_meta = (cave_dir / 'meta.yaml').read_bytes()
        identity_path = cave_dir / 'image-identity.json'
        raw_identity = identity_path.read_bytes() if identity_path.exists() else None
        before = input_hashes(cave_dir)
        if raw_identity is not None:
            before['image-identity.json'] = hashlib.sha256(raw_identity).hexdigest()
        else:
            before.pop('image-identity.json', None)  # snapshot obejmuje również brak pliku
        before['meta.yaml'] = hashlib.sha256(raw_meta).hexdigest()
        meta, params = prepare_cave(cave_dir, index, registry, meta_text=raw_meta.decode('utf-8'),
                                    orientation_context=orientation_context,
                                    identity_text=raw_identity.decode('utf-8') if raw_identity is not None else False)
        computed_meta = copy.deepcopy(meta)
        update_computed_section(computed_meta, params)
        plans.append({'source_directory': cave_dir, 'inputs': before, 'params': params,
                      'computed': computed_meta['computed'],
                      'orientation': orientation.summary(meta),
                      'measurement': rows[meta['coordinates']['gps_kataster_object_id']]})
    provenance = {
        'content_version': build_identity.CONTENT_VERSION,
        'environment': build_identity.environment(),
        'geometry': copy.deepcopy(GEOMETRY),
        'coordinate_source': {**pin,
                              'manifest_sha256': guarded[str(DEFAULT_MANIFEST.resolve())]},
        'orientation_sources': {p.name: guarded[str(p.resolve())] for p in orientation_paths},
        'image_registry': {'path': str(registry_path.resolve()),
                           'sha256': guarded[str(registry_path.resolve())]},
        'implementation': implementation,
        'guarded_files': guarded,
        'catalogue_snapshot': catalogue_snapshot,
    }
    return publish_run(output_dir, plans, provenance, write_tfw, force=force,
                       changed_plans=changed_plans, selection=selection)


def process_cave(cave_dir, gps_kataster_index=None, gps_kataster_strict=False,
                 image_registry=None):
    """API niskopoziomowe także dla syntetycznych danych; CLI dodatkowo weryfikuje pin."""
    try:
        source_meta, params = prepare_cave(cave_dir, gps_kataster_index, image_registry)
    except (ValueError, OSError) as exc:
        return False, str(exc)
    # Zgodność API walidacji T03. Generowanie wymaga osobnego przebiegu.
    return True, params


def find_caves(data_dir, changed_only=False):
    """Każdy nieukryty katalog, także z brakującym YAML-em, podlega preflight."""
    return [p for p in sorted(Path(data_dir).iterdir())
            if p.is_dir() and not p.name.startswith(('_', '.'))]


def main():
    args = parse_args()
    data_dir = Path(args.data_dir)
    try:
        caves = [data_dir / args.cave] if args.cave else find_caves(data_dir)
        selection = None
        if args.selection_file:
            import json
            try:
                selection = json.loads(args.selection_file.read_text())
                if (not isinstance(selection, dict) or selection.get('schema_version') != 1
                        or type(selection.get('full')) is not bool
                        or not isinstance(selection.get('plans'), list)
                        or any(not isinstance(p, str) for p in selection['plans'])):
                    raise ValueError('Niepoprawny zakres')
            except (OSError, ValueError):
                selection = {'full': True, 'plans': [], 'reason': 'niepoprawny zakres'}
        destination = process_output(caves, args.output_dir, data_dir,
            args.gps_kataster_best_measurements, args.image_registry,
            force=args.force or bool(selection and selection['full']),
            changed_plans=selection['plans'] if selection else (), selection=selection,
            full_catalogue=not args.cave)
    except (ValueError, OSError) as exc:
        sys.exit(f'BŁĄD generacji wyników: {exc}')
    print(f'Gotowe: {len(caves)} OK; kompletny przebieg: {destination}')


if __name__ == "__main__":
    main()
