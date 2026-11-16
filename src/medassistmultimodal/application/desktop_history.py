"""Read-only presentation contracts; no Tkinter, SQL or provider execution."""
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID


class HistoryError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SessionRow:
    session_id: str
    patient_id: str
    started_at: str


@dataclass(frozen=True, slots=True)
class SessionDetail:
    # Canonical immutable JSON, decoded afresh by presentation callers.
    payload: bytes

    @property
    def document(self):
        import json
        return json.loads(self.payload)


class HistoryReader(Protocol):
    def sessions(self, database: str, patient_id: str) -> tuple[SessionRow, ...]: ...
    def detail(self, database: str, session_id: UUID) -> SessionDetail: ...


@dataclass
class HistoryState:
    status: Literal['idle', 'loading', 'ready', 'empty', 'error'] = 'idle'
    rows: tuple[SessionRow, ...] = ()
    selected_session_id: str | None = None
    detail: SessionDetail | None = None
    error_code: str | None = None
    generation: int = 0

    def begin(self, session_id=None):
        self.generation += 1
        self.status = 'loading'
        self.detail = None
        self.selected_session_id = session_id
        self.error_code = None
        if session_id is None:
            self.rows = ()
        return self.generation

    def receive_detail(self, generation, detail):
        if generation != self.generation:
            return False
        self.detail = detail
        self.status = 'ready'
        return True

    def fail(self, generation, code):
        if generation != self.generation:
            return False
        self.detail = None
        self.status = 'error'
        self.error_code = code
        return True
