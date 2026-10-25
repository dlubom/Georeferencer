"""Independent numeric/source audit; writes only the supplied review directory."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from unittest.mock import patch

import yaml
from pyproj import Transformer

ROOT = Path('/workspace')
OUT = Path('/audit')
sys.path.insert(0, str(ROOT / 'pipeline'))
import qa
import coordinate_source


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_csv(version):
    path = ROOT / f'data/coordinate-source/best-measurements-{version}.csv'
    rows = list(csv.DictReader(path.open(newline='', encoding='utf-8-sig')))
    result = {r['object_id']: r for r in rows}
    assert len(result) == len(rows)
    return result


old, new = read_csv('v1.3.1'), read_csv('v1.3.2')
impact = json.loads((ROOT / 'docs/reports/coordinate-source-v1.3.2-impact.json').read_text())
history = json.loads((ROOT / 'data/baseline/2026-10-24/catalogue.json').read_text())
historical = {p['dir_id']: p for p in history['plans']}
metas = {p.parent.name: yaml.safe_load(p.read_bytes())
         for p in sorted((ROOT / 'data/caves').glob('*/meta.yaml'))}
assert set(metas) == set(historical)
links = {}
for plan_id, meta in metas.items():
    key = meta['coordinates']['gps_kataster_object_id']
    links.setdefault(key, []).append(plan_id)
    assert key in new
    assert new[key]['category'] in {'jaskinia_otwor', 'sztolnia'}
    assert key == historical[plan_id]['object_id']
    assert meta['north']['reference'] == 'unknown'
    assert meta['orientation']['mode'] == 'historical_tfw'
    assert meta['orientation']['status'] == 'unverified'

expected_changes = []
for object_id in sorted(old.keys() | new.keys()):
    before, after = old.get(object_id, {}), new.get(object_id, {})
    fields = {k: {'before': before.get(k), 'after': after.get(k)}
              for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)}
    if fields:
        expected_changes.append({'object_id': object_id, 'plans': sorted(links.get(object_id, [])),
                                 'fields': fields, 'before': before or None, 'after': after or None,
                                 'position_changed': bool({'lat', 'lon'} & fields.keys())})
assert expected_changes == impact['changes']
affected = sorted({plan for change in expected_changes for plan in change['plans']})
assert affected == impact['affected_plans'] == ['001349', '001351', '001387', '010935']

project = Transformer.from_crs('EPSG:4326', 'EPSG:2180', always_xy=True)
order = ('A', 'D', 'B', 'E', 'C', 'F')


def independent_tfw(plan_id, rows):
    meta = metas[plan_id]
    historical_tfw = historical[plan_id]['historical_tfw']['parameters']
    angle = math.atan2(historical_tfw['D'], historical_tfw['A'])
    mpp = 1 / meta['scale']['pixels_per_meter']
    a, d = mpp * math.cos(angle), mpp * math.sin(angle)
    b, e = d, -a
    row = rows[meta['coordinates']['gps_kataster_object_id']]
    x, y = project.transform(float(row['lon']), float(row['lat']))
    u, v = meta['entrance']['x'] - .5, meta['entrance']['y'] - .5
    values = dict(A=a, D=d, B=b, E=e, C=x - a*u - b*v, F=y - d*u - e*v)
    return '\n'.join(f'{values[k]:.{10 if k in "ADBE" else 6}f}' for k in order) + '\n'


t11 = json.loads((ROOT / 'docs/reports/t11-reproducibility.json').read_text())
previous = {p['plan_id']: p for p in t11['comparisons']}
changed_plans, independent_geometry = [], []
for plan_id in sorted(metas):
    before, after = independent_tfw(plan_id, old), independent_tfw(plan_id, new)
    assert digest(before.encode()) == previous[plan_id]['tfw_sha256'], plan_id
    if before != after:
        changed_plans.append(plan_id)
        record = next(p for p in impact['geometry']['plans'] if p['dir_id'] == plan_id)
        assert record['before']['tfw_text'] == before
        assert record['after']['tfw_text'] == after
        p, q = [dict(zip(order, map(float, text.splitlines()))) for text in (before, after)]
        assert all(p[k] == q[k] for k in ('A', 'D', 'B', 'E'))
        de, dn = q['C'] - p['C'], q['F'] - p['F']
        assert abs(de - record['delta']['entrance_dx_m']) < 1e-9
        assert abs(dn - record['delta']['entrance_dy_m']) < 1e-9
        assert record['delta']['rotation_deg'] == record['delta']['scale_m_per_pixel'] == 0
        independent_geometry.append({'plan_id': plan_id, 'delta_e_m': de, 'delta_n_m': dn,
                                     'distance_m': math.hypot(de, dn), 'rotation_scale_unchanged': True})
assert changed_plans == affected

prior_exceptions = json.loads((OUT / 'prior-exceptions.json').read_text())
current_exceptions = json.loads((ROOT / 'data/qa/exceptions-v1.json').read_text())
old_pin = ROOT / 'data/coordinate-source/source-v1.3.1.json'
with patch.object(qa, 'verify', lambda: coordinate_source.verify(old_pin)):
    before_qa = qa.create_report(exceptions=prior_exceptions)
stale_qa = qa.create_report(exceptions=prior_exceptions)
current_qa = qa.create_report()
assert before_qa['passed'] and current_qa['passed']
assert before_qa['counts']['accepted'] == current_qa['counts']['accepted'] == 1405
assert before_qa['counts']['blocking'] == current_qa['counts']['blocking'] == 0
assert stale_qa['counts']['accepted'] == 1396 and stale_qa['counts']['blocking'] == 18
review = json.loads((ROOT / 'docs/reports/coordinate-source-v1.3.2-qa-review.json').read_text())
assert review['before_counts'] == before_qa['counts']
assert review['stale_counts'] == stale_qa['counts']
prior_entries = {(p['plan_id'], p['rule']): p for p in prior_exceptions['exceptions']}
current_entries = {(p['plan_id'], p['rule']): p for p in current_exceptions['exceptions']}
assert len(prior_entries) == len(prior_exceptions['exceptions']) == 1405
assert set(prior_entries) == set(current_entries)
changed_entries = {key for key in prior_entries if prior_entries[key] != current_entries[key]}
assert len(changed_entries) == 9
assert changed_entries == {(p['plan_id'], p['rule']) for p in review['reviewed_entries']}
current_problems = {(p['plan_id'], p['rule']): p for p in current_qa['problems']}
prior_plans = {p['plan_id']: p for p in before_qa['plans']}
current_plans = {p['plan_id']: p for p in current_qa['plans']}
for record in review['reviewed_entries']:
    key = record['plan_id'], record['rule']
    assert record['before'] == prior_entries[key]
    assert record['after'] == current_entries[key] == current_problems[key]['exception']
    assert record['measurement_before'] == prior_plans[key[0]]['measurement']
    assert record['measurement_after'] == current_plans[key[0]]['measurement']
    assert current_entries[key]['evidence'] == prior_entries[key]['evidence']
    assert current_entries[key]['close_when'] == prior_entries[key]['close_when']
    assert current_entries[key]['basis_sha256'] == current_problems[key]['basis_sha256']
    assert key[1] in qa.INTERPRETIVE and not current_problems[key]['technical']
for plan_id in metas:
    before, after = prior_plans[plan_id], current_plans[plan_id]
    difference = {k for k in before if before[k] != after[k]}
    assert difference <= {'coordinates', 'measurement'}, (plan_id, difference)
    if difference:
        assert plan_id in affected

result = {'passed': True, 'source_objects_before': len(old), 'source_objects_after': len(new),
          'existing_objects_changed': sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
          'objects_added': sorted(new.keys()-old.keys()), 'objects_removed': sorted(old.keys()-new.keys()),
          'full_field_report_matches_csv': True, 'explicit_plan_links_valid_and_unchanged': len(metas),
          'independent_tfw_matches_t11': len(metas), 'independent_tfw_changed': changed_plans,
          'geometry': independent_geometry, 'qa_before': before_qa['counts'],
          'qa_stale': stale_qa['counts'], 'qa_after': current_qa['counts'],
          'qa_entries_reviewed': len(changed_entries), 'qa_entries_identical': 1405-len(changed_entries),
          'qa_evidence_and_close_conditions_unchanged': True,
          'inputs_orientation_aggregate_unchanged': True}
(OUT / 'source-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
