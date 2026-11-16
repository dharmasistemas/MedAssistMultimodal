"""Bind prepared audio evidence to existing immutable sessions/events/audit."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from uuid import UUID, uuid5

from medassistmultimodal.domain.events import MultimodalEvent, SourceKind
from medassistmultimodal.domain.session import Session, SubjectIdentity, SubjectKind
from .process_audio import ProcessedAudio
from .register_vitals import strict_json, encode_json


@dataclass(frozen=True, slots=True)
class PreparedAudioRegistration:
    run_id: UUID
    session: Session
    events: tuple[MultimodalEvent, ...]
    evidence: bytes
    evidence_sha256: str
    evidence_ref: str


def _prepare_audio_registration(result: ProcessedAudio, *, evidence_ref: str):
    if not isinstance(result, ProcessedAudio) or not isinstance(result.evidence, bytes):
        raise ValueError('Processed audio required')
    if (not isinstance(evidence_ref, str) or not evidence_ref or '#' in evidence_ref
            or '\\' in evidence_ref or not evidence_ref.startswith('data/interim/audio/')
            or not evidence_ref.endswith('.json')
            or any(p in ('', '.', '..') or p.casefold() in ('_backup', '.git') for p in evidence_ref.split('/'))):
        raise ValueError('Canonical relative audio evidence reference required')
    sha = hashlib.sha256(result.evidence).hexdigest()
    if sha != result.evidence_sha256: raise ValueError('Prepared evidence hash mismatch')
    doc = strict_json(result.evidence)
    if encode_json(doc) != result.evidence or doc.get('schema_version') != 'audio-processing-evidence-v1':
        raise ValueError('Canonical versioned audio evidence required')
    if result.status not in ('completed', 'degraded', 'failed') or doc['summary']['status'] != result.status:
        raise ValueError('Rejected/inconsistent processing cannot be registered')
    identity = doc['identity']; run_id = UUID(identity['run_id'])
    if run_id.int == 0 or str(run_id) != identity['run_id']: raise ValueError('Canonical run UUID required')
    if identity['subject_kind'] != 'synthetic_patient' or identity['source_kind'] != 'simulated':
        raise ValueError('Only simulated fictional-patient audio supported')
    session = Session(session_id=UUID(identity['session_id']),
        subject=SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT, patient_id=identity['patient_id']),
        started_at=datetime.fromisoformat(doc['time']['session_timestamp_utc']))
    inp = doc['input']
    if inp['status'] != 'accepted' or inp.get('permission_declared') is not True:
        raise ValueError('Verified input/provenance required')
    digest = inp['expected_sha256']
    if (not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None
            or inp['observed_sha256'] != digest or inp['final_sha256'] != digest):
        raise ValueError('Unverified media hash')
    asr = doc['asr']; rules = doc['rules']; llm = doc['llm']
    if rules['status'] not in ('succeeded_with_mentions', 'succeeded_no_mentions',
                               'unsupported_input', 'unavailable', 'not_run'):
        raise ValueError('Invalid rule state')
    if llm['status'] not in ('disabled', 'not_configured', 'succeeded', 'unavailable', 'timeout',
                             'invalid_response', 'unsupported_input', 'not_run'):
        raise ValueError('Invalid text state')
    complete = (asr['status'] == 'succeeded' and doc['acoustics']['status'] == 'succeeded'
                and rules['status'] in ('succeeded_with_mentions', 'succeeded_no_mentions')
                and llm['status'] in ('disabled', 'succeeded'))
    if (result.status == 'completed') != complete:
        raise ValueError('Global processing state differs from stages')
    if result.status == 'failed':
        if (asr['status'] not in ('no_speech', 'unavailable', 'invalid_output')
                or rules['status'] != 'not_run' or llm['status'] != 'not_run'):
            raise ValueError('Invalid failed-run state')
    elif asr['status'] != 'succeeded':
        raise ValueError('Successful transcript required for completed/degraded runs')
    if asr['status'] == 'succeeded':
        text = asr['result']['text']
        if (not isinstance(text,str) or not text.strip()
                or hashlib.sha256(text.encode()).hexdigest() != asr['input_text_sha256']
                or asr['result']['evidence_ref'] != f"{inp['audio_ref']}#sha256={digest}"):
            raise ValueError('Transcript provenance/hash mismatch')
    items = rules['items']
    if rules['status'] in ('succeeded_with_mentions', 'succeeded_no_mentions'):
        if not isinstance(items, list) or bool(items) != (rules['status'] == 'succeeded_with_mentions'):
            raise ValueError('Invalid rule items')
    elif items is not None:
        raise ValueError('Failed/skipped rules must not contain items')
    if items:
        text = asr['result']['text']
        for item in items:
            start, end = item['start'], item['end']
            if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
                    or text[start:end] != item['quote'] or item['review_status'] != 'pending_review'):
                raise ValueError('Invalid rule evidence')
            expected_class = ('candidate_for_human_review' if item['context'] == 'affirmed_current'
                              else 'context_uncertain' if item['context'] == 'unknown'
                              else 'context_information' if item['context'] in (
                                  'negated_current','conditional','third_party',
                                  'affirmed_historical','affirmed_earlier_in_session') else None)
            if expected_class is None or item['classification'] != expected_class:
                raise ValueError('Rule classification differs from context')
    asr_mock = asr['provider']['is_mock']
    if type(asr_mock) is not bool: raise ValueError('Invalid ASR mock flag')
    llm_mock = (llm['provider']['is_mock'] if llm.get('provider')
                and llm['status'] not in ('disabled', 'not_run', 'not_configured', 'unsupported_input') else False)
    if type(llm_mock) is not bool: raise ValueError('Invalid LLM mock flag')
    fragments = [('summary', asr_mock or llm_mock or bool(rules.get('is_mock')))]
    fragments += [(f'rules/items/{i}', asr_mock or bool(rules.get('is_mock'))) for i in range(len(items or []))]
    events = tuple(MultimodalEvent(
        event_id=uuid5(run_id, f'audio-processing-v1:{fragment}'),
        session_id=session.session_id, subject_kind=session.subject.kind,
        patient_id=session.subject.patient_id, source_kind=SourceKind.SIMULATED,
        source='simulated-audio-v1', timestamp=session.started_at, confidence=None,
        evidence_ref=f'{evidence_ref}#sha256={sha}&item=/{fragment}',
        processor='audio-processing-v1', is_mock=mock)
        for fragment, mock in fragments)
    return PreparedAudioRegistration(run_id, session, events, result.evidence, sha, evidence_ref)


def prepare_audio_registration(result: ProcessedAudio, *, evidence_ref: str):
    try:
        return _prepare_audio_registration(result, evidence_ref=evidence_ref)
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError('Malformed prepared audio evidence') from exc


def verify_prepared_audio(prepared):
    if not isinstance(prepared, PreparedAudioRegistration): raise ValueError('Prepared audio required')
    rebuilt = prepare_audio_registration(
        ProcessedAudio(strict_json(prepared.evidence)['summary']['status'],
                       prepared.evidence, prepared.evidence_sha256), evidence_ref=prepared.evidence_ref)
    if rebuilt != prepared: raise ValueError('Registration metadata differs from evidence')
