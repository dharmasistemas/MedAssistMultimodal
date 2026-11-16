"""Read-only SQLite composition. Never initializes a DB or changes evidence."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3
from uuid import UUID

from medassistmultimodal.application.desktop_history import HistoryError, SessionDetail, SessionRow
from medassistmultimodal.application.register_vitals import encode_json, strict_json
from medassistmultimodal.domain.session import SubjectIdentity, SubjectKind
from medassistmultimodal.providers.whisper_local import checked_path
from .audio_evidence_store import AudioEvidenceStore
from .sqlite_audio_registration import query_audio_session
from .sqlite_event_review import event_review_history
from .sqlite_session_repository import SQLiteSessionRepository


class _SnapshotStore:
    """Return exactly the same bytes for verification and presentation."""
    def __init__(self, root):
        self.store = AudioEvidenceStore(root)
        self.contents = {}

    def read(self, reference):
        if reference not in self.contents:
            try:
                raw = self.store.read(reference)
            except FileNotFoundError as exc:
                raise HistoryError('evidence_missing') from exc
            document = strict_json(raw)
            if document.get('schema_version') != 'audio-processing-evidence-v1':
                raise HistoryError('evidence_unsupported')
            self.contents[reference] = raw
        return self.contents[reference]


class SQLiteHistoryReader:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()

    @contextmanager
    def _connection(self, database):
        try:
            path = checked_path(database, self.root)
            if not path.is_file():
                raise HistoryError('database_unavailable')
        except (ValueError, OSError) as exc:
            raise HistoryError('database_unavailable') from exc
        connection = None
        try:
            connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            yield connection
        except HistoryError:
            raise
        except (sqlite3.Error, ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            raise HistoryError('history_unavailable') from exc
        finally:
            if connection is not None:
                connection.close()

    def sessions(self, database: str, patient_id: str):
        try:
            SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT, patient_id=patient_id)
        except ValueError as exc:
            raise HistoryError('invalid_patient') from exc
        with self._connection(database) as connection:
            return tuple(SessionRow(str(s.session_id), s.subject.patient_id, s.started_at.isoformat())
                         for s in SQLiteSessionRepository(connection).list_for_patient(patient_id))

    def detail(self, database: str, session_id: UUID):
        with self._connection(database) as connection:
            store = _SnapshotStore(self.root)
            try:
                view = query_audio_session(session_id, connection=connection, store=store)
                if view is None:
                    raise HistoryError('session_not_found')
                documents = []
                for reference, raw in store.contents.items():
                    documents.append(dict(reference=reference, sha256=hashlib.sha256(raw).hexdigest(),
                                          evidence=strict_json(raw)))
                histories = {row['event']['event_id']: event_review_history(
                    UUID(row['event']['event_id']), connection=connection) for row in view['events']}
                return SessionDetail(encode_json(dict(**view, documents=documents,
                    review_histories=histories, integrity='verified' if documents else 'not_checked',
                    access_mode='read_only')))
            except HistoryError:
                raise
            except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
                raise HistoryError('evidence_invalid') from exc
