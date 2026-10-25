#!/usr/bin/env python3
"""T09: bieżące źródłowe QA oraz opcjonalny odbiór wybranego przebiegu T04."""
import argparse
import csv
import sys
from pathlib import Path

from qa import create_report, write_reports
from orientation import summary as orientation_summary

DATA_DIR = Path('data/caves')
REPORTS_DIR = DATA_DIR / '_reports'


def write_summary(metas):
    """Zgodność małego API T05; właściwy raport katalogu powstaje przez create_report."""
    fields = ['north_reference', 'angle_origin', 'orientation_status', 'orientation_uncertainty_reason']
    with (REPORTS_DIR / 'summary.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for meta in metas:
            data = orientation_summary(meta)
            writer.writerow(dict(zip(fields, (data['north_reference'], data['angle_origin'], data['status'], data['uncertainty_reason']))))


def main():
    parser = argparse.ArgumentParser(description='QA planów, reguły i jawne wyjątki T09')
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--reports-dir', type=Path, help='Domyślnie DATA_DIR/_reports')
    parser.add_argument('--run-dir', type=Path, help='Konkretny przebieg T04 lub jego current; dokładny komplet katalogu')
    parser.add_argument('--require-results', action='store_true', help='Brak wybranego przebiegu blokuje kontrolę')
    parser.add_argument('--image-registry', type=Path)
    parser.add_argument('--exceptions', type=Path)
    args = parser.parse_args()
    kwargs = {'run_dir': args.run_dir, 'require_results': args.require_results}
    if args.image_registry:
        kwargs['registry_path'] = args.image_registry
    if args.exceptions:
        import json
        kwargs['exceptions'] = json.loads(args.exceptions.read_text())
    result = create_report(args.data_dir, **kwargs)
    write_reports(result, args.reports_dir or args.data_dir / '_reports')
    counts = result['counts']
    print(f"QA: {counts['plans']} planów; {counts['accepted']} dopuszczonych niepewności; {counts['blocking']} problemów blokujących")
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
