"""Exact comparison with a declared fictional plan; no therapeutic judgement."""
from dataclasses import asdict,dataclass
from datetime import datetime
import re

from .prescriptions import PrescriptionSnapshot,FIELDS,_object,_snapshot,_sha,_timestamp


@dataclass(frozen=True,slots=True)
class ExpectedDifference:
    item_id: str
    field: str
    expected: str | int | None
    observed: str | int | None


@dataclass(frozen=True,slots=True)
class ExpectationAssessment:
    processor: str
    status: str
    reason: str
    differences: tuple[ExpectedDifference,...]
    clinical_validation: bool = False
    confidence: None = None


def snapshot_from_result(raw):
    return _snapshot(dict(**raw,schema_version='synthetic-prescriptions-v1',subject_kind='synthetic_patient',
        source_kind='synthetic',source='synthetic-prescriptions-fixture-v1',dataset_id=None,
        participant_ref=None,synthetic=True,complete=True))


def assess_expectation(before:PrescriptionSnapshot,after:PrescriptionSnapshot,plan):
    if not isinstance(before,PrescriptionSnapshot) or not isinstance(after,PrescriptionSnapshot):
        raise ValueError('Typed snapshots required')
    def result(status,reason,differences=()):
        return ExpectationAssessment('prescription-expectation-v1',status,reason,tuple(differences))
    if plan is None:return result('indeterminate','plan_missing')
    _object(plan,('schema_version','patient_id','prescription_set_id','before_canonical_sha256',
        'target_version','declared_at','expected_items'))
    if plan['schema_version']!='prescription-expectation-v1':raise ValueError('Unsupported plan')
    if not isinstance(plan['patient_id'],str) or not re.fullmatch(r'PAT-[0-9]{3}',plan['patient_id']):raise ValueError('Synthetic patient required')
    if not isinstance(plan['prescription_set_id'],str) or not plan['prescription_set_id'].strip():raise ValueError('Set required')
    if not isinstance(plan['before_canonical_sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',plan['before_canonical_sha256']):raise ValueError('Base hash required')
    if type(plan['target_version']) is not int or plan['target_version']<1:raise ValueError('Target version required')
    declared=datetime.fromisoformat(_timestamp(plan['declared_at']))
    desired=snapshot_from_result({**asdict(after),'items':plan['expected_items']})
    if (before.patient_id!=after.patient_id or before.prescription_set_id!=after.prescription_set_id
        or plan['patient_id']!=before.patient_id or plan['prescription_set_id']!=before.prescription_set_id):
        return result('indeterminate','identity_mismatch')
    if plan['before_canonical_sha256']!=_sha(before):return result('indeterminate','base_mismatch')
    if plan['target_version']!=after.version or after.version<=before.version:return result('indeterminate','version_mismatch')
    if not datetime.fromisoformat(before.issued_at)<=declared<datetime.fromisoformat(after.issued_at):
        return result('indeterminate','plan_time_incompatible')
    old={i.item_id:i for i in before.items};actual={i.item_id:i for i in after.items};expected={i.item_id:i for i in desired.items}
    for identifier in old.keys() & actual.keys():
        if old[identifier].dose_unit!=actual[identifier].dose_unit:return result('indeterminate','unit_change_not_interpreted')
    differences=[]
    for identifier in sorted(expected.keys()|actual.keys()):
        a,b=expected.get(identifier),actual.get(identifier)
        if a is None or b is None:
            differences.append(ExpectedDifference(identifier,'presence','present' if a else 'absent','present' if b else 'absent'))
        else:
            if a.dose_unit!=b.dose_unit:return result('indeterminate','unit_change_not_interpreted')
            for field in FIELDS:
                if getattr(a,field)!=getattr(b,field):
                    differences.append(ExpectedDifference(identifier,field,getattr(a,field),getattr(b,field)))
    return result('divergent','differs_from_declared_plan',differences) if differences else result('compatible','matches_declared_plan')
