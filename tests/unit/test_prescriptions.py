from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
import hashlib
import json
import unicodedata

import pytest

from medassistmultimodal.demo.prescription_fixtures import base_pair,build_prescription_cases
from medassistmultimodal.domain.prescriptions import compare_prescriptions


def encode(p):return json.dumps(p,ensure_ascii=False).encode('utf-8')


@pytest.mark.parametrize('case',[f'P{i:02d}' for i in range(1,25)])
def test_approved_primary_cases(case):
    cases,refs=build_prescription_cases()
    original=deepcopy(cases[case])
    if case in refs['rejected']:
        with pytest.raises(ValueError):compare_prescriptions(encode(cases[case]))
    else:
        result=compare_prescriptions(encode(cases[case]))
        actual=[{'kind':c.kind,'item_id':c.item_id,'fields':[f.field for f in c.field_changes]} for c in result.changes]
        assert actual==refs['changes'][case]
        assert result==compare_prescriptions(encode(cases[case]))
        assert result.status==('changed' if actual else 'unchanged')
        assert result.included_count+result.removed_count+result.modified_count==len(actual)
    assert cases[case]==original


@pytest.mark.parametrize('value',['0','-1','NaN','Infinity','.5','1.','1e2','1,5',True,10,None])
def test_invalid_dose(value):
    p=base_pair();p['after']['items'][0]['dose_value']=value
    with pytest.raises(ValueError):compare_prescriptions(encode(p))


@pytest.mark.parametrize('mutation',['version_reverse','date_reverse','naive','patient','set','source',
    'dataset','partial','missing_after','missing_items','unit','missing_unit','route',
    'frequency_bool','duration_bool','extra_item','extra_snapshot','extra_pair','missing_value','bad_id'])
def test_schema_and_comparison_rejections(mutation):
    p=base_pair();s=p['after'];item=s['items'][0]
    if mutation=='version_reverse':p['before']['version']=3
    elif mutation=='date_reverse':s['issued_at']='2026-11-02T12:00:00+00:00'
    elif mutation=='naive':s['issued_at']='2026-11-04T12:00:00'
    elif mutation=='patient':s['patient_id']='PAT-002'
    elif mutation=='set':s['prescription_set_id']='OTHER'
    elif mutation=='source':s['source']='other'
    elif mutation=='dataset':s['dataset_id']='bidmc'
    elif mutation=='partial':s['complete']=False
    elif mutation=='missing_after':del p['after']
    elif mutation=='missing_items':del s['items']
    elif mutation=='unit':item['dose_unit']='unknown'
    elif mutation=='missing_unit':del item['dose_unit']
    elif mutation=='route':item['route']='unknown'
    elif mutation=='frequency_bool':item['frequency_per_day']=True
    elif mutation=='duration_bool':item['duration_days']=True
    elif mutation=='extra_item':item['extra']='ignored?'
    elif mutation=='extra_snapshot':s['extra']='ignored?'
    elif mutation=='extra_pair':p['extra']='ignored?'
    elif mutation=='missing_value':del item['dose_value']
    elif mutation=='bad_id':item['item_id']=' RX-001'
    with pytest.raises(ValueError):compare_prescriptions(encode(p))


@pytest.mark.parametrize('raw',[b'{"before":null,"before":null,"after":null}',b'{"before":NaN,"after":null}',b'\xff',b'not json'])
def test_strict_json(raw):
    with pytest.raises(ValueError):compare_prescriptions(raw)


def test_exact_decimal_canonicalization_without_precision_loss():
    p=base_pair()
    value='123456789012345678901234567890.123456789'
    p['before']['items'][0]['dose_value']=value+'00'
    p['after']['items'][0]['dose_value']=value
    r=compare_prescriptions(encode(p))
    assert not r.changes and r.after.items[0].dose_value==value
    p['after']['items'][0]['dose_value']='0.001'
    assert compare_prescriptions(encode(p)).changes[0].after.dose_value=='0.001'
    p['before']['items'][0]['dose_value']='010.00';p['after']['items'][0]['dose_value']='10'
    assert not compare_prescriptions(encode(p)).changes


def test_nfc_preserves_case_and_instructions_empty():
    p=base_pair()
    p['before']['items'][0]['instructions']='Observação'
    p['after']['items'][0]['instructions']=unicodedata.normalize('NFD','Observação')
    assert not compare_prescriptions(encode(p)).changes
    p['after']['items'][0]['instructions']='observação'
    assert compare_prescriptions(encode(p)).changes[0].field_changes[0].field=='instructions'
    p['after']['items'][0]['instructions']=''
    assert compare_prescriptions(encode(p)).after.items[0].instructions==''


def test_hashes_distinguish_original_pair_from_canonical_snapshots():
    p=base_pair();p['after']=deepcopy(p['before'])
    raw=encode(p);r=compare_prescriptions(raw)
    assert r.input_pair_sha256==hashlib.sha256(raw).hexdigest()
    assert r.before_canonical_sha256==r.after_canonical_sha256
    p['after']['items'][0]['dose_value']='10.00'
    other=compare_prescriptions(encode(p))
    assert r.input_pair_sha256!=other.input_pair_sha256
    assert r.after_canonical_sha256==other.after_canonical_sha256
    with pytest.raises(FrozenInstanceError):r.status='changed'


def test_mixed_changes_sorted_with_values_and_unit_warning():
    p=base_pair();base=deepcopy(p['before']['items'][0])
    p['before']['items'].append({**base,'item_id':'RX-003'})
    p['after']['items'].append({**base,'item_id':'RX-002'})
    p['after']['items'][0]['dose_unit']='g'
    r=compare_prescriptions(encode(p))
    assert [(c.item_id,c.kind) for c in r.changes]==[('RX-001','modified'),('RX-002','included'),('RX-003','removed')]
    assert r.changes[0].unit_change_note
    assert asdict(r)['changes'][0]['before']['dose_unit']=='mg'
