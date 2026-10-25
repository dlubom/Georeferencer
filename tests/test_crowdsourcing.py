"""T07: kwalifikacja źródeł, niezależni użytkownicy i kompletne pomiary."""
import copy
import itertools
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
import crowdsourcing as core


def row(number=1, user=None, angle=0.0, **changes):
    value = {
        'submission_id': f'SUB_{number}', 'user_id': user or f'user-{number}',
        'cave_id': 'T.X-01.01', 'submit_type': 'NORMAL', 'assignment_id': None,
        'image_id': 12, 'image_used_path': 'caves_mono/000123/image_12.tif',
        'points_orig_json': json.dumps([
            {'x': 10., 'y': 20.}, {'x': 0., 'y': 0.}, {'x': 10., 'y': 0.},
            {'x': 50., 'y': 50.},
            {'x': 50. + math.sin(math.radians(angle)),
             'y': 50. - math.cos(math.radians(angle))},
        ]),
        'pixels_per_meter': 10., 'skipNorth': False, 'north_deg': angle,
    }
    value.update(changes)
    return value


class CrowdsourcingTest(unittest.TestCase):
    def aggregate(self, rows, **kwargs):
        return core.aggregate_cave('T.X-01.01', pd.DataFrame(rows), classification={}, **kwargs)

    def test_mrozna_excludes_only_classified_ids_and_reproduces_scatter(self):
        subs = pd.read_parquet(ROOT / 'parquet/SUBMISSIONS.parquet')
        group = subs[subs.cave_id == 'T.D-08.07']
        old = core.aggregate_cave('T.D-08.07', group, classification={})
        corrected = core.aggregate_cave('T.D-08.07', group)
        self.assertEqual(old['quality']['entrance_std_px'], 7042.09)
        self.assertEqual(corrected['quality']['entrance_std_px'], 1.16)
        self.assertAlmostEqual(corrected['raw']['entrance_std_px'], 1.1586872257713097, places=12)
        self.assertEqual(corrected['entrance'], {'x': 20694.01, 'y': 1732.56})
        self.assertEqual(corrected['scale'], {'pixels_per_meter': 59.03})
        self.assertEqual(corrected['north']['angle_deg'], 50.002)
        self.assertEqual(corrected['count'], 5)
        self.assertEqual(corrected['users'], 5)
        self.assertEqual(corrected['components']['scale_before_iqr']['observations'], 5)
        self.assertEqual(corrected['components']['scale_after_iqr']['observations'], 3)
        self.assertEqual(corrected['quality']['outliers_removed'], 2)
        self.assertEqual(corrected['excluded_submission_ids'],
                         ['SUB_1769506147971_9732', 'SUB_1769509389437_7729'])

    def test_snapshot_preserves_every_group_and_five_real_users(self):
        subs = pd.read_parquet(ROOT / 'parquet/SUBMISSIONS.parquet')
        result = core.aggregate_catalogue(subs)
        self.assertEqual(len(result), 827)
        self.assertEqual(set(result), set(subs.cave_id))
        historical = {cid for cid, group in subs.groupby('cave_id') if len(group) >= 5}
        self.assertEqual(len(historical), 801)
        self.assertEqual({cid for cid, group in result.items() if group['eligible']}, historical)
        self.assertTrue(all(result[cid]['users'] >= 5 for cid in historical))
        self.assertEqual(sum(g['source_count'] for g in result.values()), 4048)
        self.assertEqual(sum(g['count'] for g in result.values()), 4041)
        self.assertEqual(sum(len(g['excluded_submission_ids']) for g in result.values()), 7)
        self.assertIsNone(result['T.B-04.04']['north']['angle_deg'])
        self.assertIsNone(result['T.C-13.04']['north']['angle_deg'])

    def test_registry_is_exact_id_list_with_verified_marker_evidence(self):
        registry = core.load_classification()
        self.assertEqual(len(registry), 7)
        subs = pd.read_parquet(ROOT / 'parquet/SUBMISSIONS.parquet').set_index('submission_id')
        self.assertEqual(set(registry), set(subs[subs['Unnamed: 52'].eq('TEST')].index))
        for sid, entry in registry.items():
            self.assertTrue(entry['reason'].strip())
            self.assertEqual(entry['classification'], 'TEST')
            self.assertEqual(entry['cave_id'], subs.loc[sid, 'cave_id'])
            self.assertEqual(entry['evidence'], {'column': 'Unnamed: 52', 'value': 'TEST'})

    def test_registry_rejects_missing_reason_duplicate_or_false_evidence(self):
        original = json.loads(core.DEFAULT_CLASSIFICATION.read_text())
        changed = []
        missing = copy.deepcopy(original)
        missing['exclusions'][0]['reason'] = ' '
        changed.append(missing)
        duplicate = copy.deepcopy(original)
        duplicate['exclusions'].append(duplicate['exclusions'][0])
        changed.append(duplicate)
        false = copy.deepcopy(original)
        false['exclusions'][0]['evidence']['value'] = 'NORMAL'
        changed.append(false)
        wrong_cave = copy.deepcopy(original)
        wrong_cave['exclusions'][0]['cave_id'] = 'T.X-01.01'
        changed.append(wrong_cave)
        wrong_hash = copy.deepcopy(original)
        wrong_hash['source']['sha256'] = '0' * 64
        changed.append(wrong_hash)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'registry.json'
            for registry in changed:
                with self.subTest(registry=registry):
                    path.write_text(json.dumps(registry))
                    with self.assertRaises(ValueError):
                        core.load_classification(path)

    def test_without_assignment_and_unclassified_test_marker_are_retained(self):
        rows = [row(1), row(2, assignment_id='missing'), row(3, **{'Unnamed: 52': 'TEST'})]
        result = core.aggregate_cave('T.X-01.01', pd.DataFrame(rows))
        self.assertEqual(result['count'], 3)
        self.assertEqual(result['excluded_submission_ids'], [])

    def test_permutation_cannot_change_aggregate_or_audit_order(self):
        rows = [row(3, angle=179.), row(1, angle=-179.), row(2, angle=178.)]
        expected = self.aggregate(rows)
        for permutation in itertools.permutations(rows):
            self.assertEqual(self.aggregate(permutation), expected)
        subs = pd.read_parquet(ROOT / 'parquet/SUBMISSIONS.parquet')
        group = subs[subs.cave_id == 'T.D-08.07']
        self.assertEqual(core.aggregate_cave('T.D-08.07', group),
                         core.aggregate_cave('T.D-08.07', group.sample(frac=1, random_state=7)))

    def test_circular_boundary_and_ambiguous_antipodes(self):
        for angles, expected in [([179., -179.], -180.), ([359., 1.], 0.),
                                 ([360., 0., -360.], 0.), ([178., -179., 179.], 179.)]:
            with self.subTest(angles=angles):
                north = self.aggregate([row(i + 1, angle=a) for i, a in enumerate(angles)])['north']
                self.assertEqual(north['angle_deg'], expected)
                self.assertFalse(north['ambiguous'])
        for angles in ([0., 180.], [0., 120., 240.]):
            north = self.aggregate([row(i + 1, angle=a) for i, a in enumerate(angles)])['north']
            self.assertIsNone(north['angle_deg'])
            self.assertTrue(north['ambiguous'])

    def test_component_counts_distinguish_rows_users_and_iqr(self):
        rows = [row(1, user='same'), row(2, user='same'), row(3), row(4),
                row(5, pixels_per_meter=100.)]
        result = self.aggregate(rows)
        self.assertEqual((result['count'], result['users']), (5, 4))
        for component in ('entrance', 'scale_before_iqr', 'north'):
            self.assertEqual(result['components'][component]['observations'], 5)
            self.assertEqual(result['components'][component]['users'], 4)
        self.assertEqual(result['components']['scale_after_iqr']['observations'], 4)
        self.assertEqual(result['components']['scale_after_iqr']['users'], 3)
        self.assertEqual(result['components']['scale_after_iqr']['rejected_submission_ids'], ['SUB_5'])

    def test_invalid_components_do_not_invalidate_other_components(self):
        bad_entrance = json.loads(row()['points_orig_json'])
        bad_entrance[0]['x'] = float('nan')
        rows = [row(1, points_orig_json=json.dumps(bad_entrance)),
                row(2, pixels_per_meter=-1), row(3, pixels_per_meter=float('inf')),
                row(4, pixels_per_meter=0), row(5, pixels_per_meter=True)]
        result = self.aggregate(rows)
        self.assertEqual(result['count'], 5)
        self.assertEqual(result['components']['entrance']['observations'], 4)
        self.assertEqual(result['components']['scale_before_iqr']['observations'], 1)
        self.assertEqual(result['components']['north']['observations'], 5)
        self.assertEqual(result['scale']['pixels_per_meter'], 10.)

    def test_north_requires_complete_finite_distinct_arrow_and_real_false_flag(self):
        complete = json.loads(row()['points_orig_json'])
        zero = copy.deepcopy(complete)
        zero[4] = zero[3]
        nonfinite = copy.deepcopy(complete)
        nonfinite[4]['y'] = float('inf')
        rows = [row(1), row(2, points_orig_json=json.dumps(complete[:3])),
                row(3, points_orig_json=json.dumps(zero)), row(4, points_orig_json=json.dumps(nonfinite)),
                row(5, skipNorth=True), row(6, north_deg=float('nan')),
                row(7, skipNorth=0), row(8, skipNorth='false')]
        result = self.aggregate(rows)
        self.assertEqual(result['components']['north']['submission_ids'], ['SUB_1'])
        self.assertEqual(result['north']['angle_deg'], 0.)
        self.assertEqual(result['north']['angle_origin'], 'measured')
        self.assertNotIn('reference', result['north'])

    def test_no_measurement_is_null_and_skip_status_is_explicit(self):
        for rows, skipped in [([row(1, skipNorth=True)], True),
                              ([row(1, points_orig_json='[]')], False)]:
            result = self.aggregate(rows)
            self.assertIsNone(result['north']['angle_deg'])
            self.assertEqual(result['north']['angle_origin'], 'unknown')
            self.assertEqual(result['north']['all_skipped'], skipped)
        invalid = self.aggregate([row(1, points_orig_json='invalid', pixels_per_meter=None)])
        self.assertEqual(invalid['entrance'], {'x': None, 'y': None})
        self.assertIsNone(invalid['scale']['pixels_per_meter'])
        self.assertIsNone(invalid['quality']['entrance_std_px'])
        self.assertIsNone(invalid['quality']['ppm_cv'])
        json.dumps(invalid, allow_nan=False)

    def test_below_threshold_and_entirely_excluded_groups_are_never_dropped(self):
        rows = [row(1, user='same'), row(2, user='same')]
        groups = core.aggregate_catalogue(pd.DataFrame(rows), min_users=2, classification={})
        self.assertEqual(list(groups), ['T.X-01.01'])
        self.assertFalse(groups['T.X-01.01']['eligible'])
        self.assertEqual(groups['T.X-01.01']['min_users'], 2)
        rows[0]['submit_type'] = 'SKIP'
        group = core.aggregate_catalogue(pd.DataFrame(rows[:1]), classification={})['T.X-01.01']
        self.assertEqual(group['count'], 0)
        self.assertFalse(group['eligible'])
        self.assertIsNone(group['north']['angle_deg'])
        subs = pd.read_parquet(ROOT / 'parquet/SUBMISSIONS.parquet')
        test_only = subs[subs.submission_id == 'SUB_1769506147971_9732']
        group = core.aggregate_catalogue(test_only)['T.D-08.07']
        self.assertEqual(group['source_count'], 1)
        self.assertEqual((group['count'], group['users']), (0, 0))
        self.assertEqual(group['excluded_submission_ids'], ['SUB_1769506147971_9732'])
        self.assertFalse(group['eligible'])
        self.assertIsNone(group['north']['angle_deg'])

    def test_invalid_duplicate_ids_and_mixed_images_fail_loudly(self):
        for rows in ([row(1), row(1)], [row(1, submission_id=' ')], [row(1, user_id=None)],
                     [row(1, cave_id='other')], [row(1), row(2, image_id=13)],
                     [row(1), row(2, image_used_path='caves_mono/000123/different.tif')],
                     [row(1, image_id=None)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.aggregate(rows)
        rows = [row(1), row(1, cave_id='other')]
        with self.assertRaisesRegex(ValueError, 'submission_id'):
            core.aggregate_catalogue(pd.DataFrame(rows), classification={})


if __name__ == '__main__':
    unittest.main()
