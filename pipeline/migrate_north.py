"""Jawna migracja T05; bez nadpisywania historii, obrazów, TFW i ręcznych korekt."""
import argparse
import json
from pathlib import Path

import yaml

from coordinate_source import ROOT
from orientation import BASELINE_SHA256, digest, load_context, migration_metadata

REPORT = ROOT / 'data/migrations/t05-north.json'


def migration(root=ROOT):
    context = load_context()
    plans, writes = [], []
    for plan_id, plan in context['plans'].items():
        path = Path(root) / f'data/caves/{plan_id}/meta.yaml'
        original = context['originals'][plan_id]
        before = yaml.safe_load(original)
        after = migration_metadata(before, plan)
        # Dopisujemy pola, pozostawiając wszystkie wcześniejsze bajty i precyzję.
        additions = {k: after['north'][k] for k in ('reference', 'angle_origin')}
        north_lines = yaml.safe_dump({'north': additions}, sort_keys=False).splitlines(keepends=True)[1:]
        raw = original.decode('utf-8').replace('north:\n', 'north:\n' + ''.join(north_lines), 1)
        raw += yaml.safe_dump({k: after[k] for k in ('declination', 'orientation')},
                              allow_unicode=True, sort_keys=False)
        raw = raw.encode('utf-8')
        # Nigdy nie nadpisujemy obcej edycji ani nie odświeżamy automatycznie decyzji.
        if path.read_bytes() not in (original, raw):
            raise ValueError(f'{plan_id}: zmienione wejście; migracja wymaga jawnego rozstrzygnięcia')
        assert yaml.safe_load(raw) == after
        fields = {f'north.{k}': {'before': {'present': False}, 'after': v} for k, v in additions.items()}
        fields.update({k: {'before': {'present': False}, 'after': after[k]} for k in ('declination', 'orientation')})
        plans.append({'dir_id': plan_id, 'name': before['cave']['name'], 'reason': after['orientation']['uncertainty_reason'],
                      'before_sha256': digest(original), 'after_sha256': digest(raw), 'fields': fields,
                      'geometry': {'orientation': 'historical_tfw', 'position_inputs_changed': False,
                                   'scale_input_changed': False},
                      'historical_tfw_sha256': after['orientation']['historical']['tfw_sha256']})
        writes.append((path, raw))
    report = {'schema_version': 1, 'kind': 't05_explicit_north_migration',
              'baseline_sha256': BASELINE_SHA256, 'archive_sha256': context['hashes'][str(ROOT / 'data/history/t02-inputs.zip')],
              'plans': plans}
    return report, writes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Jawnie zapisz migrację; bez opcji tylko odbiór/raport')
    parser.add_argument('--report', type=Path, required=True, help='Osobny raport przed/po')
    args = parser.parse_args()
    report, writes = migration()
    if args.apply:
        for path, raw in writes:
            path.write_bytes(raw)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(writes)} planów; zapis YAML: {args.apply}; raport: {args.report}')


if __name__ == '__main__':
    main()
