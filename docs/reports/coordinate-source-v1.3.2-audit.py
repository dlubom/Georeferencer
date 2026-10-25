"""Odbiór aktualizacji pinu względem wersjonowanych dowodów T11, bez zapisu źródeł."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from coordinate_source import read_rows, sha256, verify
from geotiff_output import check_geotiff, tfw_geotransform
from catalogue_baseline import capture_plans, coordinate_impact
import build_identity


def audit(run, qa_path, revision):
    run = run.resolve(strict=True)
    manifest = json.loads((run / 'manifest.json').read_text())
    qa = json.loads(qa_path.read_text())
    assert qa['passed'] and qa['counts']['blocking'] == 0
    assert all(p['output_status'] == 'current' for p in qa['plans'])
    assert manifest['code'] == {'commit': revision, 'dirty': 'false'}
    pin_dir = ROOT / 'data/coordinate-source'
    before_pin, after_pin = pin_dir / 'source-v1.3.1.json', pin_dir / 'source.json'
    assert after_pin.read_bytes() == (pin_dir / 'source-v1.3.2.json').read_bytes()
    before, after = read_rows(verify(before_pin)), read_rows(verify(after_pin))
    impact = json.loads((ROOT / 'docs/reports/coordinate-source-v1.3.2-impact.json').read_text())
    plans = capture_plans(ROOT, before)
    # Odtwarzamy raport geometrii obu pinów tym samym kodem, bez mutacji katalogu.
    assert coordinate_impact(ROOT, plans, before_pin, after_pin) == impact['geometry']
    by_id = {p['dir_id']: p for p in manifest['plans']}
    assert len(by_id) == len(manifest['plans']) == len(plans)
    assert set(by_id) == {p['dir_id'] for p in plans}
    missing_links = [p for p in plans if p['object_id'] not in after]
    assert not missing_links, missing_links
    for p in plans:
        assert by_id[p['dir_id']]['measurement'] == after[p['object_id']]
    delivery = json.loads((ROOT / 'docs/reports/t11-delivery.json').read_text())
    t11_path = ROOT / 'docs/reports/t11-reproducibility.json'
    assert sha256(t11_path) == delivery['comparison']['sha256']
    t11 = json.loads(t11_path.read_text())
    assert t11['passed'] and len(t11['builds']) == 2
    assert all(b['generated'] == len(plans) and b['reused'] == 0 for b in t11['builds'])
    assert manifest['implementation'] == delivery['manifest_contract']['implementation_sha256']
    assert build_identity.implementation() == manifest['implementation']
    assert manifest['environment'] == t11['environment']
    assert sha256(verify(before_pin)) == t11['coordinate_source']['sha256']
    previous = {p['plan_id']: p for p in t11['comparisons']}
    assert set(previous) == set(by_id)
    changes = {p['dir_id']: p for p in impact['geometry']['plans']}
    comparisons = []
    for plan_id, record in sorted(by_id.items()):
        directory = run / plan_id
        tfw = directory / 'image.tfw'
        actual = check_geotiff(ROOT / 'data/caves' / plan_id / 'image.tif',
                               directory / 'image_georef.tif', tfw_geotransform(tfw))
        assert actual == record['acceptance']
        old = previous[plan_id]
        for field in ('crs', 'size', 'decoded_pixels_sha256'):
            assert actual[field] == old[field], (plan_id, field)
        transform = actual['geotransform']
        old_transform = old['geotransform']
        assert all(transform[i] == old_transform[i] for i in (1, 2, 4, 5))
        changed = sha256(tfw) != old['tfw_sha256']
        assert changed == (plan_id in changes), plan_id
        if changed:
            expected = changes[plan_id]
            assert hashlib.sha256(expected['before']['tfw_text'].encode()).hexdigest() == old['tfw_sha256']
            assert tfw.read_text() == expected['after']['tfw_text']
        else:
            assert transform == old_transform
        comparisons.append({'plan_id': plan_id, 'object_id': record['measurement']['object_id'],
            'measurement_id': record['measurement']['measurement_id'],
            'tfw_sha256_before': old['tfw_sha256'], 'tfw_sha256_after': sha256(tfw),
            'changed': changed, 'delta': changes[plan_id]['delta'] if changed else None,
            'matrix_unchanged': True, 'pixels_crs_dimensions_unchanged': True,
            'geotransform_before': old_transform, 'actual': actual,
            'fingerprint_before': old['fingerprint'], 'fingerprint_after': record['fingerprint']})
    return {'schema_version': 1, 'passed': True, 'code': manifest['code'],
        'run_id': manifest['run_id'], 'run_manifest_sha256': sha256(run / 'manifest.json'),
        'source_objects_before': len(before), 'source_objects_after': len(after),
        'source_objects_added': sorted(after.keys() - before.keys()),
        'source_objects_removed': sorted(before.keys() - after.keys()),
        'existing_objects_changed': sorted(k for k in before.keys() & after.keys() if before[k] != after[k]),
        'plans': len(plans), 'changed_tfw': len(changes), 'unchanged_tfw': len(plans) - len(changes),
        'missing_explicit_objects': missing_links, 'automatic_relinks': [],
        'new_objects_without_plan_links': sorted(k for k in after.keys() - before.keys()
            if not any(p['object_id'] == k for p in plans)),
        'pending_manual_links': [{k: p[k] for k in ('plan_id', 'object_id', 'link_status')}
            for p in qa['plans'] if p['link_status'] == 'explicit_valid_pending_review'],
        'qa': qa['counts'], 'coordinate_source': manifest['coordinate_source'],
        'environment': manifest['environment'],
        'generation': {'generated': len(manifest['build']['generated']), 'reused': len(manifest['build']['reused'])},
        't11_evidence': {'report_sha256': sha256(t11_path),
            'delivery_sha256': sha256(ROOT / 'docs/reports/t11-delivery.json'),
            'cold_builds_reused_as_prior_evidence': 2,
            'implementation_and_environment_unchanged': True,
            'scope': 'Jeden pełny build nowego pinu; porównanie wszystkich wyników z wersjonowanymi dowodami T11. Bez ponawiania dwóch zimnych buildów.'},
        'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--qa', required=True, type=Path)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    run = args.run_dir.resolve(strict=True)
    output = args.output.resolve()
    assert not output.is_relative_to(run), 'Raport musi być poza przebiegiem'
    assert not output.is_relative_to(ROOT / 'data'), 'Raport musi być poza źródłami'
    result = audit(run, args.qa, args.revision)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(f"Odbiór aktualizacji: {result['plans']} planów, {result['changed_tfw']} zmienione TFW, PASS")


if __name__ == '__main__':
    main()
