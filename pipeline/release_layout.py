"""Wersjonowany układ ZIP; bez zmiany nazw ani manifestu przebiegu T04."""
import hashlib
import re
import unicodedata
from pathlib import Path

import yaml

from geotiff_output import OUTPUTS
from validation import UniqueLoader

RELEASE_VERSION = 't11-v2'
SUPPORTED_VERSIONS = ('t11-v1', RELEASE_VERSION)


def path_key(path):
    """Klucz kolizji także dla systemów bez rozróżniania case/Unicode."""
    return unicodedata.normalize('NFC', path.casefold())


def check_path(path):
    if not isinstance(path, str) or not path or path.startswith('/'):
        raise ValueError(f'ZIP: niebezpieczna ścieżka: {path!r}')
    for part in path.split('/'):
        if (not part or part in ('.', '..') or part.endswith((' ', '.'))
                or len(part.encode('utf-8')) > 255
                or any(c in '\\:<>|?*"' or unicodedata.category(c).startswith('C') for c in part)
                or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)):
            raise ValueError(f'ZIP: niebezpieczna ścieżka: {path!r}')
    return path


def geotiff_name(plan_id, cave):
    values = []
    for field in ('inventory_number', 'name'):
        value = cave.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'plan {plan_id}: cave.{field}: wymagany niepusty tekst')
        # Historyczne / jest separatorem prezentacji; traversal i znaki
        # sterujące nigdy nie są naprawiane przez normalizację.
        if (value.startswith('/') or any(p in ('.', '..') for p in value.split('/'))
                or any(c in '\\:<>|?*' or unicodedata.category(c).startswith('C') for c in value)):
            raise ValueError(f'plan {plan_id}: cave.{field}: niebezpieczna ścieżka')
        safe = value.translate(str.maketrans({' ': '_', '/': '_', "'": '', '"': ''}))
        if not safe.strip('_'):
            raise ValueError(f'plan {plan_id}: cave.{field}: pusta nazwa po normalizacji')
        values.append(safe)
    try:
        return check_path(f'{plan_id}_{values[0]}_{values[1]}.tif')
    except ValueError as exc:
        raise ValueError(f'plan {plan_id}: cave.inventory_number/name: {exc}') from exc


def files_for_release(manifest, data_dir, *, version=RELEASE_VERSION):
    """Oczekiwane relacje odtworzone ze źródeł, nigdy z deklaracji ZIP."""
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f'ZIP: nieznana wersja kontraktu: {version!r}')
    plans = manifest.get('plans')
    if not isinstance(plans, list) or not plans:
        raise ValueError('ZIP: wymagany niepusty katalog planów')
    files, ids, paths = [], set(), {path_key('manifest.json')}
    for plan in plans:
        plan_id = plan['dir_id']
        check_path(plan_id)
        if '/' in plan_id:
            raise ValueError(f'ZIP: niepoprawna ścieżka planu: {plan_id!r}')
        key = path_key(plan_id)
        if key in ids:
            raise ValueError(f'ZIP: kolizja/powtórzony identyfikator planu: {plan_id}')
        ids.add(key)
        outputs = plan['outputs']
        if not isinstance(outputs, dict) or set(outputs) != OUTPUTS:
            raise ValueError(f'plan {plan_id}: niepoprawny komplet wyników')
        filename = None
        if version == RELEASE_VERSION:
            raw = (Path(data_dir) / plan_id / 'meta.yaml').read_bytes()
            if hashlib.sha256(raw).hexdigest() != plan['inputs']['meta.yaml']:
                raise ValueError(f'plan {plan_id}: meta.yaml: hash metadanych niezgodny z przebiegiem')
            try:
                metadata = yaml.load(raw, Loader=UniqueLoader)
                cave = metadata['cave']
                if not isinstance(cave, dict):
                    raise ValueError('wymagana mapa cave')
                filename = geotiff_name(plan_id, cave)
            except (KeyError, TypeError, RecursionError, yaml.YAMLError) as exc:
                raise ValueError(f'plan {plan_id}: meta.yaml: niepoprawne metadane: {exc}') from exc
        for output, digest in sorted(outputs.items()):
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError(f'plan {plan_id}: {output}: wymagany SHA-256')
            path = (plan_id + '/' + output if version == 't11-v1' else
                    filename if output == 'image_georef.tif' else f'metadane/{plan_id}/{output}')
            check_path(path)
            key = path_key(path)
            if key in paths:
                raise ValueError(f'ZIP: kolizja nazw po normalizacji: {path}')
            paths.add(key)
            files.append({'plan_id': plan_id, 'output': output, 'archive_path': path, 'sha256': digest})
    return sorted(files, key=lambda item: (item['plan_id'], item['output']))
