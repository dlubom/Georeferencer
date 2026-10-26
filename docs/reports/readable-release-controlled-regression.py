"""Kontrolowany powrót starego układu ZIP: nowy test ma zgłosić FAIL.

Mutuje wyłącznie prywatną kopię modułu w /tmp; checkout pozostaje readonly.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'pipeline')]
raw = (ROOT / 'pipeline/package_release.py').read_text()
changes = {
    'files = files_for_release(manifest, data)':
        "files = files_for_release(manifest, data, version='t11-v1')",
    "'version': release_acceptance.RELEASE_VERSION": "'version': 't11-v1'",
}
for before, after in changes.items():
    if raw.count(before) != 1:
        raise SystemExit('Zmienił się punkt mutacji; wymagany przegląd próby')
    raw = raw.replace(before, after)
with tempfile.TemporaryDirectory(prefix='readable-release-mutant-') as temporary:
    mutant = Path(temporary) / 'package_release.py'
    mutant.write_text(raw)
    spec = importlib.util.spec_from_file_location('package_release', mutant)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules['package_release'] = module
    suite = unittest.defaultTestLoader.loadTestsFromName(
        'test_package_release.PackageTest.test_complete_package_has_exact_manifest_inventory_and_external_qa')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    detected = result.testsRun == 1 and len(result.failures) == 1 and not result.errors
    print('Kontrolowana regresja wykryta:', detected)
    raise SystemExit(0 if detected else 1)
