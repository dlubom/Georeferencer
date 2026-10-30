"""Metadane orientacji dla syntetycznych wejść testowych."""
import copy
from pathlib import Path
import yaml


def attach_orientation(meta, image_sha256=None):
    original = yaml.safe_load((Path(__file__).resolve().parents[1] / 'data/caves' /
                               meta['cave']['dir_id'] / 'meta.yaml').read_text())
    result = copy.deepcopy(meta)
    result['north'].setdefault('reference', 'unknown')
    result['north'].setdefault('angle_origin', 'unknown')
    result.setdefault('declination', original['declination'])
    image_sha256 = image_sha256 or result.get('orientation', {}).get('image_sha256')
    result['orientation'] = original['orientation']
    if image_sha256:
        result['orientation']['image_sha256'] = image_sha256
    return result
