"""Identidade independente de providers e persistência."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import re
from uuid import UUID


def require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} deve ser texto não vazio, sem espaços externos")


def require_uuid(value: UUID, field: str) -> None:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{field} deve ser UUID não nulo")


def utc_datetime(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} deve incluir fuso horário")
    return value.astimezone(timezone.utc)


class SubjectKind(StrEnum):
    SYNTHETIC_PATIENT = "synthetic_patient"
    DATASET_PARTICIPANT = "dataset_participant"


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectIdentity:
    kind: SubjectKind
    patient_id: str | None = None
    dataset_id: str | None = None
    participant_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SubjectKind):
            raise ValueError("kind deve ser SubjectKind")
        if self.kind is SubjectKind.SYNTHETIC_PATIENT:
            if not isinstance(self.patient_id, str) or re.fullmatch(r"PAT-[0-9]{3}", self.patient_id) is None:
                raise ValueError("patient_id deve seguir PAT-000")
            if self.dataset_id is not None or self.participant_ref is not None:
                raise ValueError("paciente sintético não pode ter identidade de dataset")
        else:
            if self.patient_id is not None:
                raise ValueError("participante de dataset não pode ter patient_id")
            require_text(self.dataset_id, "dataset_id")
            require_text(self.participant_ref, "participant_ref")


@dataclass(frozen=True, slots=True, kw_only=True)
class Session:
    session_id: UUID
    subject: SubjectIdentity
    started_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.session_id, "session_id")
        if not isinstance(self.subject, SubjectIdentity):
            raise ValueError("subject deve ser SubjectIdentity")
        object.__setattr__(self, "started_at", utc_datetime(self.started_at, "started_at"))
