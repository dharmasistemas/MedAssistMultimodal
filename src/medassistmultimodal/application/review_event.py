"""Explicit review requests; a status transition is not a clinical certification."""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal
from uuid import UUID

from medassistmultimodal.domain.events import ReviewStatus, MultimodalEvent
from medassistmultimodal.domain.session import require_uuid, require_text, utc_datetime
from .audit import AuditRecord


@dataclass(frozen=True, slots=True, kw_only=True)
class EventReviewRequest:
    review_id: UUID
    event_id: UUID
    reviewer_ref: str
    reviewed_at: datetime
    reason: str
    target_status: ReviewStatus
    expected_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    scope: Literal['human_review', 'technical_simulation'] = 'human_review'

    def __post_init__(self):
        require_uuid(self.review_id, 'review_id'); require_uuid(self.event_id, 'event_id')
        if not isinstance(self.reviewer_ref,str) or re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}',self.reviewer_ref) is None:
            raise ValueError('Opaque reviewer reference required')
        require_text(self.reason, 'reason')
        if len(self.reason)>500 or any(ord(c)<32 for c in self.reason):
            raise ValueError('Reason must be a single line up to 500 characters')
        if self.expected_status is not ReviewStatus.PENDING_REVIEW:
            raise ValueError('Only pending events can receive a first review')
        if not isinstance(self.target_status,ReviewStatus) or self.target_status not in (
                ReviewStatus.REVIEWED,ReviewStatus.DISMISSED):
            raise ValueError('Review target must be reviewed or dismissed')
        if self.scope not in ('human_review','technical_simulation'):
            raise ValueError('Explicit review scope required')
        object.__setattr__(self,'reviewed_at',utc_datetime(self.reviewed_at,'reviewed_at'))


def review_audit_record(request: EventReviewRequest, event: MultimodalEvent):
    return AuditRecord(correlation_id=str(request.review_id),patient_id=event.patient_id,
        operation='review_multimodal_event',decision='human_validation',provider=None,model=None,
        latency_ms=None,requires_human_validation=True,error_code=None,
        sources=({'session_id':str(event.session_id),'evidence_ref':event.evidence_ref},),
        events=({'event_id':str(event.event_id),'before_status':request.expected_status.value,
                 'after_status':request.target_status.value,'reviewer_ref':request.reviewer_ref,
                 'reviewed_at':request.reviewed_at.isoformat(timespec='microseconds'),
                 'reason':request.reason,'scope':request.scope,
                 'clinical_validation':False},))
