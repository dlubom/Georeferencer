"""Bieżące modele orientacji i zachowanie kąta nieustalonej północy."""
import copy
import importlib.util
import math
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from gps_kataster_coordinates import load_best_measurements
from validation import validate_meta

spec = importlib.util.spec_from_file_location('t05_generator', ROOT / 'pipeline/02_generate_geotiff.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def resolved(plan='001131'):
    meta = yaml.safe_load((ROOT / 'data/caves' / plan / 'meta.yaml').read_text())
    row = load_best_measurements(ROOT / 'data/coordinate-source/best-measurements-v1.3.1.csv').by_object_id[
        meta['coordinates']['gps_kataster_object_id']]
    meta['coordinates'].update(lat=row.lat, lon=row.lon)
    return meta


def angle(params):
    return math.degrees(math.atan2(params['D'], params['A']))


class OrientationTest(unittest.TestCase):
    def test_coordinates_scale_and_click_change_without_recomputing_orientation(self):
        meta = resolved()
        old = generator.compute_world_file(meta)
        meta['coordinates'].update(lat=50.0, lon=22.0)
        meta['scale']['pixels_per_meter'] *= 2
        meta['entrance'].update(x=300, y=400)
        new = generator.compute_world_file(meta)
        self.assertAlmostEqual(angle(old), angle(new), places=12)
        self.assertAlmostEqual(math.hypot(new['A'], new['D']), math.hypot(old['A'], old['D']) / 2)
        expected = generator.TRANSFORMER.transform(22.0, 50.0)
        self.assertAlmostEqual(new['A'] * 299.5 + new['B'] * 399.5 + new['C'], expected[0])
        self.assertAlmostEqual(new['D'] * 299.5 + new['E'] * 399.5 + new['F'], expected[1])

    def test_missing_orientation_metadata_is_an_error(self):
        meta = resolved()
        meta.pop('orientation', None)
        with self.assertRaisesRegex(ValueError, 'orientation'):
            generator.compute_world_file(meta)

    def test_established_north_and_declination_require_sources(self):
        meta = resolved()
        meta['north'].update(reference='geographic', angle_origin='measured')
        meta['north'].pop('evidence', None)
        with self.assertRaisesRegex(ValueError, 'north.evidence'):
            validate_meta(meta, '001131')
        meta['north'].update(reference='magnetic', evidence='Legenda planu')
        meta['declination'] = {'status': 'documented', 'sign_convention': 'east_positive', 'basis': 'WMM'}
        with self.assertRaisesRegex(ValueError, 'declination.epoch'):
            validate_meta(meta, '001131')

    def test_measured_zero_is_distinct_from_assumed_zero(self):
        results = []
        for origin in ('measured', 'assumed'):
            meta = resolved()
            meta['north'].update(angle_deg=0.0, angle_origin=origin,
                                  evidence='Opis pomiaru strzałki' if origin == 'measured' else 'Jawne przyjęcie operatora')
            validate_meta(meta, '001131')
            results.append(generator.compute_world_file(meta))
            self.assertEqual(meta['north']['angle_origin'], origin)
        self.assertAlmostEqual(angle(results[0]), angle(results[1]))

    def test_explicit_reference_transition_keeps_sources_and_unverified_status_with_model(self):
        from orientation import validate_orientation
        for reference in ('geographic', 'magnetic', 'grid'):
            with self.subTest(reference=reference):
                meta = resolved()
                historical = copy.deepcopy(meta['orientation']['historical'])
                meta['orientation']['mode'] = 'reference'
                meta['north'].update(reference=reference, angle_origin='measured', evidence='Legenda planu, strona 1: rodzaj północy')
                meta['declination'] = {'status': 'documented', 'sign_convention': 'east_positive',
                                       'basis': 'Odczyt wartości z legendy planu', 'epoch': '1980.0'}
                validate_meta(meta, '001131')
                validate_orientation(meta)
                self.assertEqual(meta['orientation']['historical'], historical)
                self.assertEqual(meta['orientation']['status'], 'unverified')
                self.assertTrue(all(math.isfinite(v) for v in generator.compute_world_file(meta).values()))
                summary = generator.orientation.summary(meta)
                self.assertEqual(summary['north']['evidence'], meta['north']['evidence'])
                self.assertEqual(summary['declination'], meta['declination'])

    def test_declination_requires_value_sign_and_basis_including_negative_values(self):
        for value in (-4.0, 0.0, 4.0):
            meta = resolved()
            meta['declination_deg'] = value
            meta['declination'] = {'status': 'documented', 'sign_convention': 'east_positive',
                                   'basis': 'Zapis na planie', 'epoch': '2000.0'}
            validate_meta(meta, '001131')
            for field in ('sign_convention', 'basis'):
                bad = copy.deepcopy(meta)
                del bad['declination'][field]
                with self.subTest(value=value, missing=field):
                    with self.assertRaisesRegex(ValueError, 'declination.' + field):
                        validate_meta(bad, '001131')
        del meta['declination_deg']
        with self.assertRaisesRegex(ValueError, 'declination_deg'):
            validate_meta(meta, '001131')

    def test_qa_exposes_status_and_uncertainty_reason(self):
        import csv
        import tempfile
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('t05_report', ROOT / 'pipeline/03_report.py')
        report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(report)
        meta = resolved()
        meta.update(_has_tif=True, _has_tfw=True, _has_georef=False)
        with tempfile.TemporaryDirectory() as tmp, patch.object(report, 'REPORTS_DIR', Path(tmp)):
            report.write_summary([meta])
            with (Path(tmp) / 'summary.csv').open() as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row['orientation_status'], 'unverified')
            self.assertEqual(row['north_reference'], 'unknown')
            self.assertEqual(row['orientation_uncertainty_reason'], meta['orientation']['uncertainty_reason'])
