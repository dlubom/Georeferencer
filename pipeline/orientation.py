"""Modele północy i zachowane kąty planów z nieustaloną północą."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from functools import lru_cache

from pyproj import Proj

from coordinate_source import ROOT

BASELINE = ROOT / 'data/baseline/2026-10-24/catalogue.json'
REFERENCES = ('unknown', 'geographic', 'magnetic', 'grid')
PROJECTION = Proj('EPSG:2180')
GRID_CONVENTION = 'image_x_ccw_from_grid_east'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def error(plan, field, rule):
    raise ValueError(f'plan {plan}: {field}: {rule}')


def text(value, plan, field):
    if not isinstance(value, str) or not value.strip():
        error(plan, field, 'wymagany niepusty tekst')


def load_context(baseline_bytes=None):
    """Katalog jest zwykłym źródłem kątów; hash służy aktualności buildu."""
    raw = BASELINE.read_bytes() if baseline_bytes is None else baseline_bytes
    document = json.loads(raw)
    return {'plans': {p['dir_id']: p for p in document['plans']},
            'hashes': {str(BASELINE): digest(raw)}}


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
    mode = orientation_mode(meta)
    if orientation.get('mode') != mode:
        error(plan, 'orientation.mode', f'wymagany tryb {mode}')


def orientation_mode(meta):
    if meta['north']['reference'] != 'unknown':
        return 'reference'
    return 'assumed_grid' if 'grid_assumption' in meta.get('orientation', {}) else 'historical_tfw'


def validate_orientation(meta, context=None):
    plan = meta['cave']['dir_id']
    validate_metadata(meta, plan)
    if meta['orientation']['mode'] == 'assumed_grid':
        assumption = meta['orientation']['grid_assumption']
        if not isinstance(assumption, dict):
            error(plan, 'orientation.grid_assumption', 'wymagana mapa')
        value = assumption.get('rotation_deg')
        if type(value) not in (float, int) or not math.isfinite(value):
            error(plan, 'orientation.grid_assumption.rotation_deg', 'wymagany skończony kąt obrotu')
        if assumption.get('crs') != 'EPSG:2180' or assumption.get('convention') != GRID_CONVENTION:
            error(plan, 'orientation.grid_assumption', 'wymagane EPSG:2180 i image_x_ccw_from_grid_east')


def historical_rotation(meta, context=None):
    context = default_context() if context is None else context
    plan = meta['cave']['dir_id']
    if plan not in context['plans']:
        error(plan, 'orientation.mode', 'brak zapisanego kąta; podaj grid_assumption lub rodzaj północy')
    params = context['plans'][plan]['historical_tfw']['parameters']
    a, d = params['A'], params['D']
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (a, d)) or (a == 0 and d == 0):
        error(plan, 'historical_tfw', 'wymagany skończony, niezerowy wektor (A, D)')
    return math.degrees(math.atan2(d, a))


def rotation(meta, context=None):
    """Obrót osi x obrazu ku północy siatki (CCW), w stopniach.

    Strzałka w obrazie: (sin α, -cos α). Po transformacji ma azymut
    siatkowy α-r. Północ geograficzna ma azymut -γ, magnetyczna δ-γ.
    Stąd r=α+γ (geographic), r=α+γ-δ (magnetic), r=α (grid).
    γ to zbieżność PROJ, δ to udokumentowana deklinacja east_positive.
    """
    validate_orientation(meta, context)
    if meta['north']['reference'] == 'unknown':
        if meta['orientation']['mode'] == 'assumed_grid':
            return meta['orientation']['grid_assumption']['rotation_deg']
        return historical_rotation(meta, context)
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
