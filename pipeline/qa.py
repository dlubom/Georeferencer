"""Bieżące QA T09: reguły interpretacji oddzielnie od błędów technicznych.

Nie zapisuje katalogu ani nie migruje agregatów. Wyjątek dotyczy jednej reguły
jednego planu i dokładnej podstawy danych; nigdy nie zmienia metadanych.
"""
import copy
import csv
import hashlib
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

from coordinate_source import ROOT, DEFAULT_MANIFEST, read_rows, sha256, verify
from crowdsourcing import aggregate_catalogue, load_classification
from geotiff_output import input_hashes, write_json
from gps_kataster_coordinates import load_best_measurements
from validation import IMAGE_REGISTRY, UniqueLoader, validate_plan
import orientation
from qa_outputs import inspect_run

QA_DIR = ROOT / 'data/qa'
POLICY = {'version': 't09-v1', 'north_min_users': 3, 'north_max_spread_deg': 5,
          'scale_max_cv': .1, 'entrance_max_std_px': 10}
INTERPRETIVE = {'orientation.unknown', 'orientation.unverified', 'north.missing',
                'north.low_support', 'north.disagreement', 'scale.disagreement',
                'entrance.disagreement', 'entrance.review', 'source.review'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def generator_module():
    spec = importlib.util.spec_from_file_location('qa_generator', ROOT / 'pipeline/02_generate_geotiff.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_aggregates():
    source = ROOT / 'parquet/SUBMISSIONS.parquet'
    frame = pd.read_parquet(source)
    groups = aggregate_catalogue(frame, classification=load_classification())
    by_submission = frame.set_index('submission_id')['north_deg'].to_dict()
    for group in groups.values():
        ids = group['components']['north']['submission_ids']
        angles = [float(by_submission[sid]) for sid in ids]
        group['north']['values_deg'] = angles
        group['north']['max_pairwise_difference_deg'] = max(
            (abs((a - b + 180) % 360 - 180) for a in angles for b in angles), default=None)
    return {group['dir_id']: group for group in groups.values()}


def _default(name):
    return json.loads((QA_DIR / name).read_text(encoding='utf-8'))


def enforce(problems, exceptions):
    """Walidacja rejestru jest fail-closed, w tym wpisy bez aktualnej reguły."""
    errors, seen = [], set()
    by_key = {(p['plan_id'], p['rule']): p for p in problems}
    if not isinstance(exceptions, dict) or type(exceptions.get('schema_version')) is not int or exceptions['schema_version'] != 1 or not isinstance(exceptions.get('exceptions'), list):
        return [{'plan_id': '__registry__', 'rule': 'exception.invalid', 'evidence': 'Wymagany rejestr v1 z listą exceptions', 'accepted': False, 'technical': True}]
    for entry in exceptions['exceptions']:
        key = (entry.get('plan_id'), entry.get('rule')) if isinstance(entry, dict) else (None, None)
        valid = isinstance(entry, dict) and all(isinstance(entry.get(k), str) and entry[k].strip()
            for k in ('plan_id', 'rule', 'reason', 'close_when', 'basis_sha256'))
        valid = valid and isinstance(entry.get('sources'), list) and bool(entry['sources']) and all(
            isinstance(s, str) and s.strip() for s in entry['sources'])
        if not valid or not all(isinstance(k, str) for k in key) or key[1] not in INTERPRETIVE or key in seen:
            errors.append({'plan_id': str(key[0]), 'rule': 'exception.invalid', 'evidence': 'Niepoprawny, powtórzony lub techniczny wyjątek', 'accepted': False, 'technical': True})
            continue
        seen.add(key)
        problem = by_key.get(key)
        if problem is None or entry['basis_sha256'] != problem['basis_sha256'] or entry.get('evidence') != problem['evidence']:
            errors.append({'plan_id': key[0], 'rule': 'exception.stale', 'evidence': {'rule': key[1], 'saved_basis': entry['basis_sha256'], 'current_basis': problem.get('basis_sha256') if problem else None}, 'accepted': False, 'technical': True})
            continue
        problem['accepted'] = True
        problem['exception'] = copy.deepcopy(entry)
    return errors


def create_report(data_dir=ROOT / 'data/caves', *, registry_path=IMAGE_REGISTRY,
                  aggregates=None, observations=None, exceptions=None, run_dir=None, require_results=False):
    """Dokładny bieżący katalog; parametry in-memory służą testom syntetycznym."""
    data_dir, registry_path = Path(data_dir), Path(registry_path)
    problems, records, prepared, reconciliation = [], [], {}, []
    generator = generator_module()
    plans = {p.name: p for p in sorted(data_dir.iterdir() if data_dir.is_dir() else []) if p.is_dir() and not p.name.startswith(('_', '.'))}
    if not plans:
        problems.append({'plan_id': '__catalogue__', 'rule': 'input.missing', 'evidence': 'Pusty katalog planów'})
    source_error = None
    try:
        csv_path = verify()
        index, rows = load_best_measurements(csv_path), read_rows(csv_path)
        registry_raw = registry_path.read_bytes()
        registry = json.loads(registry_raw)
        aggregation_sources = ({'SUBMISSIONS.parquet': sha256(ROOT / 'parquet/SUBMISSIONS.parquet'),
            'test-submissions-v1.json': sha256(ROOT / 'data/classification/test-submissions-v1.json')} if aggregates is None else {})
        aggregates = load_aggregates() if aggregates is None else aggregates
        observations = _default('observations-v1.json')['observations'] if observations is None else observations
        context = orientation.load_context()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        source_error = 'missing' if isinstance(exc, FileNotFoundError) else 'invalid'
        problems.append({'plan_id': '__sources__', 'rule': 'input.' + source_error, 'evidence': str(exc)})
        aggregates, observations, rows, index, registry, context = {}, [], {}, None, {}, None
        registry_raw = b''
        aggregation_sources = {}
    for plan_id, directory in plans.items():
        record = {'plan_id': plan_id, 'input_status': 'invalid', 'output_status': 'not_requested',
                  'origin': 'unresolved', 'source_cave_id': None, 'image_id': None, 'object_id': None,
                  'link_status': 'invalid', 'problems': []}
        records.append(record)
        if source_error:
            record['input_status'] = source_error
            continue
        try:
            missing = [name for name in ('meta.yaml', 'image.tif') if not (directory / name).is_file()]
            if missing:
                problems.append({'plan_id': plan_id, 'rule': 'input.missing', 'evidence': missing})
                record['input_status'] = 'missing'
                continue
            raw = (directory / 'meta.yaml').read_bytes()
            local_path = directory / 'image-identity.json'
            local = local_path.read_bytes() if local_path.exists() else None
            preview = yaml.load(raw.decode('utf-8'), Loader=UniqueLoader)
            if isinstance(preview, dict) and isinstance(preview.get('orientation'), dict) and 'origin' in preview['orientation'] and local is None:
                record['input_status'] = 'missing'
                problems.append({'plan_id': plan_id, 'rule': 'input.missing', 'evidence': ['image-identity.json']})
                continue
            if local is not None and not isinstance(json.loads(local), dict):
                raise ValueError('image-identity.json: wymagana mapa JSON')
            inputs = input_hashes(directory)
            inputs['meta.yaml'] = hashlib.sha256(raw).hexdigest()
            if local is None:
                inputs.pop('image-identity.json', None)
            else:
                inputs['image-identity.json'] = hashlib.sha256(local).hexdigest()
            meta, resolved = validate_plan(directory, index, registry, meta_text=raw.decode('utf-8'),
                orientation_context=context, identity_text=local.decode('utf-8') if local is not None else False)
            params = generator.compute_world_file(resolved, context)
            if not all(math.isfinite(v) for v in params.values()):
                raise ValueError('Nieskończone parametry transformacji')
            if inputs != input_hashes(directory):
                raise ValueError('Wejścia zmieniły się podczas odczytu QA')
            prepared[plan_id] = (meta, resolved, params)
            group = aggregates.get(plan_id)
            historical = context['plans'].get(plan_id)
            manual = 'origin' in meta['orientation'] or (historical and historical['cave'].get('n_submissions') == 0)
            if group and not manual and group['image_id'] != meta['image']['image_id']:
                raise ValueError('Tożsamość obrazu agregatu T07 nie odpowiada planowi')
            if not manual and group is None and aggregates:
                raise ValueError('Brak grupy crowdsourcingu dla planu')
            source_id = meta['cave'].get('source_cave_id') or (historical['cave'].get('pig_id') if historical else None)
            record.update(input_status='valid', origin='manual_t08' if 'origin' in meta['orientation'] else ('manual_historical' if manual else 'crowdsourcing'),
                source_cave_id=source_id, image_id=meta['image']['image_id'], object_id=meta['coordinates']['gps_kataster_object_id'],
                name=meta['cave']['name'], inventory_number=meta['cave'].get('inventory_number'),
                link_status='explicit_valid', measurement=rows[meta['coordinates']['gps_kataster_object_id']],
                orientation=orientation.summary(meta), rotation_deg=params['total_rotation_deg'],
                north_angle_deg=meta['north']['angle_deg'], components=group['components'] if group and not manual else None,
                north_measurements=group['north'] if group and not manual else None,
                source_id_basis='cave.source_cave_id' if 'source_cave_id' in meta['cave'] else 'historical plan directory; separate source ID unavailable',
                inputs=inputs, n_submissions=meta['cave'].get('n_submissions'),
                coordinates=resolved['coordinates'], raw_quality=group['raw'] if group and not manual else None, quality=group['quality'] if group and not manual else meta.get('quality', {}),
                crowdsourcing={k: group[k] for k in ('source_count', 'count', 'users', 'excluded_submission_ids', 'exclusions')} if group and not manual else None)
            if record['source_cave_id'] is None and group and not manual:
                # cave_id agregatu jest numerem inwentarzowym; nie jest source_cave_id PIG.
                record['crowdsourcing_cave_id'] = group['cave_id']
            relevant = {'policy': POLICY, 'inputs': inputs, 'image_registry_sha256': hashlib.sha256(registry_raw).hexdigest(),
                        'measurement': record['measurement'], 'orientation': record['orientation'],
                        'aggregate': group if not manual else None,
                        'aggregation_sources': aggregation_sources if not manual else {}}

            def issue(rule, evidence):
                problems.append({'plan_id': plan_id, 'rule': rule, 'evidence': evidence,
                    'basis_sha256': digest({'inputs': relevant, 'rule': rule, 'evidence': evidence})})

            if meta['north']['reference'] == 'unknown':
                issue('orientation.unknown', {k: record['orientation'].get(k) for k in
                    ('north_reference', 'angle_origin', 'mode', 'status', 'uncertainty_reason', 'historical', 'grid_assumption')})
            elif meta['orientation']['status'] == 'unverified':
                issue('orientation.unverified', record['orientation'])
            if group and not manual:
                north = group['components']['north']
                if north['observations'] == 0:
                    issue('north.missing', group['north'])
                elif north['users'] < POLICY['north_min_users']:
                    issue('north.low_support', north)
                spread = group['north'].get('max_pairwise_difference_deg')
                if group['north'].get('ambiguous') or (spread is not None and spread > POLICY['north_max_spread_deg']):
                    issue('north.disagreement', group['north'])
                quality = group['quality']
            else:
                quality = meta.get('quality', {})
            for metric, threshold, rule in (('ppm_cv', POLICY['scale_max_cv'], 'scale.disagreement'),
                                           ('entrance_std_px', POLICY['entrance_max_std_px'], 'entrance.disagreement')):
                value = group['raw'].get(metric) if group and not manual else quality.get(metric)
                if type(value) in (float, int) and value > threshold:
                    issue(rule, {metric: value, 'threshold': threshold})
            for observation in observations:
                if plan_id in observation.get('plan_ids', []):
                    rule = observation['rule']
                    if rule not in {'source.review', 'entrance.review'}:
                        raise ValueError('Niepoprawna reguła obserwacji')
                    evidence = {**observation, 'current_object_id': record['object_id'], 'input_status': 'valid'}
                    issue(rule, evidence)
                    if rule == 'entrance.review':
                        record['link_status'] = 'explicit_valid_pending_review'
        except (OSError, ValueError, TypeError, KeyError, ArithmeticError, yaml.YAMLError) as exc:
            prepared.pop(plan_id, None)
            record['input_status'] = 'invalid'
            problems.append({'plan_id': plan_id, 'rule': 'input.invalid', 'evidence': str(exc)})
    states, output_problems = inspect_run(run_dir, plans, prepared, rows, registry_path, generator, require_results)
    problems.extend(output_problems)
    for record in records:
        record['output_status'] = states[record['plan_id']]
    by_id = {r['plan_id']: r for r in records}
    for observation in observations:
        matches = [by_id[p] for p in observation.get('plan_ids', []) if p in by_id]
        reconciliation.append({**observation, 'current_plans': [{k: p.get(k) for k in
            ('plan_id', 'image_id', 'object_id', 'input_status', 'output_status', 'link_status')} for p in matches],
            'status': 'unresolved_interpretation' if matches else 'unmatched_name_or_id',
            'conclusion': 'Dawna uwaga nie dowodzi aktualnego defektu; wymaga sprawdzenia źródła.' if matches else 'Brak dokładnego dopasowania nazwy lub jawnego ID; nie jest to dowód nieobecności jaskini ani planu. Zachowano źródło uwagi.'})
    for problem in problems:
        problem.update(technical=problem['rule'] not in INTERPRETIVE, accepted=False)
        problem.setdefault('basis_sha256', digest({'rule': problem['rule'], 'evidence': problem['evidence']}))
    exceptions = _default('exceptions-v1.json') if exceptions is None else exceptions
    problems.extend(enforce(problems, exceptions))
    problems.sort(key=lambda p: (p['plan_id'], p['rule'], digest(p['evidence'])))
    for record in records:
        record['problems'] = [p['rule'] for p in problems if p['plan_id'] == record['plan_id']]
    return {'schema_version': 1, 'policy': POLICY, 'passed': not any(not p['accepted'] for p in problems),
            'counts': {'plans': len(records), 'origins': dict(sorted(Counter(p['origin'] for p in records).items())),
                       'problems': len(problems), 'accepted': sum(p['accepted'] for p in problems),
                       'blocking': sum(not p['accepted'] for p in problems)},
            'plans': records, 'problems': problems, 'issue_reconciliation': reconciliation}


def write_reports(report, reports_dir):
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_json(reports_dir / 'qa.json', report)
    fields = ['dir_id', 'inventory_number', 'name', 'origin', 'source_cave_id', 'image_id', 'object_id',
              'input_status', 'output_status', 'link_status', 'north_angle_deg', 'north_reference',
              'angle_origin', 'orientation_status', 'orientation_uncertainty_reason',
              'north_observations', 'north_users', 'north_spread_deg', 'problems']
    for name, selected in [('summary', report['plans']), ('flagged', [p for p in report['plans'] if p['problems']]),
                           ('missing', [p for p in report['plans'] if p['input_status'] == 'missing' or p['output_status'] == 'missing'])]:
        with (reports_dir / (name + '.csv')).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for plan in selected:
                row = {k: plan.get(k) for k in fields if k in plan}
                north, components = plan.get('north_measurements') or {}, (plan.get('components') or {}).get('north', {})
                orientation_data = plan.get('orientation', {})
                row.update(dir_id=plan['plan_id'], north_reference=orientation_data.get('north_reference'),
                    angle_origin=orientation_data.get('angle_origin'), orientation_status=orientation_data.get('status'),
                    orientation_uncertainty_reason=orientation_data.get('uncertainty_reason'),
                    north_observations=components.get('observations'), north_users=components.get('users'),
                    north_spread_deg=north.get('max_pairwise_difference_deg'), problems=';'.join(plan['problems']))
                writer.writerow(row)
