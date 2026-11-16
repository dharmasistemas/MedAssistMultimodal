"""Eventos imutáveis, com identidade obtida da sessão e transações do chamador."""
from datetime import datetime
import sqlite3
from uuid import UUID

from medassistmultimodal.domain.events import MultimodalEvent, SourceKind, ReviewStatus
from medassistmultimodal.domain.session import SubjectKind, require_uuid
from .sqlite_session_repository import SQLiteSessionRepository
from .sqlite_multimodal_schema import require_multimodal_version

_COLUMNS = ('event_id', 'session_id', 'source_kind', 'source', 'timestamp',
            'confidence', 'evidence_ref', 'review_status', 'processor', 'is_mock')
_SELECT = ','.join('e.' + name for name in _COLUMNS)
_JOIN = ' FROM multimodal_events e LEFT JOIN multimodal_sessions s ON s.session_id=e.session_id '
_IDENTITY = ',s.subject_kind,s.patient_id,s.dataset_id,s.participant_ref'


def _values(event: MultimodalEvent) -> tuple:
    return (str(event.event_id), str(event.session_id), event.source_kind.value,
            event.source, event.timestamp.isoformat(timespec='microseconds'),
            None if event.confidence is None else float(event.confidence), event.evidence_ref,
            event.review_status.value, event.processor, int(event.is_mock))


def _event(row) -> MultimodalEvent | None:
    if row is None:
        return None
    try:
        if type(row[9]) is not int or row[9] not in (0, 1):
            raise ValueError('is_mock inválido')
        value = MultimodalEvent(event_id=UUID(row[0]), session_id=UUID(row[1]),
            source_kind=SourceKind(row[2]), source=row[3], timestamp=datetime.fromisoformat(row[4]),
            confidence=row[5], evidence_ref=row[6], review_status=ReviewStatus(row[7]),
            processor=row[8], is_mock=bool(row[9]), subject_kind=SubjectKind(row[10]),
            patient_id=row[11], dataset_id=row[12], participant_ref=row[13])
        if _values(value) != tuple(row[:10]):
            raise ValueError('Representação não canônica')
        return value
    except (ValueError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError('Integridade inválida do evento persistido') from error


class SQLiteEventRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.sessions = SQLiteSessionRepository(connection)

    def _require_ready(self) -> None:
        require_multimodal_version(self.connection)

    def save(self, event: MultimodalEvent) -> None:
        self._require_ready()
        if not isinstance(event, MultimodalEvent):
            raise ValueError('event deve ser MultimodalEvent')
        session = self.sessions.get_by_id(event.session_id)
        if session is None:
            raise ValueError('Sessão inexistente')
        event.validate_for_session(session)
        existing = self.get_by_id(event.event_id)
        if existing is not None:
            if existing != event:
                raise ValueError('event_id já existe com conteúdo diferente')
            return
        if event.review_status is not ReviewStatus.PENDING_REVIEW:
            raise ValueError('Evento novo deve iniciar pending_review')
        self.connection.execute(
            'INSERT INTO multimodal_events (' + ','.join(_COLUMNS) + ') '
            'VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(event_id) DO NOTHING', _values(event))
        if self.get_by_id(event.event_id) != event:
            raise ValueError('event_id já existe com conteúdo diferente')

    def get_by_id(self, event_id: UUID) -> MultimodalEvent | None:
        self._require_ready()
        require_uuid(event_id, 'event_id')
        row = self.connection.execute('SELECT ' + _SELECT + _IDENTITY + _JOIN +
            'WHERE e.event_id=?', (str(event_id),)).fetchone()
        event = _event(row)
        if event is not None:
            session = self.sessions.get_by_id(event.session_id)
            event.validate_for_session(session)
        return event

    def list_for_session(self, session_id: UUID) -> tuple[MultimodalEvent, ...]:
        self._require_ready()
        require_uuid(session_id, 'session_id')
        session = self.sessions.get_by_id(session_id)
        if session is None:
            return ()
        rows = self.connection.execute('SELECT ' + _SELECT + _IDENTITY + _JOIN +
            'WHERE e.session_id=? ORDER BY e.timestamp,e.event_id', (str(session_id),)).fetchall()
        events = tuple(_event(row) for row in rows)
        for event in events:
            event.validate_for_session(session)
        return events
