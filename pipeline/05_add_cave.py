#!/usr/bin/env python3
"""T08: jednoznaczny plan, jawne źródła, T03/T04 i publikacja bez nadpisywania.

Pełne wywołania i konwencje: pipeline/MANUAL_ADD.md.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import copy
import ctypes
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from PIL import Image
import yaml

from coordinate_source import ROOT, DEFAULT_MANIFEST, check_bytes, read_manifest
from gps_kataster_coordinates import LAT_TEMPLATE, LON_TEMPLATE, load_best_measurements_csv_bytes
import orientation
from validation import read_registry, validate_meta, resolve_coordinates, validate_image, validate_orientation

Image.MAX_IMAGE_PIXELS = None
SCRAPER_DIR = ROOT.parent / 'Polish-Cave-Data-Scraper'
JSONL_PATH = ROOT.parent / 'Jaskiniowy-Kataster-Tatr-Zachodnich/doc/jaskinie_polski_pig_dump.jsonl'
DATA_DIR = ROOT / 'data/caves'


def identifier(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', value):
        raise ValueError(f'{field}: wymagany bezpieczny identyfikator, bez ścieżek i początkowego _')
    return value


def load_cave_from_jsonl(cave_id, path=JSONL_PATH, raw=None):
    raw = Path(path).read_bytes() if raw is None else raw
    records = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    found = [r for r in records if r.get('cave_id') == cave_id]
    if len(found) != 1:
        raise ValueError(f'cave_id {cave_id}: wymagany dokładnie jeden rekord JSONL, znaleziono {len(found)}')
    return found[0]


def find_plan_image(cave_id, cave_data, image_id=None, scraper_dir=SCRAPER_DIR):
    """Wyłącznie wskazana grafika typu plan i jej dokładny plik mono."""
    images = cave_data.get('images')
    if not isinstance(images, list) or any(not isinstance(i, dict) or not isinstance(i.get('metadata'), dict) for i in images):
        raise ValueError('images: wymagane metadane obrazów')
    ids = [i['metadata'].get('graphics_id') for i in images]
    if any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('graphics_id: brak, niepoprawne lub powtórzone ID obrazu')
    plans = [i for i in images if i['metadata'].get('graphics_type_name') == 'plan'
             and (image_id is None or i['metadata']['graphics_id'] == image_id)]
    if len(plans) != 1:
        raise ValueError(f'image-id: wybór wieloznaczny albo brak planu; znaleziono {len(plans)}, wskaż --image-id')
    selected = plans[0]
    meta = selected['metadata']
    filename = f"image_{meta['graphics_id']}_zoom_10"
    expected_path = f'caves/{cave_id}/{filename}.jpg'
    if selected.get('image_path') != expected_path:
        raise ValueError('image_path: niespójność ścieżki, ID jaskini i graphics_id w metadanych')
    if meta.get('inventory_number') != cave_data.get('inventory_number'):
        raise ValueError('inventory_number: niespójność metadanych jaskini i obrazu')
    path = Path(scraper_dir) / 'caves_mono' / cave_id / (filename + '.tif')
    if not path.is_file():
        raise ValueError(f'Brak wskazanego obrazu TIFF: {path}')
    return filename, copy.deepcopy(meta)


def read_image(path, image_meta):
    # Jeden snapshot w pamięci: wymiary i hash dotyczą tych samych bajtów.
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'TIFF' or image.mode != '1' or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Obraz mono: wymagany jednostronicowy TIFF 1-bit')
        image.load()
        width, height = image.size
    for key, size in [('maxWidth', width), ('maxHeight', height)]:
        if key in image_meta and (type(image_meta[key]) is not int or image_meta[key] <= 0 or image_meta[key] * 2 != size):
            raise ValueError(f'image.{key}: wymiary mono niespójne z metadanymi obrazu 2x')
    return raw, width, height


def required(args, *fields):
    for field in fields:
        value = getattr(args, field)
        if value is None or isinstance(value, str) and not value.strip():
            raise ValueError(f'--{field.replace("_", "-")}: wymagane dane do planu produkcyjnego')


def build_meta(args, cave, image_meta, filename, raw, width, height, pin, jsonl_sha256):
    required(args, 'plan_id', 'gps_kataster_object_id', 'entrance_x', 'entrance_y', 'pixels_per_meter',
             'image_sha256', 'entrance_source', 'scale_source', 'north_reference', 'decision_reason', 'decision_date')
    try:
        date.fromisoformat(args.decision_date)
    except ValueError as exc:
        raise ValueError('--decision-date: wymagana poprawna data YYYY-MM-DD') from exc
    identifier(args.plan_id, 'plan-id')
    check_bytes(raw, args.image_sha256)
    if args.north_skipped:
        if args.north_reference != 'unknown' or args.north_source is not None:
            raise ValueError('--north-skipped: dozwolone tylko unknown bez pozornego źródła pomiaru')
        angle, origin = None, 'unknown'
    else:
        required(args, 'north_angle', 'north_source')
        angle, origin = args.north_angle, 'measured'
    if args.north_reference == 'unknown':
        required(args, 'assumed_grid_angle', 'grid_angle_convention')
    elif args.assumed_grid_angle is not None or args.grid_angle_convention is not None:
        raise ValueError('Przyjęty kąt siatki dotyczy wyłącznie nowego unknown')
    if args.north_reference == 'magnetic':
        required(args, 'declination', 'declination_basis', 'declination_epoch', 'declination_sign_convention')
    elif any(value is not None for value in (args.declination, args.declination_basis,
                                             args.declination_epoch, args.declination_sign_convention)):
        raise ValueError('Parametry deklinacji wymagają --north-reference magnetic')
    north = {'reference': args.north_reference, 'angle_deg': angle,
             'angle_origin': origin, 'all_skipped': args.north_skipped}
    if args.north_source is not None:
        north['evidence'] = args.north_source
    orient = {'mode': 'assumed_grid' if args.north_reference == 'unknown' else 'reference',
              'status': 'unverified', 'image_sha256': orientation.digest(raw),
              'uncertainty_reason': args.decision_reason}
    if args.north_reference == 'unknown':
        orient['grid_assumption'] = {'rotation_deg': args.assumed_grid_angle, 'crs': 'EPSG:2180',
                                    'convention': args.grid_angle_convention, 'reason': args.decision_reason}
    declination = {'status': 'unknown', 'basis': 'Nie użyto deklinacji; brak ustalonej podstawy magnetycznej.'}
    if args.north_reference == 'magnetic':
        declination = {'status': 'documented', 'basis': args.declination_basis,
                       'epoch': args.declination_epoch, 'sign_convention': args.declination_sign_convention}
    meta = {
        'cave': {'dir_id': args.plan_id, 'source_cave_id': args.cave, 'name': cave.get('name'),
                 'inventory_number': cave.get('inventory_number'), 'n_submissions': 0},
        'image': {'filename': filename + '.tif', 'image_id': image_meta['graphics_id'],
                  'width': width, 'height': height},
        'coordinates': {'gps_kataster_object_id': args.gps_kataster_object_id, 'lat': LAT_TEMPLATE, 'lon': LON_TEMPLATE},
        'entrance': {'x': args.entrance_x, 'y': args.entrance_y},
        'scale': {'pixels_per_meter': args.pixels_per_meter}, 'north': north,
        'declination_deg': args.declination if args.declination is not None else 0.0,
        'declination': declination, 'orientation': orient, 'computed': {}, 'quality': {'flag': 'manual'},
        'provenance': {
            'method': 'manual_t08', 'date': args.decision_date,
            'image': {'source_cave_id': args.cave, 'graphics_id': image_meta['graphics_id'],
                      'path': f'caves_mono/{args.cave}/{filename}.tif', 'sha256': orientation.digest(raw),
                      'metadata': image_meta},
            'registry': {'path': str(args.jsonl), 'sha256': jsonl_sha256},
            'entrance': {'method': 'manual_click', 'source': args.entrance_source},
            'scale': {'method': 'manual_measurement', 'source': args.scale_source},
            'coordinates': {**pin, 'object_id': args.gps_kataster_object_id}}}
    orient['origin'] = {'kind': 'manual_t08', 'plan_id': args.plan_id,
                        'reason': args.decision_reason, 'date': args.decision_date}
    return meta


def accept_generation(plan_dir, data_dir, output_dir):
    """Ta sama ścieżka T04 co CLI: snapshoty, GDAL, odczyt i publikacja poza źródłami."""
    spec = importlib.util.spec_from_file_location('manual_add_generator', ROOT / 'pipeline/02_generate_geotiff.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.process_output([plan_dir], output_dir, data_dir, full_catalogue=False)


def publish_directory(source, destination):
    """Atomowy rename bez zastępowania celu, także utworzonego w czasie wyścigu.

    Linux: renameat2(RENAME_NOREPLACE); macOS: renamex_np(RENAME_EXCL).
    Brak wsparcia kończy operację błędem, bez zastępczego zwykłego rename.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    source, destination = os.fsencode(source), os.fsencode(destination)
    if sys.platform == 'linux' and hasattr(libc, 'renameat2'):
        function = libc.renameat2
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        result = function(-100, source, -100, destination, 1)  # AT_FDCWD, RENAME_NOREPLACE
    elif sys.platform == 'darwin' and hasattr(libc, 'renamex_np'):
        function = libc.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        result = function(source, destination, 4)  # RENAME_EXCL, sys/stdio.h
    else:
        raise OSError(errno.ENOTSUP, 'Brak atomowego rename bez zastępowania celu')
    if result != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), os.fsdecode(destination))


@contextmanager
def addition_lock(data_dir):
    """O_EXCL serializuje współpracujące wywołania; brak przejmowania cudzej blokady."""
    lock = data_dir / '.manual-add.lock'
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def add_plan(args):
    identifier(args.cave, 'cave')
    jsonl_raw = args.jsonl.read_bytes()
    cave = load_cave_from_jsonl(args.cave, args.jsonl, raw=jsonl_raw)
    filename, image_meta = find_plan_image(args.cave, cave, args.image_id, args.scraper_dir)
    source = args.scraper_dir / 'caves_mono' / args.cave / (filename + '.tif')
    raw, width, height = read_image(source, image_meta)
    print(f"Jaskinia PIG: {args.cave}; grafika: {image_meta['graphics_id']}; mono: {width}×{height}")
    print(f'Obraz: {source}\nSHA-256: {orientation.digest(raw)}')
    if args.dry_run and args.plan_id is None and args.entrance_x is None and args.pixels_per_meter is None:
        return None  # inspekcja obrazu; żadnego gotowego planu
    # Pin i indeks pochodzą z jednych zweryfikowanych bajtów, także w podglądzie.
    pin = read_manifest(DEFAULT_MANIFEST)
    csv_path = args.gps_kataster_best_measurements or DEFAULT_MANIFEST.parent / pin['snapshot']
    csv_raw = Path(csv_path).read_bytes()
    check_bytes(csv_raw, pin['sha256'])
    index = load_best_measurements_csv_bytes(csv_raw)
    meta = build_meta(args, cave, image_meta, filename, raw, width, height, pin, orientation.digest(jsonl_raw))
    context = orientation.default_context()
    registry = read_registry()
    if args.plan_id in context['plans'] or args.plan_id in registry['plans']:
        raise ValueError('plan-id istnieje w T02 lub rejestrze; nowy plan wymaga własnego ID')
    target = args.data_dir / args.plan_id
    if os.path.lexists(target):
        raise ValueError(f'Plan już istnieje: {target}; dodawanie nigdy nie nadpisuje')
    identity = {'schema_version': 1, 'plans': {args.plan_id: {
        **meta['image'], 'sha256': orientation.digest(raw)}}}
    identity_text = json.dumps(identity, ensure_ascii=False, indent=2) + '\n'
    yaml_text = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    # Dry-run: pełny T03 bez zapisu i bez tymczasowych plików.
    validate_meta(meta, args.plan_id)
    resolved = resolve_coordinates(meta, index, args.plan_id)
    validate_image(meta, target, registry, identity_text, image_path=source)
    validate_orientation(resolved, context)
    if args.dry_run:
        print('\n--- meta.yaml (podgląd bez zapisu) ---\n' + yaml_text)
        return meta
    args.data_dir.mkdir(parents=True, exist_ok=True)
    with addition_lock(args.data_dir):
        if os.path.lexists(target):
            raise ValueError(f'Plan już istnieje: {target}')
        with tempfile.TemporaryDirectory(prefix='.manual-add-', dir=args.data_dir) as staging:
            staged_plan = Path(staging) / args.plan_id
            staged_plan.mkdir()
            (staged_plan / 'image.tif').write_bytes(raw)
            (staged_plan / 'meta.yaml').write_text(yaml_text, encoding='utf-8')
            (staged_plan / 'image-identity.json').write_text(identity_text, encoding='utf-8')
            for folder, output in [('caves', 'image_original.jpg'), ('caves_upscaled', 'image_upscaled.jpg')]:
                optional = args.scraper_dir / folder / args.cave / (filename + '.jpg')
                if optional.exists():
                    shutil.copyfile(optional, staged_plan / output)
            with tempfile.TemporaryDirectory(prefix='manual-add-acceptance-') as output:
                accept_generation(staged_plan, Path(staging), Path(output) / 'results')
            if os.path.lexists(target):
                raise ValueError(f'Plan już istnieje: {target}')
            # Jeden rename: YAML + obraz + rejestr pojawiają się razem.
            publish_directory(staged_plan, target)
    print(f'Zapisano plan {args.plan_id}: {target}; T03 i T04 PASS, status unverified')
    return meta


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Bezpiecznie dodaj jeden plan; instrukcja: pipeline/MANUAL_ADD.md')
    p.add_argument('--cave', required=True, help='Źródłowe cave_id PIG, nie ID katalogu planu')
    p.add_argument('--plan-id', help='Nowy, odrębny identyfikator katalogu planu')
    p.add_argument('--image-id', type=int, help='graphics_id; wymagane przy wielu planach')
    p.add_argument('--scraper-dir', type=Path, default=SCRAPER_DIR)
    p.add_argument('--jsonl', type=Path, default=JSONL_PATH)
    p.add_argument('--data-dir', type=Path, default=DATA_DIR)
    p.add_argument('--image-sha256', help='Hash obrazu mono, na którym wykonano pomiary')
    p.add_argument('--gps-kataster-object-id')
    p.add_argument('--gps-kataster-best-measurements', type=Path, help='Wyłącznie CSV zgodny z pinem')
    for field in ('entrance-x', 'entrance-y', 'pixels-per-meter', 'assumed-grid-angle', 'declination'):
        p.add_argument('--' + field, type=float)
    for field in ('entrance-source', 'scale-source', 'north-source', 'decision-reason', 'decision-date',
                  'declination-basis', 'declination-epoch'):
        p.add_argument('--' + field)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--north-angle', type=float, help='Zmierzony kąt strzałki, również jawne 0°')
    group.add_argument('--north-skipped', action='store_true', help='Brak pomiaru strzałki; tylko unknown')
    p.add_argument('--north-reference', choices=orientation.REFERENCES)
    p.add_argument('--grid-angle-convention', choices=[orientation.GRID_CONVENTION])
    p.add_argument('--declination-sign-convention', choices=['east_positive'])
    p.add_argument('--dry-run', action='store_true', help='Odczyt/podgląd T03 bez zapisu; bez odbioru GDAL')
    return p.parse_args(argv)


def main():
    try:
        add_plan(parse_args())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        sys.exit(f'BŁĄD dodawania planu: {exc}')


if __name__ == '__main__':
    main()
