"""Evento rastreável; confiança não representa probabilidade clínica."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math
from uuid import UUID

from .session import Session, SubjectIdentity, SubjectKind, require_text, require_uuid, utc_datetime


class SourceKind(StrEnum):
    SYNTHETIC = "synthetic"
    SIMULATED = "simulated"
    DATASET = "dataset"


class ReviewStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True, kw_only=True)
class MultimodalEvent:
    event_id: UUID
    session_id: UUID
    subject_kind: SubjectKind
    patient_id: str | None
    source_kind: SourceKind
    source: str
    timestamp: datetime
    confidence: float | None
    evidence_ref: str
    dataset_id: str | None = None
    participant_ref: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    processor: str | None = None
    is_mock: bool = False

    @property
    def subject(self) -> SubjectIdentity:
        return SubjectIdentity(kind=self.subject_kind, patient_id=self.patient_id,
                               dataset_id=self.dataset_id, participant_ref=self.participant_ref)

    def __post_init__(self) -> None:
        require_uuid(self.event_id, "event_id")
        require_uuid(self.session_id, "session_id")
        subject = self.subject
        if not isinstance(self.source_kind, SourceKind):
            raise ValueError("source_kind deve ser SourceKind")
        if not isinstance(self.review_status, ReviewStatus):
            raise ValueError("review_status deve ser ReviewStatus")
        is_dataset = subject.kind is SubjectKind.DATASET_PARTICIPANT
        if (self.source_kind is SourceKind.DATASET) != is_dataset:
            raise ValueError("origem incompatível com identidade")
        require_text(self.source, "source")
        require_text(self.evidence_ref, "evidence_ref")
        object.__setattr__(self, "timestamp", utc_datetime(self.timestamp, "timestamp"))
        if self.confidence is not None:
            if (isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float))
                    or not 0 <= self.confidence <= 1 or not math.isfinite(self.confidence)):
                raise ValueError("confidence deve ser None ou número finito entre 0 e 1")
        if not isinstance(self.is_mock, bool):
            raise ValueError("is_mock deve ser bool")
        if self.processor is not None:
            require_text(self.processor, "processor")
        if self.is_mock and self.processor is None:
            raise ValueError("resultado mock exige processor identificado")

    def validate_for_session(self, session: Session) -> None:
        """O caso de uso deve chamar esta validação antes de aceitar o evento."""
        if not isinstance(session, Session):
            raise ValueError("session deve ser Session")
        if self.session_id != session.session_id or self.subject != session.subject:
            raise ValueError("evento não pertence à sessão/sujeito informado")
