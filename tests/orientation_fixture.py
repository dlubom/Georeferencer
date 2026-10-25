"""Jawne przyjęcie TFW T02 w syntetycznych wejściach; bez starego wzoru."""
import copy
from orientation import default_context, initial_metadata, record_decision


def attach_orientation(meta, image_sha256=None):
    initial = initial_metadata(meta, default_context())
    result = copy.deepcopy(meta)
    result['north'].setdefault('reference', 'unknown')
    result['north'].setdefault('angle_origin', 'unknown')
    result.setdefault('declination', copy.deepcopy(initial['declination']))
    image_sha256 = image_sha256 or result.get('orientation', {}).get('image_sha256')
    result['orientation'] = copy.deepcopy(initial['orientation'])
    if image_sha256:
        result['orientation']['image_sha256'] = image_sha256
    return record_decision(result, 'Syntetyczna próba: jawne zachowanie historycznego kąta T02 przy innych danych testowych.',
                           '2026-10-25')
