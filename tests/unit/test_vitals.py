from copy import deepcopy
from dataclasses import asdict
import math

import pytest

from medassistmultimodal.demo.synthetic_vitals import build_scenarios
from medassistmultimodal.domain.vitals import analyze_vitals, validate_vital_series, VitalsProfile

HASH = 'a' * 64


@pytest.mark.parametrize('number', range(18))
def test_matches_predeclared_references(number):
    inputs, references = build_scenarios()
    payload = inputs[number]
    original = deepcopy(payload)
    result = analyze_vitals(payload, input_sha256=HASH)
    expected = references['scenarios'][payload['scenario_id']]
    fields = ('channel', 'direction', 'first_index', 'last_index', 'confirmed_index', 'termination')
    actual = [{k: asdict(o)[k] for k in fields} for o in result.occurrences]
    assert actual == expected['threshold_occurrences']
    order = lambda q: (q['channel'], q['first_index'], q['last_index'])
    assert sorted((asdict(q) for q in result.quality_intervals), key=order) == sorted(expected['quality_intervals'], key=order)
    assert payload == original
    assert result == analyze_vitals(payload, input_sha256=HASH)
    for occurrence in result.occurrences:
        assert occurrence.confirmation_latency_seconds == 2
        assert occurrence.duration_seconds == occurrence.last_index - occurrence.first_index + 1
        assert len(occurrence.values) == occurrence.duration_seconds


@pytest.mark.parametrize('channel,bound,direction', [('heart_rate',50,'low'),('heart_rate',110,'high'),
    ('spo2',94,'low'),('systolic',90,'low'),('systolic',140,'high'),('diastolic',60,'low'),('diastolic',90,'high')])
def test_equality_and_immediately_beyond_bound(channel, bound, direction):
    payload = build_scenarios()[0][0]
    for sample in payload['samples']:
        sample[channel]['value'] = bound
    assert not analyze_vitals(payload, input_sha256=HASH).occurrences
    for sample in payload['samples']:
        sample[channel]['value'] = math.nextafter(bound, -math.inf if direction == 'low' else math.inf)
    result = analyze_vitals(payload, input_sha256=HASH)
    assert len(result.occurrences) == 1
    assert result.occurrences[0].direction == direction


@pytest.mark.parametrize('mutation', ['bool','nan','inf','unit','no_unit','naive','order','duplicate',
    'dataset','valid_null','missing_number','empty','no_channel','bad_seed','bad_interval','no_reason'])
def test_rejects_invalid_envelope_and_unrepresentable_channels(mutation):
    p = build_scenarios()[0][0]
    s = p['samples'][0]
    if mutation in ('bool','nan','inf'):
        s['heart_rate']['value'] = {'bool':True,'nan':float('nan'),'inf':float('inf')}[mutation]
    elif mutation == 'unit': s['heart_rate']['unit'] = 'Hz'
    elif mutation == 'no_unit': del s['heart_rate']['unit']
    elif mutation == 'naive': s['timestamp'] = '2026-11-03T12:00:00'
    elif mutation == 'order': p['samples'].reverse()
    elif mutation == 'duplicate': p['samples'][1]['sample_index'] = 0
    elif mutation == 'dataset': p['dataset_id'] = 'bidmc'
    elif mutation == 'valid_null': s['heart_rate']['value'] = None
    elif mutation == 'missing_number': s['heart_rate'].update(quality='missing',reason='absent')
    elif mutation == 'empty': p['samples'] = []
    elif mutation == 'no_channel': del s['spo2']
    elif mutation == 'bad_seed': p['seed'] = True
    elif mutation == 'bad_interval': p['interval_seconds'] = True
    elif mutation == 'no_reason': s['heart_rate'].update(quality='invalid')
    with pytest.raises(ValueError): analyze_vitals(p, input_sha256=HASH)


def test_direction_change_and_quality_gap_termination():
    p = build_scenarios()[0][0]
    for i in range(6): p['samples'][i]['heart_rate']['value'] = 120 if i < 3 else 45
    p['samples'][6]['heart_rate'].update(value=None, quality='missing',reason='not_provided')
    r = analyze_vitals(p,input_sha256=HASH)
    assert [(o.first_index,o.last_index,o.termination) for o in r.occurrences] == [
        (3,5,'quality_gap'),(0,2,'direction_change')]


def test_normalizes_domain_invalid_without_losing_other_channel_episode():
    p = build_scenarios()[0][1]
    p['samples'][4]['spo2']['value'] = 101
    p['samples'][5]['systolic']['value'] = 70
    p['samples'][5]['diastolic']['value'] = 80
    samples = validate_vital_series(p)
    assert samples[4].channels[1].value == 101 and samples[4].channels[1].quality == 'invalid'
    assert all(v.quality == 'invalid' for v in samples[5].channels[2:])
    r = analyze_vitals(p,input_sha256=HASH)
    assert len(r.occurrences) == 1 and r.occurrences[0].last_index == 7


def test_missing_pressure_pair_is_not_used_even_if_partner_marked_valid():
    p = build_scenarios()[0][17]
    p['samples'][3]['diastolic'].update(quality='valid')
    del p['samples'][3]['diastolic']['reason']
    r = analyze_vitals(p,input_sha256=HASH)
    assert not r.occurrences
    assert r.coverage[2].valid_samples == r.coverage[3].valid_samples == 11


def test_all_missing_coverage_is_zero_and_quality_is_compact():
    r = analyze_vitals(build_scenarios()[0][11],input_sha256=HASH)
    assert not r.occurrences and len(r.quality_intervals) == 4
    assert all(c.fraction == 0 for c in r.coverage)
    assert all(q.first_index == 0 and q.last_index == 11 for q in r.quality_intervals)


@pytest.mark.parametrize('kwargs',[{'persistence':True},{'persistence':0},{'version':''},
    {'bounds':((100,50),(94,None),(90,140),(60,90))}])
def test_invalid_profiles(kwargs):
    with pytest.raises(ValueError): VitalsProfile(**kwargs)


def test_hash_is_required():
    with pytest.raises(ValueError): analyze_vitals(build_scenarios()[0][0],input_sha256='unknown')
