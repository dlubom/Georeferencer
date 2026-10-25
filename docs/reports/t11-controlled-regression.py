"""Dowód regresji: pominięcie odbioru gotowego ZIP musi złamać test.

Uruchamiać w przypiętym obrazie z repo readonly; mutuje tylko prywatną kopię
modułu w /tmp. Nie jest poleceniem naprawy ani aktualizacji wyjątków.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'pipeline')]
source = ROOT / 'pipeline/package_release.py'
needle = '        release_acceptance.verify_archive(temporary, data, qa_kwargs=options)'
raw = source.read_text()
if raw.count(needle) != 1:
    raise SystemExit('Zmienił się punkt mutacji; wymagany przegląd próby')
with tempfile.TemporaryDirectory(prefix='t11-mutant-') as temporary:
    mutant = Path(temporary) / 'package_release.py'
    mutant.write_text(raw.replace(needle, '        pass  # kontrolowane pominięcie odbioru ZIP'))
    spec = importlib.util.spec_from_file_location('package_release', mutant)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules['package_release'] = module
    suite = unittest.defaultTestLoader.loadTestsFromName(
        'test_release_acceptance.AcceptanceTest.test_failed_archive_readback_preserves_previous_package_and_current')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    detected = result.testsRun == 1 and len(result.failures) == 1 and not result.errors
    print('Kontrolowana regresja wykryta:', detected)
    raise SystemExit(0 if detected else 1)
