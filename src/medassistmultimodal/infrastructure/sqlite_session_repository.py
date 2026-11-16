"""Sessões imutáveis; commit/rollback pertencem ao chamador."""
from datetime import datetime
import sqlite3
from uuid import UUID

from medassistmultimodal.domain.session import Session, SubjectIdentity, SubjectKind, require_text, require_uuid
from .sqlite_multimodal_schema import require_foreign_keys, require_multimodal_version

_COLUMNS = 'session_id,subject_kind,patient_id,dataset_id,participant_ref,started_at'


def _values(session: Session) -> tuple:
    return (str(session.session_id), session.subject.kind.value, session.subject.patient_id,
            session.subject.dataset_id, session.subject.participant_ref,
            session.started_at.isoformat(timespec='microseconds'))


def _session(row) -> Session | None:
    if row is None:
        return None
    try:
        value = Session(session_id=UUID(row[0]),
            subject=SubjectIdentity(kind=SubjectKind(row[1]), patient_id=row[2],
                                    dataset_id=row[3], participant_ref=row[4]),
            started_at=datetime.fromisoformat(row[5]))
        if _values(value) != tuple(row):
            raise ValueError('Representação não canônica')
        return value
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError('Integridade inválida da sessão persistida') from error


class SQLiteSessionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        require_foreign_keys(connection)
        self.connection = connection
        self._require_ready()

    def _require_ready(self) -> None:
        require_multimodal_version(self.connection)

    def save(self, session: Session) -> None:
        self._require_ready()
        if not isinstance(session, Session):
            raise ValueError('session deve ser Session')
        values = _values(session)
        self.connection.execute(
            f'INSERT INTO multimodal_sessions ({_COLUMNS}) VALUES (?,?,?,?,?,?) '
            'ON CONFLICT(session_id) DO NOTHING', values)
        stored = self.get_by_id(session.session_id)
        if stored != session:
            raise ValueError('session_id já existe com conteúdo diferente')

    def get_by_id(self, session_id: UUID) -> Session | None:
        self._require_ready()
        require_uuid(session_id, 'session_id')
        return _session(self.connection.execute(
            f'SELECT {_COLUMNS} FROM multimodal_sessions WHERE session_id=?', (str(session_id),)).fetchone())

    def list_for_patient(self, patient_id: str) -> tuple[Session, ...]:
        SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT, patient_id=patient_id)
        return self._list('patient_id=?', (patient_id,))

    def list_for_dataset_participant(self, dataset_id: str, participant_ref: str) -> tuple[Session, ...]:
        require_text(dataset_id, 'dataset_id')
        require_text(participant_ref, 'participant_ref')
        return self._list('dataset_id=? AND participant_ref=?', (dataset_id, participant_ref))

    def _list(self, predicate, parameters) -> tuple[Session, ...]:
        self._require_ready()
        return tuple(_session(row) for row in self.connection.execute(
            f'SELECT {_COLUMNS} FROM multimodal_sessions WHERE {predicate} ORDER BY started_at,session_id',
            parameters))
