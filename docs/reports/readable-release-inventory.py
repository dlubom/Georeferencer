"""Osobny od pakowania audyt wszystkich nazw, wpisów i bajtów gotowych ZIP.

Przykład: python docs/reports/readable-release-inventory.py --run-dir RUN
  --archive tag.zip --archive manual.zip --report inventory.json
Pełny odczyt GDAL/Pillow i bieżące wyjątki egzekwuje dodatkowo accept verify.
"""
import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(run_dir, archives, data_dir):
    run = Path(run_dir).resolve(strict=True)
    run_raw = (run / 'manifest.json').read_bytes()
    run_manifest = json.loads(run_raw)
    expected = []
    for plan in run_manifest['plans']:
        plan_id = plan['dir_id']
        raw = (Path(data_dir) / plan_id / 'meta.yaml').read_bytes()
        if digest(raw) != plan['inputs']['meta.yaml']:
            raise ValueError(f'{plan_id}: metadane niezgodne z manifestem przebiegu')
        cave = yaml.safe_load(raw)['cave']
        # Osobne od release_layout odtworzenie tr/echo z workflow v0.6.2.
        inventory = cave['inventory_number'].replace(' ', '_').replace('/', '_').replace("'", '').replace('"', '')
        name = cave['name'].replace(' ', '_').replace('/', '_').replace("'", '').replace('"', '')
        for output in sorted(plan['outputs']):
            member = (f'{plan_id}_{inventory}_{name}.tif' if output == 'image_georef.tif'
                      else f'metadane/{plan_id}/{output}')
            expected.append({'plan_id': plan_id, 'output': output, 'archive_path': member,
                             'sha256': plan['outputs'][output]})
    expected.sort(key=lambda f: (f['plan_id'], f['output']))
    names = ['manifest.json', *(f['archive_path'] for f in expected)]
    if len(names) != len(set(names)):
        raise ValueError('Kolizja oczekiwanych nazw')
    results = []
    for archive_path in archives:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            for info in infos:
                path = info.filename
                if (path.startswith('/') or '\\' in path or '..' in path.split('/')
                        or info.is_dir() or stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG)
                        or info.external_attr & 0x10):
                    raise ValueError(f'Niebezpieczne ZipInfo: {path}')
            actual = [i.filename for i in infos]
            if len(actual) != len(set(actual)) or len(actual) != len(names) or set(actual) != set(names):
                raise ValueError('Niezgodny komplet ZIP')
            if archive.testzip() is not None:
                raise ValueError('Błąd CRC')
            manifest = json.loads(archive.read('manifest.json'))
            release = manifest.pop('release')
            if (release['version'] != 't11-v2' or release['files'] != expected
                    or release['run_manifest_sha256'] != digest(run_raw) or manifest != run_manifest):
                raise ValueError('Niezgodne mapowanie/manifest przebiegu')
            for item in expected:
                payload = archive.read(item['archive_path'])
                original = (run / item['plan_id'] / item['output']).read_bytes()
                if payload != original or digest(payload) != item['sha256']:
                    raise ValueError(f"Niezgodne bajty: {item['archive_path']}")
            results.append({'archive': str(archive_path), 'sha256': digest(Path(archive_path).read_bytes()),
                'mode': release['mode'], 'bytes': Path(archive_path).stat().st_size,
                'entries': len(infos), 'tiffs_at_root': sum(n.endswith('.tif') and '/' not in n for n in actual),
                'crc': 'PASS', 'exact_inventory': 'PASS', 'all_historical_names': 'PASS',
                'identical_output_bytes': len(expected), 'run_binding': 'PASS'})
    return {'schema_version': 1, 'passed': True, 'run_id': run_manifest['run_id'],
            'run_manifest_sha256': digest(run_raw), 'plans': len(run_manifest['plans']),
            'archives': results, 'files': expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/caves')
    parser.add_argument('--archive', type=Path, action='append', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = args.report.resolve()
    for protected in (args.run_dir, args.data_dir, *args.archive):
        source = protected.resolve()
        if report == source or source in report.parents:
            raise ValueError('Raport musi leżeć poza źródłami, przebiegiem i archiwami')
    if ROOT in report.parents and ROOT / 'build' not in report.parents:
        raise ValueError('Raport w repozytorium zapisuj w ignorowanym build/')
    result = audit(args.run_dir, args.archive, args.data_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
