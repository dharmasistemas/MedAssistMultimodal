"""Audio integration over the existing unit of work; no schema changes."""
from dataclasses import asdict, replace
import hashlib
import re
from uuid import uuid5

from medassistmultimodal.application.process_audio import ProcessedAudio
from medassistmultimodal.application.register_audio import prepare_audio_registration, verify_prepared_audio
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.application.register_vitals import strict_json
from medassistmultimodal.domain.events import ReviewStatus
from .sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from .sqlite_patient_repository import SQLitePatientRepository


def register_audio_sqlite(prepared, *, connection, store):
    verify_prepared_audio(prepared)
    uow = SQLiteMultimodalUnitOfWork(connection)
    if SQLitePatientRepository(connection).get_by_id(prepared.session.subject.patient_id) is None:
        raise ValueError('Fictional patient must already exist; not created implicitly')
    existing_session = uow.sessions.get_by_id(prepared.session.session_id)
    if existing_session is not None and existing_session != prepared.session:
        raise ValueError('Session identity/time conflict')
    registered = [uow.events.get_by_id(e.event_id) for e in prepared.events]
    if any(old is not None and old != event for old,event in zip(registered,prepared.events)):
        raise ValueError('Run already committed with different metadata or review state')
    if any(e is not None for e in registered) and not all(e is not None for e in registered):
        raise ValueError('Partial audio registration; explicit recovery required')
    store.ensure(prepared, committed=registered[0] is not None)
    if store.read(prepared.evidence_ref) != prepared.evidence:
        raise ValueError('Evidence changed before registration')
    # The file precedes the DB transaction. On rollback it remains as an orphan
    # for explicit retry; no cleanup/deletion or successful registration is claimed.
    return RegisterMultimodalSession(uow).execute(prepared.session, prepared.events,
        correlation_id=uuid5(prepared.run_id, 'register-audio-v1'))


def query_audio_session(session_id, *, connection, store):
    uow = SQLiteMultimodalUnitOfWork(connection)
    session = uow.sessions.get_by_id(session_id)
    if session is None: return None
    cache = {}; seen = {}; rows = []
    for event in uow.events.list_for_session(session_id):
        if event.source != 'simulated-audio-v1': continue
        reference, separator, fragment = event.evidence_ref.partition('#')
        match = re.fullmatch(r'sha256=([0-9a-f]{64})&item=(/summary|/rules/items/[0-9]+)', fragment)
        if not separator or match is None: raise ValueError('Invalid audio evidence pointer')
        sha, pointer = match.groups()
        if (reference, sha) not in cache:
            evidence = store.read(reference)
            if hashlib.sha256(evidence).hexdigest() != sha: raise ValueError('Stored evidence hash mismatch')
            document = strict_json(evidence)
            prepared = prepare_audio_registration(ProcessedAudio(document['summary']['status'], evidence, sha),
                                                  evidence_ref=reference)
            if prepared.session != session: raise ValueError('Evidence belongs to another session')
            cache[(reference, sha)] = (document, {e.event_id:e for e in prepared.events})
            seen[(reference, sha)] = set()
        document, expected = cache[(reference, sha)]
        # Current review is DB metadata; original evidence remains pending_review.
        original = replace(event, review_status=ReviewStatus.PENDING_REVIEW)
        if expected.get(event.event_id) != original: raise ValueError('Event metadata differs from evidence')
        seen[(reference, sha)].add(event.event_id)
        item = document
        for component in pointer.split('/')[1:]:
            item = item[int(component)] if isinstance(item, list) else item[component]
        metadata = asdict(event)
        metadata.update(event_id=str(event.event_id), session_id=str(event.session_id),
                        timestamp=event.timestamp.isoformat())
        rows.append(dict(event=metadata, processing_status=document['summary']['status'], evidence_item=item))
    if any(seen[key] != set(value[1]) for key,value in cache.items()):
        raise ValueError('Audio event group is incomplete')
    return dict(session=dict(session_id=str(session.session_id), patient_id=session.subject.patient_id,
                             subject_kind=session.subject.kind.value, started_at=session.started_at.isoformat()),
                events=rows, clinical_validation=False)
