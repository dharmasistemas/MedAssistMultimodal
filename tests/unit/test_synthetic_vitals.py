"""Corpus integrity tests, independent of the future threshold detector."""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile

import pytest

from medassistmultimodal.demo.synthetic_vitals import build_scenarios, json_bytes, write_bundle, UNITS


def test_reproducibility_and_seed_isolation():
    first, reference = build_scenarios()
    assert (first, reference) == build_scenarios()
    different, other_reference = build_scenarios(42)
    assert first[0]['samples'] != different[0]['samples']
    assert reference == other_reference
    first[0]['samples'][0]['heart_rate']['value'] = -1
    assert build_scenarios()[0][0]['samples'][0]['heart_rate']['value'] > 0


def test_all_samples_have_explicit_origin_units_and_nominal_time():
    series, _ = build_scenarios()
    assert [s['scenario_id'] for s in series] == [f'V{i:02d}' for i in range(1, 19)]
    for s in series:
        assert s['patient_id'] == 'PAT-001' and s['source_kind'] == 'synthetic'
        assert s['dataset_id'] is None and s['participant_ref'] is None
        assert 'references' not in s and 'threshold_occurrences' not in s
        assert len(s['samples']) == 12
        start = datetime.fromisoformat(s['started_at'])
        for i, sample in enumerate(s['samples']):
            assert sample['sample_index'] == i
            assert datetime.fromisoformat(sample['timestamp']) == start + timedelta(seconds=i)
            for channel, unit in UNITS.items():
                entry = sample[channel]
                assert entry['unit'] == unit
                if entry['quality'] == 'missing':
                    assert entry['value'] is None and entry['reason']
                elif entry['quality'] == 'invalid':
                    assert entry['reason'] and type(entry['value']) is int
                else:
                    assert entry['quality'] == 'valid' and type(entry['value']) is int
        json.loads(json_bytes(s))


@pytest.mark.parametrize('number,channel,value,first,last', [
    (2, 'heart_rate', 120, 3, 7), (3, 'heart_rate', 45, 3, 7),
    (4, 'spo2', 92, 3, 7), (5, 'systolic', 150, 3, 7),
    (5, 'diastolic', 95, 3, 7), (6, 'systolic', 85, 3, 7),
    (6, 'diastolic', 55, 3, 7), (8, 'heart_rate', 120, 3, 4),
    (9, 'heart_rate', 120, 3, 5), (15, 'heart_rate', 120, 9, 11),
    (16, 'heart_rate', 120, 10, 11)])
def test_injected_intervals(number, channel, value, first, last):
    samples = build_scenarios()[0][number - 1]['samples']
    assert [s['sample_index'] for s in samples if s[channel]['value'] == value] == list(range(first, last + 1))


def test_boundaries_absence_invalid_pairs_and_overlapping_inputs():
    series, _ = build_scenarios()
    for i, sample in enumerate(series[6]['samples']):
        assert [sample[c]['value'] for c in UNITS] == [50 if i % 2 == 0 else 110, 94,
                                                       90 if i < 6 else 140, 60 if i < 6 else 90]
    assert all(s[c]['quality'] == 'missing' for s in series[11]['samples'] for c in UNITS)
    for n, state in ((11, 'missing'), (17, 'invalid')):
        assert series[n - 1]['samples'][3]['heart_rate']['quality'] == state
    invalid = series[12]['samples']
    assert invalid[2]['spo2']['value'] == 101
    assert invalid[4]['heart_rate']['value'] == 0
    assert all(invalid[6][c]['quality'] == 'invalid' for c in ('systolic', 'diastolic'))
    pair = series[17]['samples'][3]
    assert pair['systolic']['value'] is None
    assert pair['diastolic']['value'] == 95 and pair['diastolic']['quality'] == 'invalid'
    assert pair['heart_rate']['quality'] == pair['spo2']['quality'] == 'valid'
    assert series[13]['samples'][3]['heart_rate']['value'] == 120
    assert series[13]['samples'][3]['spo2']['value'] == 92


def test_authored_expectations_have_fixed_counts_and_special_endings():
    _, ref = build_scenarios()
    cases = ref['scenarios']
    assert [len(cases[f'V{i:02d}']['threshold_occurrences']) for i in range(1, 19)] == [
        0, 1, 1, 1, 2, 2, 0, 0, 1, 2, 0, 0, 0, 2, 1, 0, 0, 0]
    assert cases['V15']['threshold_occurrences'][0] == {
        'channel': 'heart_rate', 'direction': 'high', 'first_index': 9,
        'last_index': 11, 'confirmed_index': 11, 'termination': 'end_of_series'}
    assert len(cases['V12']['quality_intervals']) == 4
    assert len(cases['V13']['quality_intervals']) == 4
    assert len(cases['V18']['quality_intervals']) == 2


def test_bundle_bytes_hashes_and_no_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / 'a', Path(tmp) / 'b'
        manifest = write_bundle(a)
        assert write_bundle(b) == manifest
        assert len(manifest['files']) == 19
        for path in a.iterdir():
            assert path.read_bytes() == (b / path.name).read_bytes()
        for name, info in manifest['files'].items():
            data = (a / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == info['sha256']
            assert len(data) == info['bytes']
        original = (a / 'V01.json').read_bytes()
        with pytest.raises(FileExistsError):
            write_bundle(a, 42)
        assert (a / 'V01.json').read_bytes() == original


@pytest.mark.parametrize('seed', [True, 1.5, '20261103', None])
def test_invalid_seed(seed):
    with pytest.raises(ValueError):
        build_scenarios(seed)
