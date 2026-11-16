"""Synthetic inputs and independent, declared references; no detector here."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random

VERSION = 'synthetic-vitals-generator-v1'
SEED = 20261103
UNITS = {'heart_rate': 'bpm', 'spo2': '%', 'systolic': 'mmHg', 'diastolic': 'mmHg'}
START = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       sort_keys=True, indent=2) + '\n').encode('utf-8')


def build_scenarios(seed: int = SEED) -> tuple[list[dict], dict]:
    """Return new inputs and separately authored expectations, not inferred labels."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed must be an integer')
    rng = random.Random(seed)
    series = []
    references = {}
    for number in range(1, 19):
        key = f'V{number:02d}'
        samples = []
        for index in range(12):
            values = (rng.randint(72, 78), rng.randint(97, 99),
                      rng.randint(118, 122), rng.randint(78, 82))
            samples.append({'sample_index': index,
                            'timestamp': (START + timedelta(seconds=index)).isoformat(),
                            **{channel: {'value': value, 'unit': UNITS[channel], 'quality': 'valid'}
                               for channel, value in zip(UNITS, values)}})
        series.append({'schema_version': 'synthetic-vitals-v1', 'series_id': f'synthetic-vitals-v1-{key}',
                       'scenario_id': key, 'subject_kind': 'synthetic_patient', 'patient_id': 'PAT-001',
                       'source_kind': 'synthetic', 'source': VERSION, 'dataset_id': None,
                       'participant_ref': None, 'generator_version': VERSION, 'seed': seed,
                       'started_at': START.isoformat(), 'time_basis': 'fictional_nominal_utc',
                       'interval_seconds': 1, 'samples': samples})
        references[key] = {'threshold_occurrences': [], 'quality_intervals': []}

    def put(n, channel, first, last, value, quality='valid', reason=None):
        for i in range(first, last + 1):
            entry = series[n - 1]['samples'][i][channel]
            entry.update(value=value, quality=quality)
            if reason:
                entry['reason'] = reason

    def occurrence(n, channel, direction, first, last, termination='return_to_range'):
        references[f'V{n:02d}']['threshold_occurrences'].append(
            {'channel': channel, 'direction': direction, 'first_index': first,
             'last_index': last, 'confirmed_index': first + 2, 'termination': termination})

    def quality(n, channel, first, last, state, reason):
        references[f'V{n:02d}']['quality_intervals'].append(
            {'channel': channel, 'first_index': first, 'last_index': last,
             'quality': state, 'reason': reason})

    for n, channel, value, direction in ((2, 'heart_rate', 120, 'high'),
                                        (3, 'heart_rate', 45, 'low'), (4, 'spo2', 92, 'low')):
        put(n, channel, 3, 7, value)
        occurrence(n, channel, direction, 3, 7)
    for n, systolic, diastolic, direction in ((5, 150, 95, 'high'), (6, 85, 55, 'low')):
        for channel, value in (('systolic', systolic), ('diastolic', diastolic)):
            put(n, channel, 3, 7, value)
            occurrence(n, channel, direction, 3, 7)
    for i in range(12):
        put(7, 'heart_rate', i, i, 50 if i % 2 == 0 else 110)
        put(7, 'spo2', i, i, 94)
        put(7, 'systolic', i, i, 90 if i < 6 else 140)
        put(7, 'diastolic', i, i, 60 if i < 6 else 90)
    put(8, 'heart_rate', 3, 4, 120)
    put(9, 'heart_rate', 3, 5, 120)
    occurrence(9, 'heart_rate', 'high', 3, 5)
    for first, last in ((1, 3), (5, 7)):
        put(10, 'heart_rate', first, last, 120)
        occurrence(10, 'heart_rate', 'high', first, last)
    for n in (11, 17):
        put(n, 'heart_rate', 1, 2, 120)
        put(n, 'heart_rate', 4, 5, 120)
        state, value, reason = ('missing', None, 'not_provided') if n == 11 else ('invalid', 0, 'non_positive')
        put(n, 'heart_rate', 3, 3, value, state, reason)
        quality(n, 'heart_rate', 3, 3, state, reason)
    for channel in UNITS:
        put(12, channel, 0, 11, None, 'missing', 'not_provided')
        quality(12, channel, 0, 11, 'missing', 'not_provided')
    for channel, index, value, reason in (('spo2', 2, 101, 'outside_percentage'),
                                          ('heart_rate', 4, 0, 'non_positive'),
                                          ('systolic', 6, 70, 'invalid_pressure_pair'),
                                          ('diastolic', 6, 80, 'invalid_pressure_pair')):
        put(13, channel, index, index, value, 'invalid', reason)
        quality(13, channel, index, index, 'invalid', reason)
    for channel, value, first, last, direction in (('heart_rate', 120, 1, 5, 'high'),
                                                  ('spo2', 92, 2, 6, 'low')):
        put(14, channel, first, last, value)
        occurrence(14, channel, direction, first, last)
    put(15, 'heart_rate', 9, 11, 120)
    occurrence(15, 'heart_rate', 'high', 9, 11, 'end_of_series')
    put(16, 'heart_rate', 10, 11, 120)
    put(18, 'diastolic', 1, 5, 95)
    put(18, 'systolic', 3, 3, None, 'missing', 'not_provided')
    # Preserve the observed diastolic value, but explicitly mark its pair unavailable.
    put(18, 'diastolic', 3, 3, 95, 'invalid', 'pressure_pair_unavailable')
    quality(18, 'systolic', 3, 3, 'missing', 'not_provided')
    quality(18, 'diastolic', 3, 3, 'invalid', 'pressure_pair_unavailable')
    return series, {'schema_version': 'synthetic-vitals-reference-v1',
                    'reference_kind': 'authored_synthetic_expectations_not_detector_output',
                    'profile_version': 'synthetic-vitals-rules-v1', 'scenarios': references}


def write_bundle(output: Path, seed: int = SEED) -> dict:
    """Create an exclusive directory. Never overwrite a previous run."""
    series, references = build_scenarios(seed)
    payloads = {f'{s["scenario_id"]}.json': json_bytes(s) for s in series}
    payloads['references.json'] = json_bytes(references)
    manifest = {'schema_version': 'synthetic-vitals-bundle-v1', 'generator_version': VERSION,
                'seed': seed, 'algorithm': 'python.random.Random/MT19937; randint; scenario/index/channel order',
                'configuration': {'samples_per_scenario': 12, 'interval_seconds': 1,
                                  'channel_order': list(UNITS), 'units': UNITS,
                                  'baseline_integer_ranges': [[72, 78], [97, 99], [118, 122], [78, 82]]},
                'origin': 'internally_generated_fictional_data',
                'usage': 'academic_software_testing_only_no_external_dataset',
                'clinical_validation': False, 'scenario_count': 18, 'sample_count': 216,
                'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
                          for name, data in sorted(payloads.items())}}
    output.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        (output / name).write_bytes(data)
    (output / 'manifest.json').write_bytes(json_bytes(manifest))
    return manifest
