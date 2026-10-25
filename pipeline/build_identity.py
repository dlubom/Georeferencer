"""T10: treść wejść i wersje wykonania, bez mtime i SHA całego commitu."""
import hashlib
import importlib.metadata
import json
import platform
import subprocess

import pyproj
from coordinate_source import ROOT, sha256

CONTENT_VERSION = 't10-content-v1'


def implementation():
    paths = [*sorted((ROOT / 'pipeline').glob('*.py')), ROOT / 'pipeline/meta-schema-v1.json',
             ROOT / 'pipeline/requirements.txt', ROOT / 'ci/Dockerfile', ROOT / 'ci/requirements.lock',
             ROOT / 'scripts/build']
    return {str(p.relative_to(ROOT)): sha256(p) for p in paths}


def environment():
    gdal = subprocess.check_output(['gdalinfo', '--version'], text=True).strip()
    return {'system': platform.system(), 'architecture': platform.machine(),
            'Python': platform.python_version(), 'GDAL': gdal,
            'GDAL build': subprocess.check_output(['gdalinfo', '--build'], text=True).strip(),
            'PROJ (pyproj)': pyproj.proj_version_str,
            'packages': dict(sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions()))}


def fingerprint(provenance, inputs, measurement, parameters, orientation):
    common = {key: provenance.get(key) for key in ('content_version', 'implementation',
              'environment', 'coordinate_source', 'orientation_sources', 'geometry')}
    registry = provenance.get('image_registry')
    if not isinstance(registry, dict):
        raise ValueError('Manifest: rejestr obrazu musi być mapą')
    common['image_registry'] = registry.get('sha256')
    value = {'common': common, 'inputs': inputs,
             'local_image_registry': inputs.get('image-identity.json'),
             'measurement': measurement, 'parameters': parameters, 'orientation': orientation}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()
