"""Uma conexão e uma transação explícita para sessão, eventos e auditoria."""
from contextlib import contextmanager
import sqlite3

from .sqlite_multimodal_schema import require_multimodal_version
from .sqlite_session_repository import SQLiteSessionRepository
from .sqlite_event_repository import SQLiteEventRepository
from .sqlite_audit_repository import SQLiteAuditRepository


class SQLiteMultimodalUnitOfWork:
    def __init__(self, connection: sqlite3.Connection) -> None:
        require_multimodal_version(connection)
        self.connection = connection
        self.sessions = SQLiteSessionRepository(connection)
        self.events = SQLiteEventRepository(connection)
        self.audit = SQLiteAuditRepository(connection)

    @contextmanager
    def transaction(self):
        require_multimodal_version(self.connection)
        if self.connection.in_transaction:
            raise ValueError('Operação exige conexão sem transação ativa')
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield self
            self.connection.execute('COMMIT')
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute('ROLLBACK')
            raise
