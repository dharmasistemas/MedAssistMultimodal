"""Versioned expectation envelope, keeping original prescription preparation unchanged."""
from dataclasses import asdict,replace
import hashlib
from uuid import uuid5

from .register_prescriptions import prepare_prescriptions,PreparedPrescriptions
from .register_vitals import encode_json,strict_json
from medassistmultimodal.domain.prescription_expectation import assess_expectation,snapshot_from_result


def checked_expectation(document):
    r=document['result']
    expected=asdict(assess_expectation(snapshot_from_result(r['before']),snapshot_from_result(r['after']),document['expectation_plan']))
    if encode_json(expected)!=encode_json(document['expectation']):raise ValueError('Expectation differs')
    candidates=[expected] if expected['status']=='divergent' else []
    if encode_json(candidates)!=encode_json(document['expectation_candidates']):raise ValueError('Invalid candidates')
    if document['processor']!='prescription-expectation-v1':raise ValueError('Invalid processor')
    return expected


def prepare_prescription_expectation(input_bytes,plan,*,run_id,evidence_ref):
    base=prepare_prescriptions(input_bytes,run_id=run_id,evidence_ref=evidence_ref)
    doc=strict_json(base.evidence);r=doc['result']
    assessment=asdict(assess_expectation(snapshot_from_result(r['before']),snapshot_from_result(r['after']),plan))
    doc.update(schema_version='prescription-evidence-v2',processor='prescription-expectation-v1',
        expectation_plan=plan,expectation=assessment,expectation_candidates=[assessment] if assessment['status']=='divergent' else [])
    raw=encode_json(doc);sha=hashlib.sha256(raw).hexdigest()
    fragments=['summary']+[f'result/changes/{i}' for i in range(len(r['changes']))]
    if doc['expectation_candidates']:fragments.append('expectation_candidates/0')
    events=tuple(replace(base.events[0],event_id=uuid5(run_id,f"{r['input_pair_sha256']}:{sha}:{fragment}"),
        processor=doc['processor'],evidence_ref=f'{evidence_ref}#sha256={sha}&item=/{fragment}') for fragment in fragments)
    return PreparedPrescriptions(run_id,base.session,events,raw,sha)
