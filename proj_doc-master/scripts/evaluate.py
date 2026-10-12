"""Сравнение извлечённых полей с ручной/синтетической разметкой."""

import argparse
import json
from pathlib import Path

from contracts.pipeline import process_document


def evaluate(directory):
    directory = Path(directory)
    records = json.loads((directory / 'expected.json').read_text(encoding='utf-8'))
    correct = {key: 0 for key in ('number', 'date', 'customer', 'contractor', 'amount')}
    mismatches = []
    for record in records:
        path = directory / record['file']
        result = process_document(path.read_bytes(), path.suffix)
        for key in correct:
            if result.fields[key] == record['fields'][key]:
                correct[key] += 1
            else:
                mismatches.append({'file': path.name, 'field': key,
                                   'expected': record['fields'][key], 'actual': result.fields[key]})
    return {'documents': len(records), 'correct': correct, 'mismatches': mismatches}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default='data/synthetic')
    args = parser.parse_args()
    report = evaluate(args.dataset)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report['mismatches']))
