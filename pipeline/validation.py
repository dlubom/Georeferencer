"""Kontrakt wejść v1; odczyt i walidacja bez renderowania dowolnego Jinja i bez zapisu."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import yaml
from PIL import Image

from coordinate_source import ROOT, sha256
from gps_kataster_coordinates import LAT_TEMPLATE, LON_TEMPLATE
from orientation import validate_metadata, validate_orientation

SCHEMA = json.loads(Path(__file__).with_name('meta-schema-v1.json').read_text())
IMAGE_REGISTRY = ROOT / 'data/validation/images-v1.json'
Image.MAX_IMAGE_PIXELS = None


class ValidationError(ValueError):
    """Diagnostyka ma postać plan / pole / naruszona reguła."""


def fail(plan, field, rule):
    raise ValidationError(f'plan {plan}: {field}: {rule}')


class UniqueLoader(yaml.SafeLoader):
    """Nie pozwól, by powtórzone pole YAML po cichu zastąpiło wcześniejsze."""

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError(f'powtórzony klucz {key}')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def finite_numbers(value, plan, field='meta', ancestors=None):
    if isinstance(value, float) and not math.isfinite(value):
        fail(plan, field, 'wymagana skończona liczba')
    if not isinstance(value, (dict, list)):
        if value is not None and type(value) not in (str, bool, int, float):
            fail(plan, field, 'dozwolone mapy, listy i wartości skalarne; bez zbiorów i tagów specjalnych')
        return
    ancestors = set() if ancestors is None else ancestors
    identity = id(value)
    if identity in ancestors:
        fail(plan, field, 'cykliczne aliasy YAML są niedozwolone')
    ancestors.add(identity)
    try:
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    fail(plan, field, 'klucze metadanych muszą być tekstowe')
                finite_numbers(item, plan, str(key) if field == 'meta' else f'{field}.{key}', ancestors)
        else:
            for i, item in enumerate(value):
                finite_numbers(item, plan, f'{field}[{i}]', ancestors)
    finally:
        ancestors.remove(identity)


def validate_meta(meta, plan):
    if not isinstance(meta, dict):
        fail(plan, 'meta', 'wymagana mapa YAML')
    finite_numbers(meta, plan)
    for field, rule in SCHEMA['fields'].items():
        value = meta
        for key in field.split('.'):
            if not isinstance(value, dict) or key not in value:
                if rule.get('optional'):
                    break
                fail(plan, field, 'wymagane pole')
            value = value[key]
        else:
            kind = rule['type']
            number = type(value) in (int, float)
            valid = {'object': isinstance(value, dict), 'string': isinstance(value, str) and bool(value.strip()),
                     'integer': type(value) is int, 'number': number,
                     'boolean': type(value) is bool,
                     'coordinate': number or isinstance(value, str)}[kind]
            if not valid:
                fail(plan, field, f'wymagany typ {kind}')
            if number:
                try:
                    finite = math.isfinite(value)
                except OverflowError:
                    finite = False
                if not finite:
                    fail(plan, field, 'wymagana skończona liczba')
                if (('min' in rule and value < rule['min'])
                        or ('max' in rule and value > rule['max'])):
                    fail(plan, field, f'zakres [{rule.get("min")}, {rule.get("max")}]')
                if 'exclusive_min' in rule and value <= rule['exclusive_min']:
                    fail(plan, field, 'wymagana skala > 0')
    if meta['cave']['dir_id'] != plan:
        fail(plan, 'cave.dir_id', 'identyfikator musi odpowiadać katalogowi planu')
    for axis, dimension in (('x', 'width'), ('y', 'height')):
        if meta['entrance'][axis] >= meta['image'][dimension]:
            fail(plan, 'entrance.' + axis, f'kliknięcie musi być w obrazie: 0 <= {axis} < {dimension}')

    validate_metadata(meta, plan)


def resolve_coordinates(meta, index, plan):
    coordinates = meta['coordinates']
    object_id = coordinates['gps_kataster_object_id']
    if index is None or object_id not in index.by_object_id:
        fail(plan, 'coordinates.gps_kataster_object_id',
             f'{object_id}: wymagany istniejący obiekt kategorii jaskinia_otwor lub sztolnia')
    row = index.by_object_id[object_id]
    result = copy.deepcopy(meta)
    for axis, canonical in (('lat', LAT_TEMPLATE), ('lon', LON_TEMPLATE)):
        value = coordinates[axis]
        expected = getattr(row, axis)
        if isinstance(value, str):
            if value != canonical:
                fail(plan, 'coordinates.' + axis, 'dozwolony wyłącznie kanoniczny szablon jawnego object_id')
        elif value != expected:
            fail(plan, 'coordinates.' + axis, f'liczba sprzeczna z katalogiem obiektu {object_id}')
        result['coordinates'][axis] = expected
    if 'gps_kataster' in coordinates or 'gps_kataster' in meta:
        fail(plan, 'coordinates.gps_kataster_object_id', 'usuń niejednoznaczne dawne powiązanie gps_kataster')
    return result


def read_registry(path=IMAGE_REGISTRY):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_image(meta, cave_dir, registry):
    plan = cave_dir.name
    if (not isinstance(registry, dict)
            or type(registry.get('schema_version')) is not int
            or registry.get('schema_version') != SCHEMA['schema_version']):
        fail(plan, 'image.schema_version', 'nieobsługiwana wersja rejestru obrazów')
    plans = registry.get('plans')
    if not isinstance(plans, dict):
        fail(plan, 'image.plans', 'rejestr musi zawierać mapę planów')
    identity = plans.get(plan)
    if not isinstance(identity, dict):
        fail(plan, 'image', 'brak zadeklarowanej tożsamości w rejestrze obrazów')
    for field in ('filename', 'image_id', 'width', 'height'):
        if identity.get(field) != meta['image'][field]:
            fail(plan, 'image.' + field, 'niezgodność z zadeklarowanym wejściem w rejestrze obrazów')
    path = cave_dir / 'image.tif'
    try:
        with Image.open(path) as image:
            if image.format != 'TIFF':
                fail(plan, 'image.format', 'wymagany TIFF')
            if image.size != (meta['image']['width'], meta['image']['height']):
                fail(plan, 'image.width/height', 'obraz ma inną rozdzielczość niż kliki')
            if image.mode != '1' or getattr(image, 'n_frames', 1) != 1:
                fail(plan, 'image.mode', 'CCITTFAX4 wymaga pojedynczego obrazu 1-bit (tryb 1)')
            image.load()
        if sha256(path) != identity.get('sha256'):
            fail(plan, 'image.sha256', 'podmieniony obraz; hash inny niż zadeklarowane wejście')
        if meta['orientation']['image_sha256'] != identity.get('sha256'):
            fail(plan, 'orientation.image_sha256', 'zmiana treści obrazu wymaga jawnego hasha i decyzji orientacji')
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        fail(plan, 'image', f'wymagany dostępny i czytelny TIFF: {exc}')


def validate_plan(cave_dir, index, image_registry=None, meta_text=None, orientation_context=None):
    """Zwróć (oryginalne metadane, kopia z liczbami z katalogu), niczego nie zapisuj."""
    cave_dir = Path(cave_dir)
    try:
        text = (cave_dir / 'meta.yaml').read_text(encoding='utf-8') if meta_text is None else meta_text
        meta = yaml.load(text, Loader=UniqueLoader)
        validate_meta(meta, cave_dir.name)
        resolved = resolve_coordinates(meta, index, cave_dir.name)
        validate_image(meta, cave_dir, read_registry() if image_registry is None else image_registry)
        validate_orientation(resolved, orientation_context)
        return meta, resolved
    except ValidationError:
        raise
    except (OSError, ValueError, TypeError, RecursionError, yaml.YAMLError) as exc:
        fail(cave_dir.name, 'meta/image', f'niepoprawne wejście: {exc}')
