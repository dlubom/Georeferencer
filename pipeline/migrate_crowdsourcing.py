"""T07: selektywna migracja agregatów z zachowaniem ręcznych korekt i historii."""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path

import pandas as pd
import yaml

from coordinate_source import ROOT, sha256, verify
from crowdsourcing import aggregate_catalogue, load_classification, DEFAULT_CLASSIFICATION
from geometry_impact import load_generator, at_click, ORDER
from gps_kataster_coordinates import load_best_measurements
from migrate_north import migrated_bytes
from orientation import load_context, digest, record_decision, validate_orientation
from validation import validate_meta, read_registry, validate_plan

REPORT = ROOT / 'docs/reports/t07-aggregation-impact.json'
MANUAL = ROOT / 'data/classification/manual-north-v1.json'
BASE_COMMIT = '44e279f566d3ea74d600a24f63a452c5c191f674'
REASON = ('T07: wyłączenie jawnych rekordów TEST lub niekompletnych strzałek; '
          'korekta agregatu nie ustala rodzaju północy. Zachowujemy kąt historycznego TFW T02. '
          'Raport: docs/reports/t07-aggregation-impact.json; SHA-256 obrazu: ')


def preserved_edit(plan_id, component, current, old, evidence):
    proof = evidence.get(plan_id) if component == 'north' else None
    if proof and (current['angle_deg'] != proof['manual_angle_deg']
                  or old['angle_deg'] != proof['aggregate_angle_deg']):
        proof = None
    return {'dir_id': plan_id, 'component': component, 'current': current, 'legacy_aggregate': old,
            'status': 'documented_manual_correction' if proof else 'requires_decision',
            'evidence': proof, 'action': 'preserve',
            'reason': 'Różnica z agregatem nie dowodzi błędu ręcznej korekty.'}


def reconcile_plan(before, legacy, aggregate, north_affected, evidence=None):
    """Zmień tylko komponent równy dawnej agregacji; rozbieżność zachowaj jawnie."""
    evidence = {} if evidence is None else evidence
    after = copy.deepcopy(before)
    plan_id = before['cave']['dir_id']
    preserved = []
    test_affected = bool(aggregate['excluded_submission_ids'])
    for component in ('entrance', 'scale', 'quality', 'north'):
        current = before[component]
        if component == 'north':
            current = {k: current[k] for k in ('angle_deg', 'all_skipped')}
        if current != legacy[component]:
            preserved.append(preserved_edit(plan_id, component, current, legacy[component], evidence))
            continue
        if component == 'north':
            if north_affected and aggregate['north']['angle_deg'] is not None:
                after['north'].update({k: aggregate['north'][k] for k in ('angle_deg', 'all_skipped')})
                after['north']['angle_origin'] = 'measured'
            # Brak pomiaru nie zastępuje starej wartości 0 ani nie nadaje jej measured.
        elif test_affected:
            if aggregate[component] is not None:
                after[component] = copy.deepcopy(aggregate[component])
    if test_affected:
        if before['cave']['n_submissions'] == legacy['cave']['n_submissions']:
            after['cave']['n_submissions'] = aggregate['count']
        else:
            preserved.append(preserved_edit(plan_id, 'cave.n_submissions', before['cave']['n_submissions'],
                                            legacy['cave']['n_submissions'], evidence))
    if before['north'] != after['north']:
        after = record_decision(after, REASON + before['orientation']['image_sha256'], '2026-10-25')
    validate_meta(after, plan_id)
    validate_orientation(after)
    return after, preserved


def field_changes(before, after, prefix=''):
    """Dokładne wartości zmienionych pól; listy zachowujemy w całości."""
    changes = {}
    for key in sorted(set(before) | set(after)):
        name = f'{prefix}.{key}' if prefix else key
        old, new = before.get(key), after.get(key)
        if isinstance(old, dict) and isinstance(new, dict):
            changes.update(field_changes(old, new, name))
        elif old != new:
            changes[name] = {'before': old, 'after': new}
    return changes


def geometry(before, after, generator, index, context):
    metas = [copy.deepcopy(before), copy.deepcopy(after)]
    for meta in metas:
        row = index.by_object_id[meta['coordinates']['gps_kataster_object_id']]
        meta['coordinates'].update(lat=row.lat, lon=row.lon)
    models = [generator.compute_world_file(m, context) for m in metas]
    tfws = [{k: float(f'{p[k]:.{10 if k in "ADBE" else 6}f}') for k in ORDER} for p in models]
    def delta(points):
        dx, dy = (b-a for a,b in zip(*points))
        return {'before_m': points[0], 'after_m': points[1], 'dx_m': dx, 'dy_m': dy,
                'distance_m': math.hypot(dx, dy)}
    rotations = [p['total_rotation_deg'] for p in models]
    scales = [1/m['scale']['pixels_per_meter'] for m in metas]
    return {'before_tfw': tfws[0], 'after_tfw': tfws[1],
            'position': {'at_fixed_before_click': delta([at_click(p, before['entrance']) for p in tfws]),
                         'at_each_selected_click': delta([at_click(p,m['entrance']) for p,m in zip(tfws,metas)]),
                         'pixel_origin': delta([at_click(p,{'x':0,'y':0}) for p in tfws])},
            'orientation': {'before_deg': rotations[0], 'after_deg': rotations[1],
                            'delta_deg': (rotations[1]-rotations[0]+180)%360-180,
                            'reference': after['north']['reference'], 'status': after['orientation']['status']},
            'scale': {'before_m_per_pixel': scales[0], 'after_m_per_pixel': scales[1],
                      'delta_m_per_pixel': scales[1]-scales[0]},
            'source_metadata_verified': False}


def migration(root=ROOT):
    root = Path(root)
    context = load_context()
    baseline = json.loads((ROOT / 'data/baseline/2026-10-24/catalogue.json').read_text())
    # Dokładne źródła i kod do porównania historycznego, bez odświeżania hashy.
    for name in ('parquet/SUBMISSIONS.parquet', 'parquet/CAVES.parquet', 'pipeline/01_extract_yaml.py'):
        if sha256(ROOT / name) != baseline['other_inputs_sha256'][name]:
            raise ValueError(f'{name}: zmienione wejście T02 (SHA-256)')
    legacy = load_generator(ROOT / 'pipeline/01_extract_yaml.py', baseline['other_inputs_sha256']['pipeline/01_extract_yaml.py'])
    generator = load_generator(ROOT / 'pipeline/02_generate_geotiff.py')
    subs = pd.read_parquet(ROOT / 'parquet/SUBMISSIONS.parquet')
    caves = pd.read_parquet(ROOT / 'parquet/CAVES.parquet')
    classification = load_classification()
    aggregates = aggregate_catalogue(subs, classification=classification)
    evidence = {p['dir_id']: p for p in json.loads(MANUAL.read_text())['corrections']}
    index = load_best_measurements(verify())
    t05 = {p['dir_id']: p for p in json.loads((ROOT / 'data/migrations/t05-north.json').read_text())['plans']}
    groups, plans, writes, manual, preserved = [], [], [], [], []
    test_plans = []
    for plan_id, plan in sorted(context['plans'].items()):
        before_raw = migrated_bytes(context['originals'][plan_id], plan)
        if digest(before_raw) != t05[plan_id]['after_sha256']:
            raise ValueError(f'{plan_id}: odtworzenie bajtów T05 niezgodne z historycznym raportem')
        before = yaml.safe_load(before_raw)
        path = root / f'data/caves/{plan_id}/meta.yaml'
        after_raw = before_raw
        if before['cave']['n_submissions'] == 0:
            manual.append({'dir_id': plan_id, 'sha256': digest(before_raw)})
        else:
            cave_id = before['cave']['inventory_number']
            aggregate = aggregates[cave_id]
            old_group = subs[subs['cave_id'] == cave_id]
            old = legacy.aggregate_cave(cave_id, old_group, caves)['yaml_data']
            retained = old_group[~old_group.submission_id.isin(classification)]
            north_affected = bool(aggregate['excluded_submission_ids']) or int((retained.skipNorth == False).sum()) > aggregate['components']['north']['observations']
            after, edits = reconcile_plan(before, old, aggregate, north_affected, evidence)
            preserved.extend(edits)
            groups.append({'dir_id': plan_id, 'cave_id': cave_id, 'observations': aggregate['count'],
                           'users': aggregate['users'], 'eligible': aggregate['eligible'],
                           'components': {k:{f:v[f] for f in ('observations','users')} for k,v in aggregate['components'].items()}})
            if aggregate['excluded_submission_ids']:
                test_plans.append(plan_id)
            if after != before:
                # Zapisz tylko zmienione sekcje; pozostałe bajty/ręczna precyzja są nienaruszone.
                sections = before_raw.decode('utf-8').splitlines(keepends=True)
                chunks, key = {}, None
                for line in sections:
                    match = re.match(r'^([A-Za-z_]\w*):', line)
                    if match:
                        key = match.group(1)
                    chunks.setdefault(key, []).append(line)
                after_raw = ''.join(yaml.safe_dump({k:after[k]}, allow_unicode=True, sort_keys=False, width=120)
                                    if k is not None and before[k] != after[k] else ''.join(lines)
                                    for k,lines in chunks.items()).encode('utf-8')
                if yaml.safe_load(after_raw) != after:
                    raise ValueError(f'{plan_id}: serializacja zmienia dane')
                writes.append((path, after_raw))
            if north_affected:
                plans.append({'dir_id': plan_id, 'name': before['cave']['name'],
                              'reason': 'TEST' if aggregate['excluded_submission_ids'] else 'incomplete_north',
                              'before_sha256': digest(before_raw), 'after_sha256': digest(after_raw),
                              'before': before, 'after': after, 'fields': field_changes(before,after),
                              'legacy_aggregate': {k: old[k] for k in ('entrance','scale','north','quality')},
                              'aggregate': aggregate, 'preserved_edits': edits,
                              'geometry': geometry(before, after, generator, index, context)})
        if path.read_bytes() not in (before_raw, after_raw):
            raise ValueError(f'{plan_id}: późniejsza edycja; migracja nie nadpisuje danych, wymagane rozstrzygnięcie')
    mrozna = next(p for p in plans if p['dir_id'] == '001094')
    raw_points = [json.loads(v)[0] for v in subs[subs.cave_id == 'T.D-08.07'].points_orig_json]
    old_std = float(math.sqrt(pd.Series([p['x'] for p in raw_points]).var(ddof=0) + pd.Series([p['y'] for p in raw_points]).var(ddof=0)))
    report = {'schema_version': 1, 'kind': 't07_selective_crowdsourcing_migration', 'before_commit': BASE_COMMIT,
              'inputs_sha256': {name:sha256(ROOT / name) for name in
                               ('parquet/SUBMISSIONS.parquet','parquet/CAVES.parquet',
                                'data/classification/test-submissions-v1.json','data/classification/manual-north-v1.json',
                                'data/migrations/t05-north.json','docs/reports/t06-geometry-impact.json',
                                'data/history/t02-inputs.zip','data/baseline/2026-10-24/catalogue.json',
                                'data/coordinate-source/source.json','data/coordinate-source/best-measurements-v1.3.1.csv')},
              'historical_groups': len(groups), 'minimum_non_test_users': min(p['users'] for p in groups),
              'below_threshold': [p['dir_id'] for p in groups if not p['eligible']],
              'test_affected_plans': test_plans, 'changed_yaml_plans': [p.parent.name for p,_ in writes],
              'manual_plans_unchanged': manual, 'preserved_edits': preserved,
              'mrozna_reproduction': {'method': 'sqrt(var(x,ddof=0)+var(y,ddof=0)); bez odrzucania otworów jako outlierów',
                                      'rounding': 'Python round(value, 2); wyłącznie zapis, obliczenia na pełnych punktach',
                                      'before_px': old_std, 'after_px': mrozna['aggregate']['raw']['entrance_std_px'],
                                      'before_rounded_px': round(old_std,2),
                                      'after_rounded_px': mrozna['after']['quality']['entrance_std_px']},
              'interpretation': 'Północ unknown/unverified: kąt wyłącznie z TFW T02. Położenie porównane w stałym dawnym kliknięciu '
                                'oraz w każdym bieżącym otworze osobno; skala i obrót osobno. computed i źródłowe TFW są historyczne, '
                                'nie odświeżane. Brak ważnej północy daje null w agregacie; stary kąt YAML nie jest nowym pomiarem.',
              'groups': groups, 'plans': plans}
    return report, writes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Jawnie zapisz tylko kontrolowane YAML-e T07')
    parser.add_argument('--report', type=Path, required=True, help='Osobny raport; nigdy historyczny T02/T05/T06')
    args = parser.parse_args()
    output = args.report.resolve()
    if output == (ROOT / 'docs/reports/t06-geometry-impact.json').resolve() or any(
            output == (ROOT/p).resolve() or (ROOT/p).resolve() in output.parents for p in ('data','parquet','pipeline','tests','.git')):
        parser.error('Raport musi leżeć poza źródłami, historią i raportem T06')
    report, writes = migration()
    if args.apply:
        index, registry = load_best_measurements(verify()), read_registry()
        for path, raw in writes:
            validate_plan(path.parent, index, registry, raw.decode('utf-8'))
        for path, raw in writes:
            path.write_bytes(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(f'{len(writes)} zmienionych YAML-i; {len(report["plans"])} planów w raporcie; zapis: {args.apply}')


if __name__ == '__main__':
    main()
