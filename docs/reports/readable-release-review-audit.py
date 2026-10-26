"""Reviewer-owned historical ZIP-name and byte-identity audit.

No release_layout, package_release, release_acceptance or author's inventory helper.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import stat
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path

import pyproj
import yaml


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_json(raw):
    def pairs(items):
        output = {}
        for name, value in items:
            require(name not in output, f'duplicate JSON key: {name}')
            output[name] = value
        return output
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def collision_key(name):
    return unicodedata.normalize('NFC', name.casefold())


def inspect_raw(info):
    name = info.orig_filename
    require(isinstance(name, str) and bool(name), 'empty raw ZipInfo name')
    require(name == info.filename, 'ZipInfo name truncation')
    require(not name.startswith('/'), f'absolute raw member: {name!r}')
    require(not info.is_dir() and not (info.external_attr & 0x10), f'directory member: {name!r}')
    require(stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG), f'special file: {name!r}')
    require(not (info.flag_bits & 1), f'encrypted member: {name!r}')
    for component in name.split('/'):
        require(component and component not in ('.', '..'), f'unsafe component: {name!r}')
        require(component[-1] not in (' ', '.'), f'trailing reserved character: {name!r}')
        require(len(component.encode('utf-8')) <= 255, f'oversize component: {name!r}')
        require(not any(char in '\\:<>|?*"' or unicodedata.category(char)[0] == 'C'
                        for char in component), f'reserved/control character: {name!r}')
        require(not re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',
                                 component, re.I), f'reserved DOS name: {name!r}')


def historical_text(value):
    require(isinstance(value, str) and bool(value.strip()), 'historical source must be nonempty text')
    # Direct equivalent of historical tr ' /' '__' | tr -d "'\"".
    output = ''
    for character in value:
        if character in "'\"":
            continue
        output += '_' if character in (' ', '/') else character
    return output


def audit(run, tag, manual, data):
    run_raw = (run / 'manifest.json').read_bytes()
    run_manifest = unique_json(run_raw)
    plans = run_manifest['plans']
    require(isinstance(plans, list) and bool(plans), 'empty catalogue')
    ids = [plan['dir_id'] for plan in plans]
    require(len(ids) == len(set(ids)), 'duplicate run plan ID')
    source_ids = {p.name for p in data.iterdir() if p.is_dir() and not p.name.startswith(('.', '_'))}
    require(set(ids) == source_ids, 'run differs from versioned source catalogue')
    outputs = ('computed.json', 'image.tfw', 'image_georef.tif')
    rows, historical_names = [], []
    for plan in sorted(plans, key=lambda item: item['dir_id']):
        plan_id = plan['dir_id']
        require('/' not in plan_id and '\\' not in plan_id and plan_id not in ('', '.', '..'), 'unsafe plan ID')
        meta_raw = (data / plan_id / 'meta.yaml').read_bytes()
        require(digest(meta_raw) == plan['inputs']['meta.yaml'], f'YAML source hash: {plan_id}')
        cave = yaml.safe_load(meta_raw)['cave']
        root_name = f"{plan_id}_{historical_text(cave['inventory_number'])}_{historical_text(cave['name'])}.tif"
        require('/' not in root_name, f'TIFF is not at root: {plan_id}')
        historical_names.append({'plan_id': plan_id, 'archive_path': root_name, 'meta_yaml_sha256': digest(meta_raw)})
        require(set(plan['outputs']) == set(outputs), f'wrong output set: {plan_id}')
        for output in outputs:
            member = root_name if output == 'image_georef.tif' else f'metadane/{plan_id}/{output}'
            original = run / plan_id / output
            require(not original.is_symlink() and original.is_file(), f'not a regular run output: {original}')
            require(digest(original.read_bytes()) == plan['outputs'][output], f'run output hash: {original}')
            rows.append({'plan_id': plan_id, 'output': output, 'archive_path': member,
                         'sha256': plan['outputs'][output]})
    expected_names = ['manifest.json'] + [row['archive_path'] for row in rows]
    require(len(expected_names) == 1 + 3 * len(plans), 'wrong expected entry count')
    require(len(expected_names) == len({collision_key(name) for name in expected_names}), 'expected name collision')
    expected_run_files = {'manifest.json'} | {f"{row['plan_id']}/{row['output']}" for row in rows}
    run_paths = list(run.rglob('*'))
    require(not any(path.is_symlink() for path in run_paths), 'run contains a symlink')
    require({str(path.relative_to(run)) for path in run_paths if path.is_file()} == expected_run_files,
            'run has missing or extra files')
    results = []
    for mode, archive_path in [('tag', tag), ('manual', manual)]:
        archive_digest_before = digest(archive_path.read_bytes())
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            # Complete pass over every raw ZipInfo before a name set or lookup exists.
            for info in infos:
                inspect_raw(info)
            actual_names = [info.filename for info in infos]
            require(len(actual_names) == len(set(actual_names)), f'{mode}: duplicate raw names')
            require(len(actual_names) == len({collision_key(name) for name in actual_names}), f'{mode}: NFC/casefold collision')
            require(len(infos) == len(expected_names) and set(actual_names) == set(expected_names), f'{mode}: exact inventory')
            require(archive.testzip() is None, f'{mode}: CRC failure')
            archive_manifest = unique_json(archive.read('manifest.json'))
            release = archive_manifest.pop('release')
            require(archive_manifest == run_manifest, f'{mode}: original run manifest changed')
            require(release['version'] == 't11-v2' and release['mode'] == mode, f'{mode}: release contract/mode')
            require(release['run_id'] == run_manifest['run_id'], f'{mode}: run ID')
            require(release['run_manifest_sha256'] == digest(run_raw), f'{mode}: manifest binding')
            require(release['files'] == rows, f'{mode}: complete independently derived mapping')
            by_name = {info.filename: info for info in infos}
            for row in rows:
                payload = archive.read(by_name[row['archive_path']])
                original = (run / row['plan_id'] / row['output']).read_bytes()
                require(payload == original, f"{mode}: byte mismatch: {row['archive_path']}")
                require(digest(payload) == row['sha256'], f"{mode}: output digest: {row['archive_path']}")
            require(sum('/' not in name and name.endswith('.tif') for name in actual_names) == len(plans), f'{mode}: TIFF root count')
        require(digest(archive_path.read_bytes()) == archive_digest_before, f'{mode}: archive changed during inspection')
        results.append({'mode': mode, 'archive': str(archive_path), 'archive_sha256': archive_digest_before,
                        'archive_bytes': archive_path.stat().st_size, 'raw_zipinfos': len(infos),
                        'validated_before_lookup': True, 'crc': 'PASS', 'exact_inventory': 'PASS',
                        'all_historical_names': 'PASS', 'tiffs_at_root': len(plans),
                        'identical_output_bytes': len(rows), 'output_sha256': 'PASS', 'run_manifest_identical': True})
    require((run / 'manifest.json').read_bytes() == run_raw, 'run manifest changed during audit')
    environment = {'system': platform.system(), 'architecture': platform.machine(), 'Python': platform.python_version(),
                   'GDAL': subprocess.check_output(['gdalinfo', '--version'], text=True).strip(),
                   'GDAL build': subprocess.check_output(['gdalinfo', '--build'], text=True).strip(),
                   'PROJ (pyproj)': pyproj.proj_version_str,
                   'packages': dict(sorted((dist.metadata['Name'], dist.version) for dist in importlib.metadata.distributions()))}
    return {'schema_version': 1, 'passed': True, 'audit_implementation': 'reviewer-owned; no release layout helpers',
            'argv': sys.argv, 'run_path': str(run), 'run_id': run_manifest['run_id'],
            'run_manifest_sha256': digest(run_raw), 'plans': len(plans), 'outputs': len(rows),
            'generated': len(run_manifest['build']['generated']), 'reused': len(run_manifest['build']['reused']),
            'code': run_manifest['code'], 'environment': environment,
            'archives': results, 'historical_names': historical_names, 'files': rows}


parser = argparse.ArgumentParser()
parser.add_argument('--run', type=Path, required=True)
parser.add_argument('--tag', type=Path, required=True)
parser.add_argument('--manual', type=Path, required=True)
parser.add_argument('--data', type=Path, default=Path('/workspace/data/caves'))
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
report = audit(args.run, args.tag, args.manual, args.data)
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
print(json.dumps({key: value for key, value in report.items() if key not in ('historical_names', 'files', 'environment')},
                 ensure_ascii=False, indent=2, sort_keys=True))
