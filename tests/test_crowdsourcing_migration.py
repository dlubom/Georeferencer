"""T07: odbiór selektywnej migracji, bez cofania ręcznych korekt."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))


class CrowdsourcingMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from migrate_crowdsourcing import migration
        cls.report, cls.writes = migration()

    def test_real_mrozna_drops_test_spread_but_preserves_manual_north(self):
        meta = yaml.safe_load((ROOT / 'data/caves/001094/meta.yaml').read_text())
        self.assertEqual(meta['cave']['n_submissions'], 5)
        self.assertEqual(meta['quality']['entrance_std_px'], 1.16)
        self.assertEqual(meta['entrance'], {'x': 20694.01, 'y': 1732.56})
        self.assertEqual(meta['scale']['pixels_per_meter'], 59.03)
        self.assertEqual(meta['north']['angle_deg'], 50.0)
        self.assertEqual(meta['coordinates']['gps_kataster_object_id'], 'KSW-0081')
        self.assertEqual(meta['north']['reference'], 'unknown')
        self.assertEqual(meta['orientation']['status'], 'unverified')

    def test_report_reproduces_and_only_declared_fields_change(self):
        from migrate_crowdsourcing import REPORT
        report, writes = self.report, self.writes
        self.assertEqual(report, json.loads(REPORT.read_text()))
        self.assertEqual(report['historical_groups'], 801)
        self.assertEqual(report['minimum_non_test_users'], 5)
        self.assertEqual(report['test_affected_plans'], ['001094', '001095', '001103', '001445'])
        self.assertEqual(len(report['manual_plans_unchanged']), 13)
        for path, raw in writes:
            self.assertEqual(path.read_bytes(), raw)
        for plan in report['plans']:
            self.assertEqual(plan['geometry']['orientation']['delta_deg'], 0.0)
            self.assertEqual(plan['after']['coordinates'], plan['before']['coordinates'])
            self.assertEqual(plan['after']['computed'], plan['before']['computed'])
            self.assertEqual(plan['after']['declination_deg'], plan['before']['declination_deg'])
            self.assertEqual(plan['after']['declination'], plan['before']['declination'])
            self.assertEqual(plan['after']['orientation']['historical'], plan['before']['orientation']['historical'])

    def test_unexplained_component_edit_is_preserved_and_reported(self):
        from migrate_crowdsourcing import reconcile_plan
        before = yaml.safe_load((ROOT / 'data/caves/001094/meta.yaml').read_text())
        before['entrance'] = {'x': 100.123456789, 'y': 200.0}
        legacy = copy.deepcopy(before)
        legacy['entrance'] = {'x': 10.0, 'y': 20.0}
        candidate = {'count': 5, 'excluded_submission_ids': ['TEST'],
                     'entrance': {'x': 11.0, 'y': 21.0}, 'scale': before['scale'],
                     'quality': before['quality'], 'north': {'angle_deg': 50.002, 'all_skipped': False},
                     'components': {'north': {'observations': 3}}}
        after, preserved = reconcile_plan(before, legacy, candidate, north_affected=False)
        self.assertEqual(after['entrance'], before['entrance'])
        item = next(x for x in preserved if x['component'] == 'entrance')
        self.assertEqual(item['status'], 'requires_decision')

    def test_later_edit_is_rejected_before_any_migration_write(self):
        from migrate_crowdsourcing import migration
        from orientation import load_context
        from migrate_north import migrated_bytes
        context = load_context()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for plan_id, plan in context['plans'].items():
                path = root / f'data/caves/{plan_id}/meta.yaml'
                path.parent.mkdir(parents=True)
                path.write_bytes(migrated_bytes(context['originals'][plan_id], plan))
            victim = root / 'data/caves/001095/meta.yaml'
            victim.write_bytes(victim.read_bytes() + b'\n# Pozniejsza edycja operatora\n')
            hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('data/caves/*/meta.yaml')}
            with self.assertRaisesRegex(ValueError, '001095.*edycj'):
                migration(root)
            self.assertEqual(hashes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in hashes})

    def test_incomplete_north_never_becomes_measured_zero(self):
        report = self.report
        for plan_id in ('004068', '001050'):
            item = next(p for p in report['plans'] if p['dir_id'] == plan_id)
            self.assertIsNone(item['aggregate']['north']['angle_deg'])
            self.assertEqual(item['after']['north']['angle_origin'], 'unknown')
            self.assertEqual(item['aggregate']['components']['north']['observations'], 0)

    def test_north_changes_require_reasoned_image_bound_decision(self):
        from orientation import validate_orientation
        report = self.report
        changed = [p for p in report['plans'] if p['before']['north'] != p['after']['north']]
        self.assertGreater(len(changed), 0)
        for item in changed:
            after = item['after']
            validate_orientation(after)
            decision = after['orientation']['decisions'][-1]
            self.assertIn(after['orientation']['image_sha256'], decision['reason'])
            self.assertEqual(decision['action'], 'preserve_historical')
            bad = copy.deepcopy(after)
            bad['orientation']['decisions'] = []
            with self.assertRaisesRegex(ValueError, 'decyzj'):
                validate_orientation(bad)
