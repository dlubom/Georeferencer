"""T05: oraklem zgodności są zapisane TFW T02, nigdy computed/stary wzór."""
import copy
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
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


def catalogue():
    return json.loads((ROOT / 'data/baseline/2026-10-24/catalogue.json').read_text())


def historical_t05_inputs():
    """Wejścia historycznego T06: dokładna migracja zweryfikowanych YAML-i T02."""
    from migrate_north import migrated_bytes
    from orientation import load_context
    context = load_context()
    return {plan_id: migrated_bytes(context['originals'][plan_id], plan)
            for plan_id, plan in context['plans'].items()}


def resolved(plan='001131'):
    meta = yaml.safe_load((ROOT / 'data/caves' / plan / 'meta.yaml').read_text())
    row = load_best_measurements(ROOT / 'data/coordinate-source/best-measurements-v1.3.1.csv').by_object_id[
        meta['coordinates']['gps_kataster_object_id']]
    meta['coordinates'].update(lat=row.lat, lon=row.lon)
    return meta


def angle(params):
    return math.degrees(math.atan2(params['D'], params['A']))


class OrientationTest(unittest.TestCase):
    def test_all_migrated_plans_keep_angle_from_saved_tfw(self):
        index = load_best_measurements(ROOT / 'data/coordinate-source/best-measurements-v1.3.1.csv')
        for plan in catalogue()['plans']:
            with self.subTest(plan=plan['dir_id']):
                meta = yaml.safe_load((ROOT / 'data/caves' / plan['dir_id'] / 'meta.yaml').read_text())
                row = index.by_object_id[meta['coordinates']['gps_kataster_object_id']]
                meta['coordinates'].update(lat=row.lat, lon=row.lon)
                expected = angle(plan['historical_tfw']['parameters'])
                self.assertAlmostEqual(angle(generator.compute_world_file(meta)), expected, places=11)
                self.assertEqual(meta['north']['reference'], 'unknown')
                self.assertEqual(meta['orientation']['status'], 'unverified')

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

    def test_orientation_changes_need_explicit_reasoned_decision(self):
        for section, field, value in [('north', 'angle_deg', 15.0),
                                      ('north', 'all_skipped', True),
                                      (None, 'declination_deg', 4.0)]:
            with self.subTest(field=field):
                meta = resolved()
                (meta if section is None else meta[section])[field] = value
                with self.assertRaisesRegex(ValueError, 'decyzj'):
                    generator.compute_world_file(meta)

    def test_known_reference_never_falls_back_to_legacy_formula(self):
        for reference in ('geographic', 'magnetic', 'grid'):
            meta = resolved()
            meta['north'].update(reference=reference, angle_origin='measured', evidence='Legenda planu, strzałka N')
            meta['declination'] = {'status': 'documented', 'sign_convention': 'east_positive',
                                   'basis': 'Wartość opisana na planie', 'epoch': '1980.0'}
            # Bez decyzji też musi nastąpić błąd, nigdy zastępczy stary wzór.
            with self.subTest(reference=reference):
                with self.assertRaises(ValueError):
                    generator.compute_world_file(meta)

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
        from orientation import record_decision
        results = []
        for origin in ('measured', 'assumed'):
            meta = resolved()
            meta['north'].update(angle_deg=0.0, angle_origin=origin,
                                  evidence='Opis pomiaru strzałki' if origin == 'measured' else 'Jawne przyjęcie operatora')
            meta = record_decision(meta, 'Rozróżnienie pochodzenia zera w próbie.', '2026-10-25')
            validate_meta(meta, '001131')
            results.append(generator.compute_world_file(meta))
            self.assertEqual(meta['north']['angle_origin'], origin)
        self.assertAlmostEqual(angle(results[0]), angle(results[1]))

    def test_explicit_reference_transition_keeps_sources_and_unverified_status_with_model(self):
        from orientation import record_decision, validate_orientation
        for reference in ('geographic', 'magnetic', 'grid'):
            with self.subTest(reference=reference):
                meta = resolved()
                historical = copy.deepcopy(meta['orientation']['historical'])
                meta['north'].update(reference=reference, angle_origin='measured', evidence='Legenda planu, strona 1: rodzaj północy')
                meta['declination'] = {'status': 'documented', 'sign_convention': 'east_positive',
                                       'basis': 'Odczyt wartości z legendy planu', 'epoch': '1980.0'}
                meta = record_decision(meta, 'Jawne ustalenie rodzaju północy na podstawie syntetycznej legendy.', '2026-10-25')
                validate_meta(meta, '001131')
                validate_orientation(meta)
                self.assertEqual(meta['orientation']['historical'], historical)
                self.assertEqual(meta['orientation']['status'], 'unverified')
                self.assertTrue(all(math.isfinite(v) for v in generator.compute_world_file(meta).values()))
                summary = generator.orientation.summary(meta)
                self.assertEqual(summary['north']['evidence'], meta['north']['evidence'])
                self.assertEqual(summary['declination'], meta['declination'])

    def test_decision_cannot_refresh_reference_or_self_verify(self):
        from orientation import record_decision
        for field, value in [('catalogue_sha256', '0' * 64), ('plan_id', '001132'), ('tfw_sha256', '0' * 64)]:
            meta = resolved()
            meta['north']['angle_deg'] += 1
            meta['orientation']['historical'][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, 'odniesienia T02'):
                    record_decision(meta, 'Próba zmiany odniesienia', '2026-10-25')
        meta = resolved()
        meta['orientation']['status'] = 'verified'
        with self.assertRaisesRegex(ValueError, 'orientation.status'):
            generator.compute_world_file(meta)

    def test_decision_requires_reason_date_and_continuous_hash_chain(self):
        from orientation import record_decision
        meta = resolved()
        meta['north']['angle_deg'] += 1
        for reason, decision_date in [('', '2026-10-25'), ('Powód', 'wczoraj')]:
            with self.subTest(reason=reason):
                with self.assertRaises(ValueError):
                    record_decision(meta, reason, decision_date)
        accepted = record_decision(meta, 'Zachowujemy TFW pomimo zmiany opisu.', '2026-10-25')
        self.assertAlmostEqual(angle(generator.compute_world_file(accepted)),
                               angle(generator.compute_world_file(resolved())))
        accepted['orientation']['decisions'][0]['before_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'łańcuch'):
            generator.compute_world_file(accepted)

    def test_declination_requires_value_sign_and_basis_including_negative_values(self):
        from orientation import record_decision
        for value in (-4.0, 0.0, 4.0):
            meta = resolved()
            meta['declination_deg'] = value
            meta['declination'] = {'status': 'documented', 'sign_convention': 'east_positive',
                                   'basis': 'Zapis na planie', 'epoch': '2000.0'}
            meta = record_decision(meta, 'Udokumentowanie historycznej wartości bez zmiany orientacji.', '2026-10-25')
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

    def test_migration_report_is_reproducible_and_preserves_all_previous_fields(self):
        from migrate_north import migration
        from orientation import load_context
        originals = load_context()['originals']
        expected = json.loads((ROOT / 'data/migrations/t05-north.json').read_text())
        expected_plans = {plan['dir_id']: plan for plan in expected['plans']}
        historical = historical_t05_inputs()
        # Odbiór migracji odtwarza archiwum, nie wymaga cofania bieżących edycji.
        with tempfile.TemporaryDirectory() as tmp:
            for plan_id, raw in originals.items():
                path = Path(tmp) / 'data/caves' / plan_id / 'meta.yaml'
                path.parent.mkdir(parents=True)
                path.write_bytes(raw)
            report, writes = migration(tmp)
            self.assertEqual(report, expected)
            self.assertEqual(len(writes), 814)
            for path, raw in writes:
                plan_id = path.parent.name
                with self.subTest(plan=plan_id):
                    self.assertEqual(path.read_bytes(), originals[plan_id])
                    self.assertEqual(hashlib.sha256(originals[plan_id]).hexdigest(),
                                     expected_plans[plan_id]['before_sha256'])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_plans[plan_id]['after_sha256'])
                    self.assertEqual(raw, historical[plan_id])
                    after = yaml.safe_load(raw)
                    del after['north']['reference'], after['north']['angle_origin']
                    del after['declination'], after['orientation']
                    self.assertEqual(after, yaml.safe_load(originals[plan_id]))
                    path.write_bytes(raw)
            self.assertEqual(migration(tmp), (report, writes))

            # Późniejsza poprawna edycja YAML-a nie zmienia historii; migrator
            # nadal odmawia jej nadpisania, także gdy zmienia się tylko komentarz.
            path, raw = writes[0]
            edited = raw + b'\n# Later catalogue edit.\n'
            path.write_bytes(edited)
            self.assertEqual(historical_t05_inputs()[path.parent.name], raw)
            with self.assertRaisesRegex(ValueError, 'zmienione wejście'):
                migration(tmp)
            self.assertEqual(path.read_bytes(), edited)

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
