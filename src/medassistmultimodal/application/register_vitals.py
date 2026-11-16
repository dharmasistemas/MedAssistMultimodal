"""Adapt a real deterministic run on fictional inputs to existing event contracts."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
from uuid import UUID, uuid5
from collections.abc import Callable

from medassistmultimodal.domain.events import MultimodalEvent, SourceKind
from medassistmultimodal.domain.session import Session, SubjectIdentity, SubjectKind, require_uuid
from medassistmultimodal.domain.vitals import analyze_vitals, VitalsProfile
from .register_multimodal_session import RegisterMultimodalSession


def strict_json(data: bytes):
    def reject(value):
        raise ValueError(f'Nonfinite JSON value: {value}')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(data, parse_constant=reject, object_pairs_hook=pairs)


def encode_json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


@dataclass(frozen=True, slots=True)
class PreparedVitals:
    run_id: UUID
    session: Session
    events: tuple[MultimodalEvent, ...]
    evidence: bytes
    evidence_sha256: str


def prepare_vitals(input_bytes: bytes, *, run_id: UUID, evidence_ref: str,
                   profile: VitalsProfile = VitalsProfile()) -> PreparedVitals:
    require_uuid(run_id, 'run_id')
    if not isinstance(evidence_ref, str) or not evidence_ref.strip() or '#' in evidence_ref:
        raise ValueError('Unfragmented evidence reference required')
    payload = strict_json(input_bytes)
    result = analyze_vitals(payload, input_sha256=hashlib.sha256(input_bytes).hexdigest(), profile=profile)
    session = Session(session_id=uuid5(run_id, 'session'),
                      subject=SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT,
                                              patient_id=payload['patient_id']),
                      started_at=datetime.fromisoformat(payload['started_at']))
    content = {'schema_version': 'vitals-evidence-v1', 'run_id': str(run_id),
               'subject': asdict(session.subject), 'time_basis': payload['time_basis'],
               'scenario_id': payload['scenario_id'], 'result': asdict(result),
               'summary': {'occurrences': len(result.occurrences),
                           'quality_intervals': len(result.quality_intervals),
                           'absence_is_not_normality': True}}
    evidence = encode_json(content)
    sha = hashlib.sha256(evidence).hexdigest()
    items = [('summary', session.started_at)]
    items += [(f'result/occurrences/{i}', datetime.fromisoformat(o.confirmed_timestamp))
              for i, o in enumerate(result.occurrences)]
    items += [(f'result/quality_intervals/{i}', session.started_at + timedelta(seconds=q.first_index))
              for i, q in enumerate(result.quality_intervals)]
    events = tuple(MultimodalEvent(
        event_id=uuid5(run_id, f'{result.input_sha256}:{sha}:{fragment}'),
        session_id=session.session_id, subject_kind=session.subject.kind,
        patient_id=session.subject.patient_id, source_kind=SourceKind.SYNTHETIC,
        source='synthetic-vitals-v1', timestamp=timestamp, confidence=None,
        evidence_ref=f'{evidence_ref}#sha256={sha}&item=/{fragment}',
        processor=result.processor, is_mock=False) for fragment, timestamp in items)
    return PreparedVitals(run_id, session, events, evidence, sha)


def register_prepared_vitals(prepared: PreparedVitals, use_case: RegisterMultimodalSession,
                             read_evidence: Callable[[], bytes]) -> int:
    """Evidence must already exist; never repair or overwrite it during registration."""
    actual = read_evidence()
    if actual != prepared.evidence or hashlib.sha256(actual).hexdigest() != prepared.evidence_sha256:
        raise ValueError('Evidence differs from the prepared result')
    return use_case.execute(prepared.session, prepared.events,
                            correlation_id=uuid5(prepared.run_id, 'register-vitals'))
