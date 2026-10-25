"""T03: błędne wejścia nie mogą nadpisywać istniejących artefaktów."""
import copy
import csv
import hashlib
import importlib.util
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from gps_kataster_coordinates import GpsKatasterIndex, load_best_measurements
from test_gps_kataster_coordinates import row

spec = importlib.util.spec_from_file_location('t03_generator', ROOT / 'pipeline/02_generate_geotiff.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class CatalogueValidationTest(unittest.TestCase):
    def test_duplicates_are_rejected_before_category_filtering_in_every_order(self):
        for category in ('jaskinia_otwor', 'sztolnia', 'ponor'):
            for rows in itertools.permutations([row('O1'), row('O1', category=category)]):
                with self.subTest(category=category, rows=rows):
                    with self.assertRaisesRegex(ValueError, 'O1.*object_id'):
                        GpsKatasterIndex(list(rows))

    def test_invalid_unlinked_coordinates_are_rejected_in_every_order(self):
        for field, values in [('lat', [float('nan'), float('inf'), -91, 91, True]),
                              ('lon', [float('-inf'), -181, 181])]:
            for value in values:
                bad = row('BAD', category='ponor', **{field: value})
                for rows in itertools.permutations([row('O1'), bad]):
                    with self.subTest(field=field, value=value):
                        with self.assertRaisesRegex(ValueError, 'BAD.*' + field):
                            GpsKatasterIndex(list(rows))

    def test_csv_and_geojson_reject_invalid_numeric_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            for field in ('lat', 'lon', 'x_1992', 'y_1992', 'elevation_m',
                          'horizontal_accuracy_m', 'vertical_accuracy_m'):
                for value in ('NaN', 'Inf', 'broken'):
                    data = dict(object_id='BAD', category='ponor', lat=49, lon=19)
                    data[field] = value
                    for suffix in ('csv', 'geojson'):
                        path = Path(tmp) / ('catalogue.' + suffix)
                        if suffix == 'csv':
                            with path.open('w', newline='') as stream:
                                writer = csv.DictWriter(stream, fieldnames=data)
                                writer.writeheader()
                                writer.writerow(data)
                        else:
                            path.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
                                {'properties': data, 'geometry': {'type': 'Point', 'coordinates': [19, 49]}}]}))
                        with self.subTest(field=field, value=value, suffix=suffix):
                            with self.assertRaisesRegex(ValueError, 'BAD.*' + field):
                                load_best_measurements(path)

    def test_catalogue_requires_text_ids_and_categories(self):
        from dataclasses import replace
        for field, value in [('object_id', True), ('object_id', 1), ('category', None)]:
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    GpsKatasterIndex([replace(row('O1'), **{field: value})])

    def test_other_categories_are_allowed_but_cannot_be_selected(self):
        index = GpsKatasterIndex([row('O1'), row('OTHER', category='ponor')])
        self.assertEqual(list(index.by_object_id), ['O1'])


class PlanValidationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cave = self.root / 'plan'
        self.cave.mkdir()
        Image.new('1', (8, 6)).save(self.cave / 'image.tif')
        self.meta = {
            'cave': {'dir_id': 'plan', 'name': 'Plan'},
            'image': {'filename': 'image_1_zoom_10.tif', 'image_id': 1, 'width': 8, 'height': 6},
            'coordinates': {'gps_kataster_object_id': 'O1',
                            'lat': '{{ gps_kataster.objects[gps_kataster_object_id].lat }}',
                            'lon': '{{ gps_kataster.objects[gps_kataster_object_id].lon }}'},
            'entrance': {'x': 2.0, 'y': 3.0}, 'scale': {'pixels_per_meter': 2.0},
            'north': {'angle_deg': 0.0}, 'declination_deg': 0.0}
        self._valid = copy.deepcopy(self.meta)
        self.registry = {'schema_version': 1, 'plans': {'plan': {
            **self.meta['image'], 'sha256': hashlib.sha256((self.cave / 'image.tif').read_bytes()).hexdigest()}}}
        self.index = GpsKatasterIndex([row('O1'), row('O2', lat=50)])
        self.save()
        for name in ('image.tfw', 'image_georef.tif'):
            (self.cave / name).write_bytes(('previous ' + name).encode())

    def save(self):
        (self.cave / 'meta.yaml').write_text(yaml.safe_dump(self.meta, allow_unicode=True))

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.cave.iterdir()}

    def reject(self, field):
        self.save()
        before = self.snapshot()
        ok, message = generator.process_cave(self.cave, self.index, image_registry=self.registry)
        self.assertFalse(ok, message)
        self.assertIn('plan', message)
        self.assertIn(field, message)
        self.assertEqual(self.snapshot(), before)

    def test_rejects_nonfinite_numbers_in_required_and_optional_fields(self):
        for section, field in [('scale', 'pixels_per_meter'), ('entrance', 'x'),
                               ('entrance', 'y'), ('north', 'angle_deg'), ('computed', 'A'),
                               ('quality', 'ppm_cv')]:
            for number in (float('nan'), float('inf'), float('-inf')):
                with self.subTest(section=section, number=number):
                    self.meta.setdefault(section, {})[field] = number
                    self.reject(section + '.' + field)
                    del self.meta[section][field]
                    self.meta = copy.deepcopy(self.valid_meta)

    @property
    def valid_meta(self):
        # Odczyt niezmienionej kopii fixture zamiast produkcyjnego normalizatora.
        return self._valid

    def test_rejects_zero_negative_boolean_and_string_scale(self):
        for number in (0, -2, True, '2'):
            self.meta['scale']['pixels_per_meter'] = number
            self.reject('scale.pixels_per_meter')

    def test_rejects_missing_fields_and_wrong_structural_types(self):
        original = copy.deepcopy(self.meta)
        for section, field in [('image', 'width'), ('image', 'height'), ('image', 'filename'),
                               ('image', 'image_id'), ('coordinates', 'gps_kataster_object_id'),
                               ('coordinates', 'lat'), ('entrance', 'x'), ('north', 'angle_deg')]:
            self.meta = copy.deepcopy(original)
            del self.meta[section][field]
            self.reject(section + '.' + field)
        for section in ('image', 'coordinates', 'scale', 'cave'):
            self.meta = copy.deepcopy(original)
            self.meta[section] = []
            self.reject(section)

    def test_rejects_clicks_outside_image_but_accepts_edge_centres(self):
        from validation import validate_plan
        for x, y in ((-0.1, 3), (8, 3), (2, -1), (2, 6)):
            self.meta['entrance'] = dict(x=x, y=y)
            self.reject('entrance.')
        self.meta['entrance'] = dict(x=0, y=5)
        self.save()
        source, resolved = validate_plan(self.cave, self.index, self.registry)
        self.assertEqual(resolved['entrance'], dict(x=0, y=5))

    def test_rejects_conflicting_numeric_coordinates_and_other_templates(self):
        for field, value in [('lat', 50), ('lat', 91), ('lon', 181), ('lon', float('nan')),
                             ('lat', True), ('lon', '19'),
                             ('lat', '{{ gps_kataster.objects["O2"].lat }}'),
                             ('lon', '{{ 19 }}')]:
            original = self.meta['coordinates'][field]
            self.meta['coordinates'][field] = value
            self.reject('coordinates.' + field)
            self.meta['coordinates'][field] = original

    def test_uses_catalogue_numbers_for_agreeing_numeric_or_canonical_coordinates(self):
        from validation import validate_plan
        self.meta['coordinates']['lat'] = 49.0
        self.meta['coordinates']['lon'] = 19.0
        self.save()
        source, resolved = validate_plan(self.cave, self.index, self.registry)
        self.assertEqual(resolved['coordinates']['lat'], 49.0)
        self.assertIsInstance(resolved['coordinates']['lat'], float)
        self.assertEqual(source, self.meta)

    def test_rejects_unknown_id_and_legacy_nested_id(self):
        self.meta['coordinates']['gps_kataster_object_id'] = 'UNKNOWN'
        self.reject('coordinates.gps_kataster_object_id')
        self.meta['coordinates'].pop('gps_kataster_object_id')
        self.meta['coordinates']['gps_kataster'] = {'object_id': 'O1'}
        self.reject('coordinates.gps_kataster_object_id')

    def test_rejects_missing_corrupt_or_incompatible_image(self):
        image = self.cave / 'image.tif'
        for kind in ('missing', 'corrupt', 'dimensions', 'mode'):
            if kind == 'missing': image.unlink()
            elif kind == 'corrupt': image.write_bytes(b'not a TIFF')
            else: Image.new('L' if kind == 'mode' else '1', (9, 6) if kind == 'dimensions' else (8, 6)).save(image)
            self.reject('image')

    def test_detects_replacement_image_with_unchanged_dimensions(self):
        Image.new('1', (8, 6), 1).save(self.cave / 'image.tif')
        self.reject('image.sha256')

    def test_rejects_wrong_image_identity_and_missing_registry_entry(self):
        for field, value in [('image_id', 2), ('filename', 'image_2_zoom_10.tif')]:
            original = self.meta['image'][field]
            self.meta['image'][field] = value
            self.reject('image.' + field)
            self.meta['image'][field] = original
        self.registry['plans'].clear()
        self.reject('image')

    def test_rejects_wrong_plan_id_and_schema_version(self):
        self.meta['cave']['dir_id'] = 'another-plan'
        self.reject('cave.dir_id')
        self.meta['cave']['dir_id'] = 'plan'
        self.registry['schema_version'] = 99
        self.reject('schema_version')

    def test_yaml_errors_and_duplicate_keys_are_reported_without_writes(self):
        for text in ('image: [', 'image: {}\nimage: {}\n', '[]'):
            (self.cave / 'meta.yaml').write_text(text)
            before = self.snapshot()
            ok, message = generator.process_cave(self.cave, self.index, image_registry=self.registry)
            self.assertFalse(ok)
            self.assertIn('plan', message)
            self.assertEqual(self.snapshot(), before)

    def test_current_catalogue_validates_without_touching_historical_artifacts(self):
        from coordinate_source import verify
        from validation import validate_plan
        index = load_best_measurements(verify())
        before = hashlib.sha256((ROOT / 'data/baseline/2026-10-24/catalogue.json').read_bytes()).hexdigest()
        for path in sorted((ROOT / 'data/caves').glob('*/meta.yaml')):
            with self.subTest(plan=path.parent.name):
                validate_plan(path.parent, index)
        self.assertEqual(hashlib.sha256((ROOT / 'data/baseline/2026-10-24/catalogue.json').read_bytes()).hexdigest(), before)

    def test_cli_rejects_unpinned_csv_before_writing(self):
        csv_path = self.root / 'arbitrary.csv'
        csv_path.write_text('object_id,category,lat,lon\nO1,jaskinia_otwor,49,19\n')
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(ROOT / 'pipeline/02_generate_geotiff.py'),
                                 '--all', '--data-dir', str(self.root),
                                 '--gps-kataster-best-measurements', str(csv_path)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SHA-256', result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_cli_validates_whole_batch_before_first_write_without_strict_flag(self):
        # Poprawny plan pierwszy, błędny drugi: żaden artefakt nie może się zmienić.
        import shutil
        from coordinate_source import verify
        self.meta['coordinates']['gps_kataster_object_id'] = 'KSZ-0033'
        self.save()
        second = self.root / 'zzz'
        shutil.copytree(self.cave, second)
        other_meta = copy.deepcopy(self.meta)
        other_meta['cave']['dir_id'] = 'zzz'
        other_meta['scale']['pixels_per_meter'] = 0
        (second / 'meta.yaml').write_text(yaml.safe_dump(other_meta))
        self.registry['plans']['zzz'] = self.registry['plans']['plan']
        registry = self.root / 'registry.json'
        registry.write_text(json.dumps(self.registry))
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, str(ROOT / 'pipeline/02_generate_geotiff.py'),
                                 '--all', '--data-dir', str(self.root), '--image-registry', str(registry)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('zzz: scale.pixels_per_meter', result.stderr)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, before)

    def test_changed_plan_does_not_skip_validation_and_preserves_outputs(self):
        import os
        self.meta['scale']['pixels_per_meter'] = -1
        self.save()
        self.meta['coordinates']['gps_kataster_object_id'] = 'KSZ-0033'
        self.save()
        os.utime(self.cave / 'image.tfw', (1, 1))
        registry = self.root / 'registry.json'
        registry.write_text(json.dumps(self.registry))
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(ROOT / 'pipeline/02_generate_geotiff.py'),
                                 '--changed', '--data-dir', str(self.root), '--image-registry', str(registry)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('scale.pixels_per_meter', result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_errors_identify_plan_field_and_rule_instead_of_crashing(self):
        for field, value in [('width', True), ('height', 0), ('width', '8')]:
            original = self.meta['image'][field]
            self.meta['image'][field] = value
            self.reject('image.' + field)
            self.meta['image'][field] = original
        self.meta['scale']['pixels_per_meter'] = 1e-320
        self.reject('coordinates/scale')

    def test_optional_known_fields_require_their_declared_types(self):
        for section, field, value in [('computed', 'A', 'NaN'), ('computed', 'C', True),
                                     ('quality', 'ppm_cv', '1'), ('north', 'all_skipped', 0)]:
            self.meta.setdefault(section, {})[field] = value
            self.reject(section + '.' + field)
            self.meta = copy.deepcopy(self._valid)

    def test_cyclic_yaml_and_nonstandard_collections_are_rejected_with_diagnostics(self):
        for extra in ({float('inf')}, {float('nan'): None}):
            self.meta['extra'] = extra
            self.reject('extra')
        self.meta['extra'] = []
        self.meta['extra'].append(self.meta['extra'])
        self.reject('extra')

    def test_malformed_registry_is_reported_as_an_image_error(self):
        original = copy.deepcopy(self.registry)
        for registry in ([], {'schema_version': 1, 'plans': []},
                         {**original, 'schema_version': True}):
            self.registry = registry
            self.reject('image')
