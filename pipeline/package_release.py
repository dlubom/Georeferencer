"""T10: wspólna bramka wydania tag/manual, także do prób bez publikacji.

Nie komunikuje się z GitHub. Tworzy ZIP dopiero po pełnym QA konkretnego
przebiegu; workflow publikuje wyłącznie udany wynik tego polecenia.
"""
import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

from coordinate_source import ROOT, DEFAULT_MANIFEST, read_manifest, sha256
from geotiff_output import input_hashes, read_json, guard_input_path
from qa import create_report, write_reports
from validation import IMAGE_REGISTRY
import build_identity
import orientation
import release_acceptance
from release_layout import files_for_release


def package_run(data_dir, run_dir, archive, reports_dir, *, mode='tag', qa_kwargs=None, require_clean_code=False):
    if mode not in ('tag', 'manual'):
        raise ValueError('Wymagana ścieżka tag albo manual')
    # Jedyny odczyt wskazania current. QA i pakowanie otrzymują ten sam katalog.
    run = Path(run_dir).resolve(strict=True)
    data, archive, reports = Path(data_dir).resolve(), Path(archive).resolve(), Path(reports_dir).resolve()
    for output in (archive, reports):
        if output == run or run in output.parents or output == data or data in output.parents:
            raise ValueError('ZIP i raporty muszą leżeć poza przebiegiem oraz danymi źródłowymi')
    if reports in run.parents or reports in data.parents or archive == reports or reports in archive.parents:
        raise ValueError('Katalog raportów nie może nakładać się na przebieg, źródła ani ZIP')
    options = dict(qa_kwargs or {})
    if 'run_dir' in options or 'require_results' in options:
        raise ValueError('Bramka wymaga QA wskazanego kompletnego przebiegu')
    registry = Path(options.get('registry_path', IMAGE_REGISTRY))
    pin = read_manifest(DEFAULT_MANIFEST)
    common_paths = [DEFAULT_MANIFEST, DEFAULT_MANIFEST.parent / pin['snapshot'], registry,
        orientation.BASELINE, *(ROOT / p for p in build_identity.implementation()),
        ROOT / 'parquet/SUBMISSIONS.parquet', *sorted((ROOT / 'data/qa').glob('*.json')),
        *sorted((ROOT / 'data/classification').glob('*.json'))]
    for path in common_paths:
        guard_input_path(path, archive)
        guard_input_path(path, reports)
    guarded = {p: sha256(p) for p in common_paths}
    manifest_bytes = (run / 'manifest.json').read_bytes()
    packaging_code = build_identity.code_version()
    if require_clean_code:
        for code in (read_json(run / 'manifest.json').get('code', {}), packaging_code):
            if not re.fullmatch('[0-9a-f]{40}', code.get('commit') or '') or code.get('dirty') != 'false':
                raise ValueError('Build i pakowanie wymagają czystego checkoutu i SHA kodu z scripts/build')
    report = create_report(data, run_dir=run, require_results=True, **options)
    report['run'] = {'path': str(run), 'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'mode': mode}
    write_reports(report, reports)
    if not report['passed']:
        raise ValueError(f"Pełne QA wydania blokuje pakowanie: {report['counts']['blocking']} problemów")
    manifest = read_json(run / 'manifest.json')
    files = files_for_release(manifest, data)
    manifest['release'] = {'version': release_acceptance.RELEASE_VERSION, 'mode': mode,
        'files': files,
        'code': packaging_code,
        'run_id': manifest['run_id'], 'run_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'qa': release_acceptance.qa_evidence(report)}
    release_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    expected = {'manifest.json': hashlib.sha256(manifest_bytes).hexdigest()}
    members = [('manifest.json', 'manifest.json', expected['manifest.json'])]
    for item in files:
        source = item['plan_id'] + '/' + item['output']
        expected[source] = item['sha256']
        members.append((item['archive_path'], source, item['sha256']))
    archive.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.package-', suffix='.zip', dir=archive.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as package:
            for name, source, digest in sorted(members):
                raw = (run / source).read_bytes()
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError(f'Wynik zmienił się po QA: {name}')
                package.writestr(name, release_bytes if name == 'manifest.json' else raw)
        release_acceptance.verify_archive(temporary, data, qa_kwargs=options)
        actual = {str(p.relative_to(run)) for p in run.rglob('*') if not p.is_dir()}
        if actual != set(expected) or any(p.is_symlink() for p in run.rglob('*')):
            raise ValueError('Komplet wyników zmienił się po QA')
        for plan in report['plans']:
            if input_hashes(data / plan['plan_id']) != plan['inputs']:
                raise ValueError('Źródła planu zmieniły się po QA')
        ids = {p.name for p in data.iterdir() if p.is_dir() and not p.name.startswith(('_', '.'))}
        if ids != {p['plan_id'] for p in report['plans']} or any(sha256(p) != h for p, h in guarded.items()):
            raise ValueError('Źródła katalogu zmieniły się po QA')
        os.replace(temporary, archive)
        return archive
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description='Pełne QA i ZIP dokładnego przebiegu, bez publikacji')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/caves')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--reports-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('tag', 'manual'), required=True)
    args = parser.parse_args()
    try:
        result = package_run(args.data_dir, args.run_dir, args.archive, args.reports_dir, mode=args.mode,
                             require_clean_code=True)
        print(f'QA i pakowanie OK: {result}')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'BŁĄD wydania: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
