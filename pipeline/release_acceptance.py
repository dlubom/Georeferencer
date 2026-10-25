"""T11: niezależny od zapisu odbiór ZIP i porównanie rzeczywistych wyników."""
import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from coordinate_source import ROOT, sha256
from geotiff_output import read_json, write_json, check_geotiff, tfw_geotransform, guard_input_path
import build_identity
import orientation
from qa import create_report

RELEASE_VERSION = 't11-v1'


def qa_evidence(report):
    paths = [ROOT / 'parquet/SUBMISSIONS.parquet',
             *sorted((ROOT / 'data/qa').glob('*.json')),
             *sorted((ROOT / 'data/classification').glob('*.json'))]
    return {'policy': report['policy'], 'counts': report['counts'],
            'accepted_exceptions': [p['exception'] for p in report['problems'] if p['accepted']],
            'sources_sha256': {str(p.relative_to(ROOT)): sha256(p) for p in paths}}


def verify_archive(archive, data_dir=ROOT / 'data/caves', *, qa_kwargs=None):
    """Nigdy nie dopuszcza wyjątków zadeklarowanych wyłącznie w archiwum.

    ZipInfo sprawdzamy przed mapowaniem nazw i przed zapisem. Nie używamy
    extractall ani namelist->set, które mogłyby zgubić duplikaty.
    """
    try:
        with zipfile.ZipFile(archive) as package, tempfile.TemporaryDirectory(prefix='t11-zip-') as temporary:
            entries = package.infolist()
            names = [i.filename for i in entries]
            if len(names) != len(set(names)) or names.count('manifest.json') != 1:
                raise ValueError('ZIP: powtórzone pliki albo brak manifestu')
            run = Path(temporary)
            (run / 'manifest.json').write_bytes(package.read('manifest.json'))
            manifest = read_json(run / 'manifest.json')
            release = manifest.pop('release')
            if (release['version'] != RELEASE_VERSION or release['mode'] not in ('tag', 'manual')
                    or release['run_id'] != manifest['run_id']):
                raise ValueError('ZIP: niepoprawny kontrakt wydania/przebiegu')
            # Oryginalny manifest ma jednoznaczny serializer T04.
            write_json(run / 'manifest.json', manifest)
            if sha256(run / 'manifest.json') != release['run_manifest_sha256']:
                raise ValueError('ZIP: niespójne powiązanie z manifestem przebiegu')
            expected = {'manifest.json'}
            ids = []
            for plan in manifest['plans']:
                plan_id = plan['dir_id']
                if not isinstance(plan_id, str) or not plan_id or Path(plan_id).name != plan_id or plan_id in ('.', '..'):
                    raise ValueError('ZIP: niepoprawna ścieżka planu')
                ids.append(plan_id)
                if set(plan['outputs']) != {'image.tfw', 'image_georef.tif', 'computed.json'}:
                    raise ValueError('ZIP: niepoprawny komplet wyników planu')
                expected.update(plan_id + '/' + name for name in plan['outputs'])
            if len(ids) != len(set(ids)) or set(names) != expected:
                raise ValueError('ZIP: brakujące, dodatkowe lub powtórzone wyniki')
            for entry in entries:
                if entry.is_dir() or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('ZIP: niedozwolony katalog/dowiązanie')
                if entry.filename == 'manifest.json':
                    continue
                target = run / entry.filename
                if run not in target.resolve().parents:
                    raise ValueError('ZIP: ścieżka poza katalogiem prywatnym')
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(package.read(entry))  # odczyt strumienia i CRC każdego ZipInfo
            # T09 ponownie sprawdza cały katalog, hashe, rzeczywisty GDAL/Pillow
            # oraz aktualny rejestr wyjątków. Manifest nie udziela dopuszczenia.
            report = create_report(data_dir, run_dir=run, require_results=True, **(qa_kwargs or {}))
            if not report['passed'] or release['qa'] != qa_evidence(report):
                raise ValueError('ZIP: QA blokuje wydanie lub dowody wyjątków są nieaktualne')
            return {'passed': True, 'files': len(entries), 'plans': len(ids),
                    'archive_sha256': sha256(archive), 'run_id': manifest['run_id'],
                    'run_manifest_sha256': release['run_manifest_sha256'], 'qa': report['counts']}
    except (OSError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError(f'ZIP: błąd odbioru: {exc}') from exc


def compare_runs(left, right, data_dir=ROOT / 'data/caves', *, qa_kwargs=None):
    """TFW bajtowo, rzeczywista geometria i zdekodowane piksele każdego planu."""
    runs = [Path(p).resolve(strict=True) for p in (left, right)]
    manifests, reports = [], []
    for run in runs:
        report = create_report(data_dir, run_dir=run, require_results=True, **(qa_kwargs or {}))
        if not report['passed']:
            raise ValueError('Porównanie: pełne QA przebiegu nie przeszło')
        reports.append(report)
        manifests.append(read_json(run / 'manifest.json'))
    if manifests[0].get('code') != manifests[1].get('code'):
        raise ValueError('Porównanie: różne wersje kodu')
    records = [{p['dir_id']: p for p in m['plans']} for m in manifests]
    if set(records[0]) != set(records[1]):
        raise ValueError('Porównanie: różne katalogi')
    comparisons = []
    for plan_id in sorted(records[0]):
        paths = [run / plan_id for run in runs]
        tfws = [(p / 'image.tfw').read_bytes() for p in paths]
        if tfws[0] != tfws[1]:
            raise ValueError(f'Porównanie: różny TFW {plan_id}')
        actual = [check_geotiff(Path(data_dir) / plan_id / 'image.tif', p / 'image_georef.tif',
                               tfw_geotransform(p / 'image.tfw')) for p in paths]
        if actual[0] != actual[1]:
            raise ValueError(f'Porównanie: różna geometria/piksele {plan_id}')
        if records[0][plan_id]['fingerprint'] != records[1][plan_id]['fingerprint']:
            raise ValueError(f'Porównanie: różne wejścia {plan_id}')
        comparisons.append({'plan_id': plan_id, 'tfw_sha256': hashlib.sha256(tfws[0]).hexdigest(),
                            'fingerprint': records[0][plan_id]['fingerprint'], **actual[0]})
    return {'schema_version': 1, 'passed': True, 'plans': len(comparisons),
            'code': manifests[0].get('code'), 'environment': manifests[0]['environment'],
            'coordinate_source': manifests[0]['coordinate_source'],
            'builds': [{'run_id': m['run_id'], 'manifest_sha256': sha256(r / 'manifest.json'),
                        'generated': len(m['build']['generated']), 'reused': len(m['build']['reused']),
                        'qa': q['counts']} for m, r, q in zip(manifests, runs, reports)],
            'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description='Odbiór ZIP albo porównanie pełnych wyników, bez publikacji')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/caves')
    sub = parser.add_subparsers(dest='operation', required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--archive', type=Path, required=True)
    compare = sub.add_parser('compare')
    compare.add_argument('--left', type=Path, required=True)
    compare.add_argument('--right', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (verify_archive(args.archive, args.data_dir) if args.operation == 'verify' else
                  compare_runs(args.left, args.right, args.data_dir))
        # Odbiorca wskazuje raport poza niezmiennymi przebiegami.
        if any((p / 'manifest.json').is_file() for p in args.report.resolve().parents):
            raise ValueError('Raport musi leżeć poza przebiegiem')
        for run in [getattr(args, 'left', None), getattr(args, 'right', None), args.data_dir]:
            if run is not None and (args.report.resolve() == Path(run).resolve() or Path(run).resolve() in args.report.resolve().parents):
                raise ValueError('Raport musi leżeć poza źródłami i przebiegami')
        protected = [*(ROOT / p for p in build_identity.implementation()),
                     *(ROOT / p for p in qa_evidence({'policy': {}, 'counts': {}, 'problems': []})['sources_sha256']),
                     *sorted((ROOT / 'data/coordinate-source').iterdir()),
                     ROOT / 'data/validation/images-v1.json', orientation.BASELINE, orientation.ARCHIVE,
                     getattr(args, 'archive', None)]
        for path in protected:
            if path is not None:
                guard_input_path(path, args.report.resolve())
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.report, result)
        print(f'Odbiór OK: {result["plans"]} planów; {args.report}')
        return 0
    except (OSError, ValueError) as exc:
        print(f'BŁĄD odbioru: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
