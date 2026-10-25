"""T06: porównanie wyników T05/T06 bez zapisu do źródeł ani odniesienia T02."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

from coordinate_source import ROOT, DEFAULT_MANIFEST, sha256, verify
from gps_kataster_coordinates import load_best_measurements
from validation import read_registry, validate_plan
import orientation

BEFORE_COMMIT = '0c09cfae5dbaaf54fb79a877e43fb045e4e0fe6b'
BEFORE_SHA256 = 'd0b07b5c594c59447ebeca29591f02307efffb3bb4be84dc0c4030e9e863a14e'
ORDER = ('A', 'D', 'B', 'E', 'C', 'F')


def load_generator(path, expected=None):
    raw = Path(path).read_bytes()
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Generator przed zmianą: wymagane dokładne bajty generatora T05 (SHA-256)')
    # Wykonaj te same bajty, które sprawdzono, bez drugiego odczytu ścieżki.
    module = type(orientation)('impact_generator')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def rounded_tfw(generator, directory, params):
    path = generator.write_tfw(directory, params)
    return dict(zip(ORDER, map(float, path.read_text().splitlines())))


def at_click(params, click):
    x, y = click['x'] - .5, click['y'] - .5
    return [params['C'] + params['A'] * x + params['B'] * y,
            params['F'] + params['D'] * x + params['E'] * y]


def compare_plan(meta, before, after):
    positions = [at_click(p, meta['entrance']) for p in (before, after)]
    rotations = [math.degrees(math.atan2(p['D'], p['A'])) for p in (before, after)]
    scales = [math.hypot(p['A'], p['D']) for p in (before, after)]
    dx, dy = (b - a for a, b in zip(*positions))
    return {
        'position': {'before_m': positions[0], 'after_m': positions[1],
                     'dx_m': dx, 'dy_m': dy, 'distance_m': math.hypot(dx, dy)},
        'orientation': {'before_deg': rotations[0], 'after_deg': rotations[1],
                        'delta_deg': (rotations[1] - rotations[0] + 180) % 360 - 180,
                        'reference': meta['north']['reference'], 'status': meta['orientation']['status']},
        'scale': {'before_m_per_pixel': scales[0], 'after_m_per_pixel': scales[1],
                  'delta_m_per_pixel': scales[1] - scales[0]},
    }


def report(before_path):
    before = load_generator(before_path, BEFORE_SHA256)
    after_path = ROOT / 'pipeline/02_generate_geotiff.py'
    after = load_generator(after_path)
    index = load_best_measurements(verify())
    registry = read_registry()
    context = orientation.load_context()
    plans = []
    with tempfile.TemporaryDirectory(prefix='t06-impact-') as temporary:
        for path in sorted((ROOT / 'data/caves').glob('*/meta.yaml')):
            raw = path.read_bytes()
            _, meta = validate_plan(path.parent, index, registry, raw.decode('utf-8'), context)
            old_model = before.compute_world_file(meta, context)
            new_model = after.compute_world_file(meta, context)
            old = rounded_tfw(before, Path(temporary), old_model)
            new = rounded_tfw(after, Path(temporary), new_model)
            saved = context['plans'][path.parent.name]['historical_tfw']['parameters']
            historical_angle = math.degrees(math.atan2(saved['D'], saved['A']))
            current_angle = new_model['total_rotation_deg']
            plans.append({
                'dir_id': path.parent.name, 'name': meta['cave']['name'],
                'object_id': meta['coordinates']['gps_kataster_object_id'],
                'meta_sha256': hashlib.sha256(raw).hexdigest(),
                'image_sha256': meta['orientation']['image_sha256'],
                'historical_compatibility': {
                    'tfw_sha256': meta['orientation']['historical']['tfw_sha256'],
                    'tfw_rotation_deg': historical_angle, 'model_rotation_deg': current_angle,
                    'delta_deg': (current_angle - historical_angle + 180) % 360 - 180,
                    'source_metadata_verified': False,
                },
                'before_tfw': old, 'after_tfw': new,
                **compare_plan(meta, old, new),
            })
    return {
        'schema_version': 1, 'before_commit': BEFORE_COMMIT,
        'before_generator_sha256': BEFORE_SHA256,
        'after_implementation_sha256': {p.name: sha256(p) for p in
            (after_path, ROOT / 'pipeline/orientation.py', ROOT / 'pipeline/geotiff_output.py', Path(__file__))},
        'coordinate_source_sha256': sha256(verify()), 'pin_sha256': sha256(DEFAULT_MANIFEST),
        'image_registry_sha256': sha256(ROOT / 'data/validation/images-v1.json'),
        'history_sha256': context['hashes'][str(orientation.BASELINE)],
        'history_archive_sha256': context['hashes'][str(orientation.ARCHIVE)],
        'geometry': after.GEOMETRY,
        'interpretation': 'Położenie w kliknięciu UI/GDAL z zaokrąglonego TFW. '
                          'Zachowanie kąta historycznego nie potwierdza poprawności geodezyjnej. '
                          'Raport parametrów nie zastępuje odczytu GeoTIFF ani weryfikacji źródłowej północy.',
        'plan_count': len(plans), 'changed_tfw_count': sum(p['before_tfw'] != p['after_tfw'] for p in plans),
        'plans': plans,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-generator', type=Path, required=True,
                        help=f'Generator z git show {BEFORE_COMMIT}:pipeline/02_generate_geotiff.py')
    parser.add_argument('--output', type=Path, required=True, help='Raport poza danymi źródłowymi')
    args = parser.parse_args()
    result = report(args.before_generator)
    # Nie pozwól poleceniu odbioru nadpisać źródła ani historii.
    output = args.output.resolve()
    for source in (ROOT / 'data', ROOT / 'parquet', ROOT / 'pipeline'):
        if output == source or source in output.parents:
            parser.error('Raport musi leżeć poza data/, parquet/ i pipeline/')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
