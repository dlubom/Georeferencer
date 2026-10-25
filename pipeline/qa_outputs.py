"""T09: tylko odczyt jednego, raz rozwiązanego przebiegu T04.

Brak wybranego przebiegu jest stanem raportu źródeł. Wybrany przebieg musi
zawierać dokładnie zgłoszony katalog; nie szukamy najnowszego po mtime.
"""
import copy
import json
import math
from pathlib import Path

from coordinate_source import ROOT, DEFAULT_MANIFEST, read_manifest, sha256
from geotiff_output import check_geotiff, input_hashes, tfw_geotransform
import orientation

OUTPUTS = {'image.tfw', 'image_georef.tif', 'computed.json'}
MODULES = ('02_generate_geotiff.py', 'geotiff_output.py', 'validation.py',
           'coordinate_source.py', 'gps_kataster_coordinates.py', 'meta-schema-v1.json', 'orientation.py')


def _implementation():
    return {p.name: sha256(p) for p in [*(ROOT / 'pipeline' / n for n in MODULES),
                                      orientation.BASELINE, orientation.ARCHIVE]}


def inspect_run(run_dir, plans, prepared, rows, registry_path, generator, require_results=False):
    """Zwróć (stany planów, problemy techniczne). prepared ma tylko poprawne wejścia."""
    states = {p: 'not_requested' for p in plans}
    problems = []

    def problem(plan_id, rule, evidence):
        problems.append({'plan_id': plan_id, 'rule': rule, 'evidence': evidence})

    if run_dir is None:
        if require_results:
            states = dict.fromkeys(plans, 'missing')
            problem('__run__', 'result.missing', 'Nie wskazano wymaganego przebiegu T04')
        return states, problems
    try:
        run = Path(run_dir).resolve(strict=True)  # current jest rozwiązywany dokładnie raz
        manifest = json.loads((run / 'manifest.json').read_text())
        if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1
                or manifest.get('status') != 'complete' or not isinstance(manifest.get('plans'), list)):
            raise ValueError('Wymagany kompletny manifest T04 v1')
        records = manifest['plans']
        ids = [p['dir_id'] for p in records]
        if any(not isinstance(p, str) or p not in plans for p in ids) or len(set(ids)) != len(ids) or set(ids) != set(plans):
            problem('__run__', 'result.inventory', {'expected': sorted(plans), 'actual': ids})
        expected_names = set(plans) | {'manifest.json'}
        if {p.name for p in run.iterdir()} != expected_names:
            problem('__run__', 'result.inventory', 'Niekompletny lub nadmiarowy zestaw plików/katalogów przebiegu')
        pin = {**read_manifest(DEFAULT_MANIFEST), 'manifest_sha256': sha256(DEFAULT_MANIFEST)}
        common_stale = []
        for name, current in {
            'coordinate_source': pin,
            'image_registry': {'sha256': sha256(registry_path)},
            'orientation_sources': {p.name: sha256(p) for p in (orientation.BASELINE, orientation.ARCHIVE)},
            'implementation': _implementation(), 'geometry': generator.GEOMETRY,
        }.items():
            saved = manifest.get(name)
            if name == 'image_registry' and isinstance(saved, dict):
                saved = {'sha256': saved.get('sha256')}
            if saved != current:
                common_stale.append(name)
        by_id = {p['dir_id']: p for p in records if p['dir_id'] in plans}
        for plan_id, directory in sorted(plans.items()):
            states[plan_id] = 'missing'
            record = by_id.get(plan_id)
            target = run / plan_id
            if record is None or not target.is_dir():
                problem(plan_id, 'result.missing', 'Brak planu w wybranym przebiegu')
                continue
            try:
                if target.is_symlink() or any(p.is_symlink() for p in target.iterdir()):
                    raise ValueError('Artefakty przebiegu nie mogą być dowiązaniami')
                actual = {p.name for p in target.iterdir()}
                if OUTPUTS - actual:
                    problem(plan_id, 'result.missing', sorted(OUTPUTS - actual))
                    continue
                if actual != OUTPUTS or set(record.get('outputs', {})) != OUTPUTS:
                    raise ValueError('Niepoprawny komplet artefaktów planu')
                if any(sha256(target / name) != record['outputs'][name] for name in OUTPUTS):
                    raise ValueError('Hash artefaktu niezgodny z manifestem')
                transform = tfw_geotransform(target / 'image.tfw')
                if len(transform) != 6 or not all(math.isfinite(v) for v in transform):
                    raise ValueError('Niepoprawny TFW')
                # Nawet stary wynik musi zachować spójność własnych artefaktów.
                values = list(map(float, (target / 'image.tfw').read_text().splitlines()))
                params = record['parameters']
                if values != [float(f'{params[k]:.{10 if k in "ADBE" else 6}f}') for k in ('A', 'D', 'B', 'E', 'C', 'F')]:
                    raise ValueError('TFW niezgodny z parameters manifestu')
                computed = json.loads((target / 'computed.json').read_text())
                stale = common_stale[:]
                inputs = input_hashes(directory)
                if record.get('inputs') != inputs:
                    stale.append('inputs')
                if plan_id not in prepared:
                    stale.append('invalid_input')
                else:
                    meta, resolved, params = prepared[plan_id]
                    if record.get('measurement') != rows[meta['coordinates']['gps_kataster_object_id']]:
                        stale.append('measurement')
                    if record.get('orientation') != orientation.summary(meta) or record.get('parameters') != params:
                        stale.append('calculation')
                    expected = copy.deepcopy(meta)
                    generator.update_computed_section(expected, params)
                    if computed != expected['computed']:
                        stale.append('computed')
                if not stale:
                    acceptance = check_geotiff(directory / 'image.tif', target / 'image_georef.tif', transform)
                    if record.get('acceptance') != acceptance:
                        raise ValueError('Odbiór GeoTIFF niezgodny z manifestem')
                else:
                    # Odczyt starego TIFF-a wobec jego własnego zdekodowanego obrazu.
                    acceptance = check_geotiff(target / 'image_georef.tif', target / 'image_georef.tif', transform)
                    if acceptance != record.get('acceptance'):
                        raise ValueError('Uszkodzony stary GeoTIFF lub dowód odbioru')
                states[plan_id] = 'stale' if stale else 'current'
                if stale:
                    problem(plan_id, 'result.stale', stale)
            except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
                states[plan_id] = 'corrupt'
                problem(plan_id, 'result.corrupt', str(exc))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        states = dict.fromkeys(plans, 'missing' if isinstance(exc, FileNotFoundError) else 'corrupt')
        problem('__run__', 'result.missing' if isinstance(exc, FileNotFoundError) else 'result.corrupt', str(exc))
    return states, problems
