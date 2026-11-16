"""Atomic review-status update plus immutable audit, using the existing schema."""
import json

from medassistmultimodal.application.review_event import EventReviewRequest, review_audit_record
from medassistmultimodal.domain.session import require_uuid
from .sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork


def review_event_sqlite(request: EventReviewRequest, *, connection):
    if not isinstance(request,EventReviewRequest):raise ValueError('Typed review request required')
    request.__post_init__()
    uow=SQLiteMultimodalUnitOfWork(connection)
    with uow.transaction():
        event=uow.events.get_by_id(request.event_id)
        if event is None:raise ValueError('Event not found')
        if request.scope=='technical_simulation' and not event.is_mock:
            raise ValueError('Technical review simulation is limited to mock events')
        record=review_audit_record(request,event)
        receipt=connection.execute('SELECT audit_record_id FROM audit_records WHERE correlation_id=?',
                                   (str(request.review_id),)).fetchone()
        if receipt is not None:
            # Existing audit save verifies exact payload equality. Do not reinterpret
            # a conflicting review_id as a fresh status change.
            audit_id=uow.audit.save(record)
            if event.review_status!=request.target_status:
                raise ValueError('Review receipt and current event disagree')
            return audit_id
        if event.review_status!=request.expected_status:
            raise ValueError('Stale review state; reopening/corrections need a separate protocol')
        cursor=connection.execute(
            'UPDATE multimodal_events SET review_status=? WHERE event_id=? AND review_status=?',
            (request.target_status.value,str(request.event_id),request.expected_status.value))
        if cursor.rowcount!=1:raise ValueError('Review state conflict')
        return uow.audit.save(record)


def event_review_history(event_id, *, connection):
    require_uuid(event_id,'event_id')
    uow=SQLiteMultimodalUnitOfWork(connection)
    if uow.events.get_by_id(event_id) is None:raise ValueError('Event not found')
    result=[]
    for audit_id,payload in connection.execute('SELECT audit_record_id,payload FROM audit_records ORDER BY audit_record_id'):
        record=json.loads(payload)
        if record['operation']=='review_multimodal_event' and any(
                event.get('event_id')==str(event_id) for event in record['events']):
            result.append(dict(audit_id=audit_id,**record))
    return tuple(result)
