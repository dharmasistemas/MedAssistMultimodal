"""Caso de uso atômico, independente da implementação SQLite."""
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import asdict
from typing import Protocol
from uuid import UUID

from .audit import AuditRecord, AuditRepository
from medassistmultimodal.domain.session import Session, require_uuid
from medassistmultimodal.domain.events import MultimodalEvent


class SessionWriter(Protocol):
    def save(self, session: Session) -> None: ...


class EventWriter(Protocol):
    def save(self, event: MultimodalEvent) -> None: ...


class MultimodalUnitOfWork(Protocol):
    sessions: SessionWriter
    events: EventWriter
    audit: AuditRepository

    def transaction(self) -> AbstractContextManager: ...


def _event_metadata(event: MultimodalEvent) -> dict[str, object]:
    value = asdict(event)
    value.update(event_id=str(event.event_id), session_id=str(event.session_id),
                 timestamp=event.timestamp.isoformat(timespec='microseconds'),
                 confidence=None if event.confidence is None else float(event.confidence))
    return value


class RegisterMultimodalSession:
    def __init__(self, unit_of_work: MultimodalUnitOfWork) -> None:
        self.unit_of_work = unit_of_work

    def execute(self, session: Session, events: Sequence[MultimodalEvent], *,
                correlation_id: UUID) -> int:
        """IDs e instantes vêm do chamador e devem ser preservados em retentativas."""
        if not isinstance(session, Session):
            raise ValueError('session deve ser Session')
        require_uuid(correlation_id, 'correlation_id')
        supplied = tuple(events)
        if any(not isinstance(event, MultimodalEvent) for event in supplied):
            raise ValueError('events deve conter MultimodalEvent')
        ordered = tuple(sorted(supplied, key=lambda event: str(event.event_id)))
        if len({event.event_id for event in ordered}) != len(ordered):
            raise ValueError('event_id duplicado no lote')
        for event in ordered:
            if not isinstance(event, MultimodalEvent):
                raise ValueError('events deve conter MultimodalEvent')
            event.validate_for_session(session)
        # Nenhum relógio, latência variável ou geração de UUID entra no payload idempotente.
        record = AuditRecord(
            correlation_id=str(correlation_id), patient_id=session.subject.patient_id,
            operation='register_multimodal_session', decision='completed',
            provider=None, model=None, latency_ms=None, requires_human_validation=True,
            error_code=None,
            sources=({'session_id': str(session.session_id),
                      'started_at': session.started_at.isoformat(timespec='microseconds'),
                      'subject': asdict(session.subject)},),
            events=tuple(_event_metadata(event) for event in ordered))
        with self.unit_of_work.transaction():
            self.unit_of_work.sessions.save(session)
            for event in ordered:
                self.unit_of_work.events.save(event)
            audit_id = self.unit_of_work.audit.save(record)
        return audit_id
