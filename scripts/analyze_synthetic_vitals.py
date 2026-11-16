"""Analyze the local v1 corpus and compare separately loaded references; no SQLite."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from medassistmultimodal.demo.synthetic_vitals import json_bytes
from medassistmultimodal.domain.vitals import analyze_vitals


def strict_json(data):
    def reject(value):
        raise ValueError(f'nonfinite JSON: {value}')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(data, parse_constant=reject, object_pairs_hook=pairs)


def main():
    root = Path(__file__).resolve().parents[1]
    bundle = root / 'data/synthetic/vitals_v1'
    manifest = strict_json((bundle / 'manifest.json').read_bytes())
    # Fixed names, never follow paths supplied by the manifest.
    names = [f'V{i:02d}.json' for i in range(1, 19)] + ['references.json']
    payloads = {}
    for name in names:
        data = (bundle / name).read_bytes()
        expected = manifest['files'][name]
        if hashlib.sha256(data).hexdigest() != expected['sha256'] or len(data) != expected['bytes']:
            raise ValueError(f'input integrity failure: {name}')
        payloads[name] = data
    # Process inputs first. Ground truth is not an argument to the detector.
    results = [analyze_vitals(strict_json(payloads[name]),
                input_sha256=hashlib.sha256(payloads[name]).hexdigest()) for name in names[:-1]]
    references = strict_json(payloads['references.json'])['scenarios']
    comparisons = []
    fields = ('channel','direction','first_index','last_index','confirmed_index','termination')
    for i, result in enumerate(results, 1):
        key = f'V{i:02d}'
        ref = references[key]
        actual = [{k: asdict(o)[k] for k in fields} for o in result.occurrences]
        order = lambda q: (q['channel'], q['first_index'], q['last_index'])
        comparisons.append({'scenario_id':key, 'occurrences':len(actual),
            'threshold_match':actual == ref['threshold_occurrences'],
            'quality_match':sorted((asdict(q) for q in result.quality_intervals), key=order) == sorted(ref['quality_intervals'], key=order)})
    if not all(c['threshold_match'] and c['quality_match'] for c in comparisons):
        raise ValueError('reference mismatch')
    output = root / 'data/interim/vitals/day11_task03_v1_final'
    output.mkdir(parents=True, exist_ok=False)
    for i, result in enumerate(results,1):
        (output / f'V{i:02d}.json').write_bytes(json_bytes(asdict(result)))
    summary = {'processor':'vitals-rules-v1','clinical_validation':False,
        'scenarios':comparisons,'detected_occurrences':sum(len(r.occurrences) for r in results),
        'quality_intervals':sum(len(r.quality_intervals) for r in results),
        'all_references_match':True,'sqlite_integration':False}
    (output / 'summary.json').write_bytes(json_bytes(summary))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
