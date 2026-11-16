"""Fixtures v1: conteúdo inteiramente fictício, sem mídia ou inferência clínica."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from medassistmultimodal.domain.events import MultimodalEvent, SourceKind
from medassistmultimodal.domain.session import Session, SubjectIdentity, SubjectKind


@dataclass(frozen=True, slots=True)
class DemoCase:
    name: str
    session: Session
    events: tuple[MultimodalEvent, ...]


def build_demo_cases() -> tuple[DemoCase, ...]:
    """Retorna objetos novos com IDs/datas fixos; não usa RNG, relógio, rede ou disco."""
    cases = []
    for number in (1, 2):
        session = Session(
            session_id=UUID(f"36a94a08-a5f4-4407-9df2-{number:012d}"),
            subject=SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT,
                                    patient_id=f"PAT-{number:03d}"),
            started_at=datetime(2026, 10, 24, 12, number, tzinfo=timezone.utc),
        )
        event = MultimodalEvent(
            event_id=UUID(f"ca87bd5c-2e5f-42cb-82e0-{number:012d}"),
            session_id=session.session_id,
            subject_kind=session.subject.kind, patient_id=session.subject.patient_id,
            source_kind=SourceKind.SYNTHETIC,
            source="medassistmultimodal.demo.fixtures:v1",
            timestamp=session.started_at, confidence=None,
            evidence_ref=f"fixture:v1/case-{number}/event-1",
            processor="fixture_builder:v1", is_mock=True,
        )
        event.validate_for_session(session)
        cases.append(DemoCase(f"case-{number}", session, (event,)))
    return tuple(cases)
