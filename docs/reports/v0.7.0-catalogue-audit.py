"""Odbiór v0.7.0 wobec niezmienionych dowodów T11; tylko odczyt źródeł."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from geotiff_output import check_geotiff, tfw_geotransform

# T09 wcześniej weryfikuje źródła T03; katalog zawiera duże obrazy 1-bit.
# Ta samodzielna komenda nie zależy od konfiguracji ubocznych importów.
Image.MAX_IMAGE_PIXELS = None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(run, qa_path):
    raw = (run / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    qa = json.loads(qa_path.read_bytes())
    assert qa['passed'] and qa['counts']['blocking'] == 0
    assert all(plan['output_status'] == 'current' for plan in qa['plans'])
    historical_path = ROOT / 'docs/reports/t11-reproducibility.json'
    historical = json.loads(historical_path.read_bytes())
    delivery = json.loads((ROOT / 'docs/reports/t11-delivery.json').read_bytes())
    assert digest(historical_path.read_bytes()) == delivery['comparison']['sha256']
    assert historical['passed'] and len(historical['builds']) == 2
    assert manifest['environment'] == historical['environment']
    previous = {plan['plan_id']: plan for plan in historical['comparisons']}
    impact = json.loads((ROOT / 'docs/reports/coordinate-source-v1.3.2-impact.json').read_bytes())
    changes = {plan['dir_id']: plan for plan in impact['geometry']['plans']}
    assert set(changes) == {'001349', '001351', '001387', '010935'}
    assert set(previous) == {plan['dir_id'] for plan in manifest['plans']}
    comparisons = []
    for plan in manifest['plans']:
        plan_id = plan['dir_id']
        tfw = run / plan_id / 'image.tfw'
        actual = check_geotiff(ROOT / 'data/caves' / plan_id / 'image.tif',
            run / plan_id / 'image_georef.tif', tfw_geotransform(tfw))
        assert actual == plan['acceptance'], plan_id
        old = previous[plan_id]
        for field in ('crs', 'size', 'decoded_pixels_sha256'):
            assert actual[field] == old[field], (plan_id, field)
        assert all(actual['geotransform'][i] == old['geotransform'][i] for i in (1, 2, 4, 5)), plan_id
        tfw_digest = digest(tfw.read_bytes())
        changed = tfw_digest != old['tfw_sha256']
        assert changed == (plan_id in changes), plan_id
        if changed:
            assert tfw.read_text() == changes[plan_id]['after']['tfw_text']
            assert digest(changes[plan_id]['before']['tfw_text'].encode()) == old['tfw_sha256']
            assert changes[plan_id]['delta']['rotation_deg'] == 0
            assert changes[plan_id]['delta']['scale_m_per_pixel'] == 0
        else:
            assert actual['geotransform'] == old['geotransform']
        comparisons.append({'plan_id': plan_id, 'changed': changed, 'tfw_sha256': tfw_digest,
            'decoded_pixels_sha256': actual['decoded_pixels_sha256']})
    return {'passed': True, 'run_id': manifest['run_id'], 'code': manifest['code'],
        'run_manifest_sha256': digest(raw), 'plans': len(comparisons),
        'changed_tfw': sorted(plan['plan_id'] for plan in comparisons if plan['changed']),
        'unchanged_tfw': sum(not plan['changed'] for plan in comparisons),
        'all_rotation_scale_crs_dimensions_pixels_unchanged': True,
        'historical_t11_report_sha256': digest(historical_path.read_bytes()),
        't11_cold_pair_preserved': True, 'new_cold_pair': False, 'qa': qa['counts'],
        'comparisons': comparisons}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--qa', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve(strict=True)
    report = args.report.resolve()
    assert report != run and run not in report.parents
    assert ROOT / 'data' not in report.parents
    result = audit(run, args.qa)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'comparisons'}, ensure_ascii=False, indent=2))
