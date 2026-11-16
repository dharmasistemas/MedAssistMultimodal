"""Adapt fictional prescription comparisons to existing audited event contracts."""
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
from collections.abc import Callable
from uuid import UUID, uuid5

from .register_multimodal_session import RegisterMultimodalSession
from .register_vitals import encode_json
from medassistmultimodal.domain.prescriptions import compare_prescriptions
from medassistmultimodal.domain.session import Session, SubjectIdentity, SubjectKind, require_uuid
from medassistmultimodal.domain.events import MultimodalEvent, SourceKind


@dataclass(frozen=True, slots=True)
class PreparedPrescriptions:
    run_id: UUID
    session: Session
    events: tuple[MultimodalEvent, ...]
    evidence: bytes
    evidence_sha256: str


def prepare_prescriptions(input_bytes: bytes, *, run_id: UUID, evidence_ref: str) -> PreparedPrescriptions:
    require_uuid(run_id,'run_id')
    if not isinstance(evidence_ref,str) or not evidence_ref.strip() or '#' in evidence_ref:
        raise ValueError('Unfragmented evidence reference required')
    result=compare_prescriptions(input_bytes)
    session=Session(session_id=uuid5(run_id,'session'),
        subject=SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT,patient_id=result.patient_id),
        started_at=datetime.fromisoformat(result.after.issued_at))
    content={'schema_version':'prescription-evidence-v1','run_id':str(run_id),
        'subject':asdict(session.subject),'time_basis':'fictional_nominal_utc',
        'result':asdict(result),'summary':{'status':result.status,'included':result.included_count,
        'removed':result.removed_count,'modified':result.modified_count,'clinical_validation':False}}
    evidence=encode_json(content);sha=hashlib.sha256(evidence).hexdigest()
    fragments=['summary']+[f'result/changes/{i}' for i in range(len(result.changes))]
    events=tuple(MultimodalEvent(event_id=uuid5(run_id,f'{result.input_pair_sha256}:{sha}:{fragment}'),
        session_id=session.session_id,subject_kind=session.subject.kind,patient_id=result.patient_id,
        source_kind=SourceKind.SYNTHETIC,source='synthetic-prescriptions-v1',
        timestamp=session.started_at,confidence=None,
        evidence_ref=f'{evidence_ref}#sha256={sha}&item=/{fragment}',processor=result.processor,
        is_mock=False) for fragment in fragments)
    return PreparedPrescriptions(run_id,session,events,evidence,sha)


def register_prepared_prescriptions(prepared: PreparedPrescriptions,
        use_case: RegisterMultimodalSession, read_evidence: Callable[[],bytes]) -> int:
    actual=read_evidence()
    if actual!=prepared.evidence or hashlib.sha256(actual).hexdigest()!=prepared.evidence_sha256:
        raise ValueError('Evidence differs from prepared comparison')
    return use_case.execute(prepared.session,prepared.events,
        correlation_id=uuid5(prepared.run_id,'register-prescriptions'))
