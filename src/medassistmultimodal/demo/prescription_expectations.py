"""Declared synthetic contexts and observed documents; labels are separate from input."""
from copy import deepcopy
from .prescription_fixtures import base_pair
from medassistmultimodal.domain.prescriptions import _snapshot,_sha


def expectation_cases():
    # Plan is defined from the baseline and its own intended 15 mg state, not observed output.
    pair=base_pair();pair['after']['items'][0]['dose_value']='15'
    intended=deepcopy(pair['before']['items']);intended[0]['dose_value']='15'
    plan=dict(schema_version='prescription-expectation-v1',patient_id='PAT-001',
        prescription_set_id=pair['before']['prescription_set_id'],
        before_canonical_sha256=_sha(_snapshot(pair['before'])),target_version=pair['after']['version'],
        declared_at=pair['before']['issued_at'],expected_items=intended)
    cases={f'E{i:02}':dict(pair=deepcopy(pair),plan=deepcopy(plan)) for i in range(1,9)}
    cases['E02']['pair']['after']['items'][0]['dose_value']='20'
    cases['E03']['plan']=None
    cases['E04']['pair']['after']['items'][0].update(dose_value='0.015',dose_unit='g')
    cases['E05']['plan']['before_canonical_sha256']='0'*64
    extra=deepcopy(intended[0]);extra.update(item_id='RX-002',product_code='DEMO-B')
    cases['E06']['plan']['expected_items'].append(deepcopy(extra))
    cases['E07']['pair']['after']['items'].append(deepcopy(extra))
    cases['E08']['pair']['after']['items']=[]
    references={'E01':'compatible','E02':'divergent','E03':'indeterminate','E04':'indeterminate',
        'E05':'indeterminate','E06':'divergent','E07':'divergent','E08':'divergent'}
    return cases,references
