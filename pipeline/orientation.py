"""Jawne źródła T05, modele północy T06 i niezmienny kąt zapisanych TFW T02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from functools import lru_cache
from datetime import date
from pathlib import Path
import zipfile

import yaml
from pyproj import Proj

from coordinate_source import ROOT

BASELINE = ROOT / 'data/baseline/2026-10-24/catalogue.json'
ARCHIVE = ROOT / 'data/history/t02-inputs.zip'
BASELINE_SHA256 = 'b9031ff93f9ca9a1930f3574cd2eddddfd8690235be4bee2610b993858df3541'
REASON = 'Nie ustalono rodzaju północy ani podstawy deklinacji; zachowano orientację historycznego TFW T02.'
REFERENCES = ('unknown', 'geographic', 'magnetic', 'grid')
PROJECTION = Proj('EPSG:2180')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def error(plan, field, rule):
    raise ValueError(f'plan {plan}: {field}: {rule}')


def text(value, plan, field):
    if not isinstance(value, str) or not value.strip():
        error(plan, field, 'wymagany niepusty tekst')


def orientation_inputs(meta):
    """Współrzędne, skala i kliknięcie otworu nie określają zachowanego kąta."""
    return {**{key: copy.deepcopy(meta.get(key)) for key in
               ('north', 'declination_deg', 'declination', 'image')},
            'image_sha256': meta.get('orientation', {}).get('image_sha256')}


def inputs_hash(meta):
    return digest(json.dumps(orientation_inputs(meta), sort_keys=True,
                             ensure_ascii=False, allow_nan=False).encode('utf-8'))


def migration_metadata(original, plan, catalogue_sha256=BASELINE_SHA256):
    """Wyłącznie dodanie jawnej niewiedzy, bez interpretacji liczby zero."""
    meta = copy.deepcopy(original)
    north = meta['north']
    north['reference'] = 'unknown'
    # all_skipped jest dowodem przyjęcia kąta; false samo nie dowodzi pomiaru.
    north['angle_origin'] = 'assumed' if north.get('all_skipped') is True else 'unknown'
    meta['declination'] = {
        'status': 'unknown',
        'basis': 'Historyczna wartość declination_deg; brak udokumentowanej podstawy i konwencji znaku.'}
    meta['orientation'] = {
        'mode': 'historical_tfw', 'status': 'unverified', 'uncertainty_reason': REASON,
        'image_sha256': plan['sha256'][f"data/caves/{plan['dir_id']}/image.tif"],
        'historical': {'catalogue_sha256': catalogue_sha256, 'plan_id': plan['dir_id'],
                       'tfw_sha256': digest(plan['historical_tfw']['text'].encode('utf-8'))},
        'decisions': []}
    return meta


def load_context(baseline_bytes=None, archive_bytes=None):
    """Odczytane bajty są zarazem źródłem hashy i interpretacji snapshotu T04."""
    baseline_bytes = BASELINE.read_bytes() if baseline_bytes is None else baseline_bytes
    archive_bytes = ARCHIVE.read_bytes() if archive_bytes is None else archive_bytes
    if digest(baseline_bytes) != BASELINE_SHA256:
        raise ValueError('orientation.historical: zmieniony katalog T02 (SHA-256)')
    document = json.loads(baseline_bytes)
    plans = {p['dir_id']: p for p in document['plans']}
    originals = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('orientation.historical: powtórzone wpisy archiwum T02')
        for plan_id, plan in plans.items():
            name = f'data/caves/{plan_id}/meta.yaml'
            raw = archive.read(name)
            if digest(raw) != plan['sha256'][name]:
                raise ValueError(f'orientation.historical: {plan_id}: zmieniony YAML T02 (SHA-256)')
            originals[plan_id] = raw
    return {'plans': plans, 'originals': originals,
            'hashes': {str(BASELINE): digest(baseline_bytes), str(ARCHIVE): digest(archive_bytes)}}


@lru_cache(maxsize=1)
def default_context():
    return load_context()


def validate_metadata(meta, plan):
    north = meta.get('north')
    if not isinstance(north, dict):
        error(plan, 'north', 'wymagana mapa')
    if north.get('reference') not in REFERENCES:
        error(plan, 'north.reference', 'wymagane unknown/geographic/magnetic/grid')
    if north.get('angle_origin') not in ('measured', 'assumed', 'unknown'):
        error(plan, 'north.angle_origin', 'wymagane measured/assumed/unknown (również dla 0°)')
    if north['reference'] != 'unknown':
        text(north.get('evidence'), plan, 'north.evidence')
    declination = meta.get('declination')
    if not isinstance(declination, dict) or declination.get('status') not in ('unknown', 'documented'):
        error(plan, 'declination.status', 'wymagane unknown/documented')
    text(declination.get('basis'), plan, 'declination.basis')
    if declination['status'] == 'documented':
        value = meta.get('declination_deg')
        if type(value) not in (int, float) or not math.isfinite(value):
            error(plan, 'declination_deg', 'wymagana skończona wartość deklinacji')
        if declination.get('sign_convention') != 'east_positive':
            error(plan, 'declination.sign_convention', 'wymagana konwencja east_positive: wschodnia dodatnia')
    if north['reference'] == 'magnetic':
        if declination['status'] != 'documented':
            error(plan, 'declination.status', 'północ magnetyczna wymaga udokumentowanej deklinacji')
        text(declination.get('epoch'), plan, 'declination.epoch')
    orientation = meta.get('orientation')
    if not isinstance(orientation, dict):
        error(plan, 'orientation', 'wymagane metadane T05; brak nie uruchamia starego wzoru')
    image_hash = orientation.get('image_sha256')
    if (not isinstance(image_hash, str) or len(image_hash) != 64
            or any(c not in '0123456789abcdef' for c in image_hash)):
        error(plan, 'orientation.image_sha256', 'wymagany SHA-256 treści obrazu objętego decyzją')
    if orientation.get('status') != 'unverified':
        error(plan, 'orientation.status', 'T05 wymaga unverified; zmiana metadanych nie weryfikuje geometrii')
    text(orientation.get('uncertainty_reason'), plan, 'orientation.uncertainty_reason')
    mode = 'historical_tfw' if north['reference'] == 'unknown' else 'reference'
    if orientation.get('mode') != mode:
        error(plan, 'orientation.mode', f'wymagany tryb {mode}')


def initial_metadata(meta, context):
    plan_id = meta['cave']['dir_id']
    if plan_id not in context['plans']:
        error(plan_id, 'orientation.historical', 'brak planu w T02; wymagane jawne odniesienie przed generacją (T08)')
    return migration_metadata(yaml.safe_load(context['originals'][plan_id]), context['plans'][plan_id])


def validate_orientation(meta, context=None):
    plan = meta['cave']['dir_id']
    validate_metadata(meta, plan)
    context = default_context() if context is None else context
    initial = initial_metadata(meta, context)
    orientation = meta['orientation']
    if orientation.get('historical') != initial['orientation']['historical']:
        error(plan, 'orientation.historical', 'nie wolno odświeżać odniesienia T02')
    accepted = inputs_hash(initial)
    decisions = orientation.get('decisions')
    if not isinstance(decisions, list):
        error(plan, 'orientation.decisions', 'wymagana lista jawnych decyzji')
    for decision in decisions:
        if not isinstance(decision, dict):
            error(plan, 'orientation.decisions', 'wymagana mapa decyzji')
        for field in ('reason', 'date', 'after_sha256'):
            text(decision.get(field), plan, 'orientation.decisions.' + field)
        try:
            date.fromisoformat(decision['date'])
        except ValueError:
            error(plan, 'orientation.decisions.date', 'wymagana data YYYY-MM-DD')
        if (decision.get('before_sha256') != accepted or decision['after_sha256'] == accepted
                or len(decision['after_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in decision['after_sha256'])):
            error(plan, 'orientation.decisions', 'niespójny łańcuch decyzji przed/po')
        if decision.get('action') not in ('preserve_historical', 'establish_reference'):
            error(plan, 'orientation.decisions.action', 'wymagana jawna decyzja o orientacji')
        accepted = decision['after_sha256']
    if accepted != inputs_hash(meta):
        error(plan, 'orientation.decisions', 'zmiana wejść orientacji wymaga jawnej decyzji z uzasadnieniem')
    if decisions:
        action = 'preserve_historical' if meta['north']['reference'] == 'unknown' else 'establish_reference'
        if decisions[-1]['action'] != action:
            error(plan, 'orientation.decisions.action', 'decyzja nie odpowiada rodzajowi północy')
    return context


def historical_rotation(meta, context=None):
    context = validate_orientation(meta, context)
    reference = meta['north']['reference']
    if reference != 'unknown':
        error(meta['cave']['dir_id'], 'north.reference', f'brak modelu obliczeń dla {reference}; wymagany T06')
    params = context['plans'][meta['cave']['dir_id']]['historical_tfw']['parameters']
    return math.degrees(math.atan2(params['D'], params['A']))


def rotation(meta, context=None):
    """Obrót osi x obrazu ku północy siatki (CCW), w stopniach.

    Strzałka w obrazie: (sin α, -cos α). Po transformacji ma azymut
    siatkowy α-r. Północ geograficzna ma azymut -γ, magnetyczna δ-γ.
    Stąd r=α+γ (geographic), r=α+γ-δ (magnetic), r=α (grid).
    γ to zbieżność PROJ, δ to udokumentowana deklinacja east_positive.
    """
    if meta.get('north', {}).get('reference') == 'unknown':
        return historical_rotation(meta, context)
    validate_orientation(meta, context)
    reference = meta['north']['reference']
    angle = meta['north']['angle_deg']
    if reference == 'grid':
        return angle  # EPSG:2180: żadnej ponownej poprawki zbieżności/deklinacji.
    coordinates = meta['coordinates']
    convergence = PROJECTION.get_factors(
        float(coordinates['lon']), float(coordinates['lat']), errcheck=True).meridian_convergence
    if not math.isfinite(convergence):
        error(meta['cave']['dir_id'], 'north', 'nieskończona zbieżność EPSG:2180')
    declination = meta['declination_deg'] if reference == 'magnetic' else 0.0
    return angle + convergence - declination


def summary(meta):
    """Ten sam status i powód dla QA, computed i manifestu."""
    return {'north_reference': meta['north']['reference'], 'angle_origin': meta['north']['angle_origin'],
            'north': copy.deepcopy(meta['north']), 'declination': copy.deepcopy(meta['declination']),
            'declination_deg': meta['declination_deg'],
            **copy.deepcopy(meta['orientation'])}


def record_decision(meta, reason, decision_date, context=None):
    """Jawny krok operatora po edycji wejść; nigdy nie odświeża historycznego TFW."""
    context = default_context() if context is None else context
    text(reason, meta['cave']['dir_id'], 'orientation.decisions.reason')
    result = copy.deepcopy(meta)
    orientation = result['orientation']
    orientation['mode'] = 'historical_tfw' if result['north']['reference'] == 'unknown' else 'reference'
    initial = initial_metadata(result, context)
    before = (orientation['decisions'][-1]['after_sha256'] if orientation['decisions'] else inputs_hash(initial))
    orientation['decisions'].append({'before_sha256': before, 'after_sha256': inputs_hash(result),
                                     'action': 'preserve_historical' if orientation['mode'] == 'historical_tfw' else 'establish_reference',
                                     'reason': reason, 'date': decision_date})
    validate_orientation(result, context)
    return result


def main():
    parser = argparse.ArgumentParser(description='Jawne zatwierdzenie edycji orientacji; nie potwierdza geometrii')
    parser.add_argument('command', choices=['decide'])
    parser.add_argument('--meta', type=Path, required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--date', required=True, help='Data decyzji YYYY-MM-DD')
    args = parser.parse_args()
    from validation import UniqueLoader, finite_numbers
    meta = yaml.load(args.meta.read_text(encoding='utf-8'), Loader=UniqueLoader)
    finite_numbers(meta, args.meta.parent.name)
    result = record_decision(meta, args.reason, args.date)
    args.meta.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding='utf-8')


if __name__ == '__main__':
    main()
