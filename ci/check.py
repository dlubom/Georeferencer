"""Weryfikacja środowiska i wspólne uruchomienie całego zestawu testów."""

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import unittest
from pathlib import Path

import pyproj


ROOT = Path(__file__).resolve().parents[1]
source_hash = hashlib.sha256((ROOT / "pipeline/requirements.txt").read_bytes()).hexdigest()
lock_header = (ROOT / "ci/requirements.lock").read_text().splitlines()[0]
if lock_header != f"# source-sha256: {source_hash}":
    sys.exit("Zmieniono requirements.txt. Odśwież lock zgodnie z ci/README.md.")

gdal = json.loads(subprocess.check_output([
    "/usr/bin/python3", "-c",
    "import json; from osgeo import gdal, osr; "
    "print(json.dumps({'GDAL': gdal.VersionInfo('RELEASE_NAME'), "
    "'PROJ (GDAL)': '.'.join(str(f()) for f in "
    "(osr.GetPROJVersionMajor, osr.GetPROJVersionMinor, osr.GetPROJVersionMicro))}))",
], text=True))
print(json.dumps({
    "system": platform.system(),
    "architecture": platform.machine(),
    "Python": platform.python_version(),
    **gdal,
    "PROJ (pyproj)": pyproj.proj_version_str,
    "packages": dict(sorted(
        (dist.metadata["Name"], dist.version)
        for dist in importlib.metadata.distributions()
    )),
}, indent=2))
subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
if suite.countTestCases() == 0:
    sys.exit("Nie znaleziono testów — kontrola nie może być uznana za udaną.")
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
