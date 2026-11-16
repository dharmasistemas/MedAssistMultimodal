"""Read and verify stored prescription snapshots/events without writing or IO in widgets."""
from dataclasses import asdict, fields, replace
from datetime import datetime
import hashlib
import re
from uuid import UUID, uuid5

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_vitals import strict_json, encode_json
from medassistmultimodal.domain.events import MultimodalEvent, SourceKind, ReviewStatus
from medassistmultimodal.domain.session import SubjectKind, require_uuid
from medassistmultimodal.domain.prescriptions import (
    PrescriptionComparison, PrescriptionChange, FieldChange, FIELDS, _snapshot, _sha,
)
from medassistmultimodal.providers.whisper_local import checked_path
from medassistmultimodal.application.register_prescription_expectation import checked_expectation


def _checked_result(document, session):
    result=document['result']
    if (set(result)!={f.name for f in fields(PrescriptionComparison)}
        or document['subject']!=asdict(session.subject)
        or session.subject.kind is not SubjectKind.SYNTHETIC_PATIENT
        or document['time_basis']!='fictional_nominal_utc'
        or result['patient_id']!=session.subject.patient_id
        or result['processor']!='prescription-diff-v1'
        or result['source']!='synthetic-prescriptions-fixture-v1'
        or result['source_kind']!='synthetic' or result['subject_kind']!='synthetic_patient'
        or result['clinical_validation'] is not False): raise ValueError('Prescription identity mismatch')
    snapshots=[]
    for key in ('before','after'):
        raw=result[key]
        if set(raw)!={'patient_id','prescription_set_id','version','issued_at','items'}: raise ValueError()
        parsed=_snapshot(dict(**raw,schema_version='synthetic-prescriptions-v1',subject_kind='synthetic_patient',
            source_kind='synthetic',source='synthetic-prescriptions-fixture-v1',dataset_id=None,
            participant_ref=None,synthetic=True,complete=True))
        if strict_json(encode_json(asdict(parsed)))!=raw or _sha(parsed)!=result[key+'_canonical_sha256']: raise ValueError('Snapshot changed')
        if parsed.patient_id!=session.subject.patient_id or parsed.prescription_set_id!=result['prescription_set_id']:
            raise ValueError('Snapshot identity mismatch')
        snapshots.append(parsed)
    before,after=snapshots
    if datetime.fromisoformat(after.issued_at)!=session.started_at: raise ValueError('Session time mismatch')
    if after.version<before.version: raise ValueError('Reversed versions')
    if after.version==before.version:
        if before!=after: raise ValueError('Same version conflict')
    elif datetime.fromisoformat(after.issued_at)<=datetime.fromisoformat(before.issued_at): raise ValueError('Reversed time')
    if not re.fullmatch(r'[0-9a-f]{64}',result['input_pair_sha256']): raise ValueError('Invalid input hash')
    old={x.item_id:x for x in before.items};new={x.item_id:x for x in after.items};expected=[]
    # Structural consistency check of the stored diff; no rule profile or model runs.
    for identifier in sorted(old.keys()|new.keys()):
        a,b=old.get(identifier),new.get(identifier)
        if a is None:expected.append(PrescriptionChange(identifier,'included',None,b,()))
        elif b is None:expected.append(PrescriptionChange(identifier,'removed',a,None,()))
        elif a!=b:
            changes=tuple(FieldChange(f,getattr(a,f),getattr(b,f)) for f in FIELDS if getattr(a,f)!=getattr(b,f))
            note='Unit representation changed; no clinical equivalence or dose increase inferred.' if a.dose_unit!=b.dose_unit else None
            expected.append(PrescriptionChange(identifier,'modified',a,b,changes,note))
    # JSON uses lists, whereas dataclasses retain tuples.
    def plain(value):
        if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):return [plain(v) for v in value]
        return value
    if plain([asdict(x) for x in expected])!=result['changes']: raise ValueError('Stored diff inconsistent')
    counts={kind:sum(c.kind==kind for c in expected) for kind in ('included','removed','modified')}
    status='changed' if expected else 'unchanged'
    if any(type(result[k+'_count']) is not int or result[k+'_count']!=v for k,v in counts.items()): raise ValueError()
    if result['status']!=status or document['summary']!=dict(status=status,**counts,clinical_validation=False): raise ValueError('Invalid summary')
    return result


def read_prescriptions(root,session,events):
    groups={};cache={};rows=[];documents=[]
    for event in events:
        reference,separator,fragment=event.evidence_ref.partition('#')
        match=re.fullmatch(r'sha256=([0-9a-f]{64})&item=(/summary|/result/changes/[0-9]+|/expectation_candidates/0)',fragment)
        if not separator or not match: raise ValueError('Invalid prescription pointer')
        sha=match.group(1)
        if reference not in cache:
            path=checked_path(reference,root)
            if not path.is_relative_to(root/'data/interim/prescriptions') and not path.is_relative_to(root/'data/interim/audio/desktop_workspaces_v1'):
                raise ValueError('Unsupported evidence area')
            try:raw=path.read_bytes()
            except FileNotFoundError as exc:raise HistoryError('evidence_missing') from exc
            if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Evidence hash mismatch')
            doc=strict_json(raw)
            if doc.get('schema_version') not in ('prescription-evidence-v1','prescription-evidence-v2'):raise HistoryError('evidence_unsupported')
            cache[reference]=(sha,doc)
        if cache[reference][0]!=sha:raise ValueError('Conflicting evidence hashes')
        groups.setdefault(reference,[]).append(event)
    for reference,actual in groups.items():
        sha,doc=cache[reference];run=UUID(doc['run_id']);require_uuid(run,'run_id')
        if uuid5(run,'session')!=session.session_id:raise ValueError('Session mismatch')
        result=_checked_result(doc,session)
        fragments=[('summary',doc['summary'])]+[(f'result/changes/{i}',c) for i,c in enumerate(result['changes'])]
        processor=result['processor']
        if doc['schema_version']=='prescription-evidence-v2':
            checked_expectation(doc);processor=doc['processor']
            fragments += [(f'expectation_candidates/{i}',item) for i,item in enumerate(doc['expectation_candidates'])]
        expected={}
        for fragment,item in fragments:
            event=MultimodalEvent(event_id=uuid5(run,f"{result['input_pair_sha256']}:{sha}:{fragment}"),
                session_id=session.session_id,subject_kind=session.subject.kind,patient_id=session.subject.patient_id,
                source_kind=SourceKind.SYNTHETIC,source='synthetic-prescriptions-v1',timestamp=session.started_at,
                confidence=None,evidence_ref=f'{reference}#sha256={sha}&item=/{fragment}',processor=processor,is_mock=False)
            expected[event.event_id]=(event,item)
        if set(expected)!={e.event_id for e in actual}:raise ValueError('Incomplete prescription group')
        for event in actual:
            original,item=expected[event.event_id]
            if replace(event,review_status=ReviewStatus.PENDING_REVIEW)!=original:raise ValueError('Event mismatch')
            metadata=asdict(event);metadata.update(event_id=str(event.event_id),session_id=str(event.session_id),timestamp=event.timestamp.isoformat())
            rows.append(dict(event=metadata,evidence_item=item,modality='prescriptions'))
        documents.append(dict(reference=reference,sha256=sha,evidence=doc))
    return rows,documents
