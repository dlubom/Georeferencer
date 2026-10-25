"""Odbiór kompletności, aktualności i numeryki raportu 814 planów T06."""
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

import yaml

from test_orientation import ROOT, generator
from test_geometry import PROJECT, tfw_tolerance
from gps_kataster_coordinates import load_best_measurements
from geometry_impact import BEFORE_COMMIT, BEFORE_SHA256, compare_plan, load_generator


class GeometryImpactTest(unittest.TestCase):
    def test_report_distinguishes_historical_compatibility_from_geometry_verification(self):
        from orientation import default_context
        report = json.loads((ROOT / 'docs/reports/t06-geometry-impact.json').read_text())
        context = default_context()
        self.assertEqual(report['history_archive_sha256'], context['hashes'][str(ROOT / 'data/history/t02-inputs.zip')])
        for plan in report['plans']:
            with self.subTest(plan=plan['dir_id']):
                historical = context['plans'][plan['dir_id']]['historical_tfw']['parameters']
                comparison = plan['historical_compatibility']
                self.assertEqual(comparison['tfw_rotation_deg'], math.degrees(math.atan2(historical['D'], historical['A'])))
                self.assertLessEqual(abs(comparison['delta_deg']), 1e-11)
                self.assertFalse(comparison['source_metadata_verified'])

    def test_report_covers_all_inputs_and_separates_position_orientation_scale(self):
        report = json.loads((ROOT / 'docs/reports/t06-geometry-impact.json').read_text())
        index = load_best_measurements(ROOT / 'data/coordinate-source/best-measurements-v1.3.1.csv')
        paths = sorted((ROOT / 'data/caves').glob('*/meta.yaml'))
        self.assertEqual([p['dir_id'] for p in report['plans']], [p.parent.name for p in paths])
        self.assertEqual(report['plan_count'], 814)
        self.assertEqual(report['changed_tfw_count'], 814)
        self.assertEqual(report['before_commit'], BEFORE_COMMIT)
        self.assertEqual(report['before_generator_sha256'], BEFORE_SHA256)
        for name, digest in report['after_implementation_sha256'].items():
            self.assertEqual(digest, hashlib.sha256((ROOT / 'pipeline' / name).read_bytes()).hexdigest())
        for path, item in zip(paths, report['plans']):
            with self.subTest(plan=path.parent.name):
                raw = path.read_bytes()
                meta = yaml.safe_load(raw)
                row = index.by_object_id[meta['coordinates']['gps_kataster_object_id']]
                meta['coordinates'].update(lat=row.lat, lon=row.lon)
                self.assertEqual(item['meta_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(item['image_sha256'], meta['orientation']['image_sha256'])
                self.assertEqual(item['object_id'], row.object_id)
                current = generator.compute_world_file(meta)
                for key, value in item['after_tfw'].items():
                    self.assertEqual(value, float(f'{current[key]:.{10 if key in "ADBE" else 6}f}'))
                self.assertEqual(compare_plan(meta, item['before_tfw'], item['after_tfw']),
                                 {key: item[key] for key in ('position', 'orientation', 'scale')})
                self.assertEqual(item['orientation']['reference'], 'unknown')
                self.assertEqual(item['orientation']['status'], 'unverified')
                self.assertEqual(item['orientation']['delta_deg'], 0)
                self.assertEqual(item['scale']['delta_m_per_pixel'], 0)
                x, y = meta['entrance']['x'], meta['entrance']['y']
                target = PROJECT.transform(row.lon, row.lat)
                before, after = item['before_tfw'], item['after_tfw']
                # Stary generator kotwiczył indeks środka (x,y), T06 narożnik UI.
                old_centre = (before['A']*x+before['B']*y+before['C'],
                              before['D']*x+before['E']*y+before['F'])
                for old, new, expected in zip(old_centre, item['position']['after_m'], target):
                    self.assertLessEqual(abs(old-expected), .5e-6+(abs(x)+abs(y))*.5e-10+2e-9)
                    self.assertLessEqual(abs(new-expected), tfw_tolerance(x,y))
                for key in ('A', 'D', 'B', 'E'):
                    self.assertEqual(before[key], after[key])
                # Półpiksel jest jedyną zmianą C,F (maks. 1 µm różnicy zaokrągleń).
                self.assertLessEqual(abs(after['C']-before['C']-.5*(after['A']+after['B'])), 1.002e-6)
                self.assertLessEqual(abs(after['F']-before['F']-.5*(after['D']+after['E'])), 1.002e-6)
        for field, path in [('coordinate_source_sha256', 'data/coordinate-source/best-measurements-v1.3.1.csv'),
                            ('pin_sha256', 'data/coordinate-source/source.json'),
                            ('image_registry_sha256', 'data/validation/images-v1.json'),
                            ('history_sha256', 'data/baseline/2026-10-24/catalogue.json')]:
            self.assertEqual(report[field], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())

    def test_before_generator_is_verified_before_any_code_is_executed(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'before.py'
            source.write_text('raise RuntimeError("ten kod nie może być uruchomiony")')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                load_generator(source, BEFORE_SHA256)
