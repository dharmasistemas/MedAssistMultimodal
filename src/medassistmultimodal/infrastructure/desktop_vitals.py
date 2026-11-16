"""Verified read-only vital evidence; raw series is optional and separately checked."""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import re
from uuid import UUID, uuid5

from medassistmultimodal.application.desktop_history import HistoryError, SessionDetail
from medassistmultimodal.application.register_vitals import strict_json, encode_json
from medassistmultimodal.domain.events import MultimodalEvent, SourceKind, ReviewStatus
from medassistmultimodal.domain.session import SubjectKind
from medassistmultimodal.domain.vitals import UNITS, validate_vital_series, VitalsProfile
from medassistmultimodal.providers.whisper_local import checked_path
from .desktop_history import SQLiteHistoryReader, _SnapshotStore
from .sqlite_audio_registration import query_audio_session
from .sqlite_event_repository import SQLiteEventRepository
from .sqlite_event_review import event_review_history
from .sqlite_session_repository import SQLiteSessionRepository
from .desktop_prescriptions import read_prescriptions
from .desktop_acoustics import read_acoustics

MODALITIES = {'simulated-audio-v1': 'Áudio', 'synthetic-vitals-v1': 'Vitais',
              'synthetic-prescriptions-v1': 'Prescrições','simulated-acoustic-pauses-v1':'Pausas de áudio'}


@dataclass(frozen=True, slots=True)
class ModalitySessionRow:
    session_id: str
    patient_id: str
    started_at: str
    modalities: tuple[str, ...]
    registered_at: str | None = None

    @property
    def display_at(self):
        return self.registered_at or self.started_at


def registration_times(connection):
    """First durable registration, not nominal data time or later review time."""
    import json
    result = {}
    for payload, created in connection.execute('SELECT payload,created_at FROM audit_records ORDER BY audit_record_id'):
        record = json.loads(payload)
        if record.get('operation') != 'register_multimodal_session':
            continue
        for source in record.get('sources', []):
            if source.get('session_id'):
                stamp = datetime.fromisoformat(created.replace('Z', '+00:00'))
                if stamp.tzinfo is None: raise ValueError('Registration time requires timezone')
                result.setdefault(source['session_id'], stamp.isoformat())
    return result


class MultimodalHistoryReader(SQLiteHistoryReader):
    def sessions(self, database, patient_id):
        # Reuse patient validation, then take a new internally consistent read snapshot.
        super().sessions(database, patient_id)
        with self._connection(database) as connection:
            events = SQLiteEventRepository(connection)
            times = registration_times(connection)
            return tuple(ModalitySessionRow(str(s.session_id), s.subject.patient_id, s.started_at.isoformat(),
                tuple(sorted({MODALITIES.get(e.source, 'Não suportada') for e in events.list_for_session(s.session_id)})),
                times.get(str(s.session_id)) if any(e.source in ('synthetic-vitals-v1','synthetic-prescriptions-v1') for e in events.list_for_session(s.session_id)) else None)
                for s in SQLiteSessionRepository(connection).list_for_patient(patient_id))

    def _raw_series(self, document, session):
        result = document['result']; scenario = document['scenario_id']
        if not isinstance(scenario, str) or not re.fullmatch(r'V[0-9]{2}', scenario):
            return dict(status='unavailable', samples=[], reference=None)
        reference = f'data/synthetic/vitals_v1/{scenario}.json'
        try:
            manifest = strict_json(checked_path('data/synthetic/vitals_v1/manifest.json', self.root).read_bytes())
            declared = manifest['files'][scenario+'.json']['sha256']
            raw = checked_path(reference, self.root).read_bytes()
        except FileNotFoundError:
            return dict(status='unavailable', samples=[], reference=reference)
        except (ValueError, OSError, KeyError, TypeError):
            return dict(status='divergent', samples=[], reference=reference)
        if hashlib.sha256(raw).hexdigest()!=result['input_sha256'] or declared!=result['input_sha256']:
            return dict(status='divergent', samples=[], reference=reference)
        try:
            payload = strict_json(raw)
            samples = validate_vital_series(payload)
            if (payload['scenario_id']!=scenario or payload['series_id']!=result['series_id']
                or payload['patient_id']!=session.subject.patient_id
                or datetime.fromisoformat(payload['started_at'])!=session.started_at
                or payload['source']!=result['source']): raise ValueError()
            values=[]
            for sample, original in zip(samples, payload['samples']):
                for (channel, unit), value in zip(UNITS.items(), sample.channels):
                    values.append(dict(index=sample.sample_index, timestamp=sample.timestamp.isoformat(),
                        channel=channel, unit=unit, value=value.value, quality=value.quality,
                        reported_quality=original[channel]['quality'], reason=value.reason))
            return dict(status='verified', samples=values, reference=reference)
        except (ValueError, KeyError, TypeError):
            return dict(status='divergent', samples=[], reference=reference)

    def _vitals(self, session, events):
        groups={}; cache={}
        for event in events:
            reference, separator, fragment = event.evidence_ref.partition('#')
            match = re.fullmatch(r'sha256=([0-9a-f]{64})&item=(/summary|/result/(occurrences|quality_intervals)/[0-9]+)',fragment)
            if not separator or not match: raise ValueError('Invalid vital pointer')
            sha=match.group(1)
            if reference not in cache:
                path=checked_path(reference,self.root)
                if not path.is_relative_to(self.root/'data/interim/vitals') and not path.is_relative_to(self.root/'data/interim/audio/desktop_workspaces_v1'):
                    raise ValueError('Unsupported vital evidence area')
                try: raw=path.read_bytes()
                except FileNotFoundError as exc: raise HistoryError('evidence_missing') from exc
                if hashlib.sha256(raw).hexdigest()!=sha: raise ValueError('Vital evidence hash mismatch')
                doc=strict_json(raw)
                if doc.get('schema_version')!='vitals-evidence-v1': raise HistoryError('evidence_unsupported')
                cache[reference]=(sha,doc)
            if cache[reference][0]!=sha: raise ValueError('Conflicting hashes')
            groups.setdefault(reference,[]).append(event)
        documents=[]; rows=[]
        for reference,actual in groups.items():
            sha,doc=cache[reference];result=doc['result'];run=UUID(doc['run_id'])
            if (str(uuid5(run,'session'))!=str(session.session_id) or doc['subject']!=asdict(session.subject)
                or session.subject.kind is not SubjectKind.SYNTHETIC_PATIENT
                or doc['time_basis']!='fictional_nominal_utc' or result['processor']!='vitals-rules-v1'
                or result['clinical_validation'] is not False): raise ValueError('Vital identity mismatch')
            if not re.fullmatch(r'[0-9a-f]{64}',result['input_sha256']): raise ValueError('Invalid input hash')
            VitalsProfile(result['profile_version'],result['persistence'],tuple(tuple(p) for p in result['bounds']))
            if (doc['summary']['occurrences']!=len(result['occurrences'])
                or doc['summary']['quality_intervals']!=len(result['quality_intervals'])
                or doc['summary']['absence_is_not_normality'] is not True): raise ValueError('Invalid vital summary')
            if {c['channel'] for c in result['coverage']}!=set(UNITS) or len(result['coverage'])!=4: raise ValueError()
            totals=set()
            for c in result['coverage']:
                if (type(c['total_samples']) is not int or type(c['valid_samples']) is not int
                    or not 0<=c['valid_samples']<=c['total_samples'] or c['total_samples']<=0
                    or type(c['fraction']) not in (float,int)
                    or c['fraction']!=c['valid_samples']/c['total_samples']): raise ValueError('Invalid coverage')
                totals.add(c['total_samples'])
            if len(totals)!=1: raise ValueError('Inconsistent sample count')
            sample_count=totals.pop()
            items=[('summary',session.started_at,doc['summary'])]
            for i,o in enumerate(result['occurrences']):
                if o['channel'] not in UNITS or o['unit']!=UNITS[o['channel']]: raise ValueError('Invalid channel/unit')
                for field,timefield in [('first_index','first_timestamp'),('last_index','last_timestamp'),('confirmed_index','confirmed_timestamp')]:
                    if type(o[field]) is not int or not 0<=o[field]<sample_count: raise ValueError('Invalid index')
                    if datetime.fromisoformat(o[timefield])!=session.started_at+timedelta(seconds=o[field]): raise ValueError('Invalid nominal time')
                if not o['first_index']<=o['confirmed_index']<=o['last_index']: raise ValueError()
                items.append((f'result/occurrences/{i}',datetime.fromisoformat(o['confirmed_timestamp']),o))
            for i,q in enumerate(result['quality_intervals']):
                if (q['channel'] not in UNITS or q['quality'] not in ('missing','invalid')
                    or type(q['first_index']) is not int or type(q['last_index']) is not int
                    or not 0<=q['first_index']<=q['last_index']<sample_count): raise ValueError()
                items.append((f'result/quality_intervals/{i}',session.started_at+timedelta(seconds=q['first_index']),q))
            expected={}
            for fragment,timestamp,item in items:
                event=MultimodalEvent(event_id=uuid5(run,f"{result['input_sha256']}:{sha}:{fragment}"),
                    session_id=session.session_id,subject_kind=session.subject.kind,patient_id=session.subject.patient_id,
                    source_kind=SourceKind.SYNTHETIC,source='synthetic-vitals-v1',timestamp=timestamp,
                    confidence=None,evidence_ref=f'{reference}#sha256={sha}&item=/{fragment}',processor=result['processor'],is_mock=False)
                expected[event.event_id]=(event,item)
            if set(expected)!={e.event_id for e in actual}: raise ValueError('Incomplete vital group')
            for event in actual:
                original,item=expected[event.event_id]
                if replace(event,review_status=ReviewStatus.PENDING_REVIEW)!=original: raise ValueError('Vital metadata mismatch')
                metadata=asdict(event);metadata.update(event_id=str(event.event_id),session_id=str(event.session_id),timestamp=event.timestamp.isoformat())
                rows.append(dict(event=metadata,evidence_item=item,modality='vitals'))
            documents.append(dict(reference=reference,sha256=sha,evidence=doc,raw_series=self._raw_series(doc,session)))
        return rows,documents

    def detail(self,database,session_id):
        with self._connection(database) as connection:
            session=SQLiteSessionRepository(connection).get_by_id(session_id)
            if session is None: raise HistoryError('session_not_found')
            try:
                all_events=SQLiteEventRepository(connection).list_for_session(session_id)
                store=_SnapshotStore(self.root)
                audio=query_audio_session(session_id,connection=connection,store=store)
                audio_documents=[dict(reference=ref,sha256=sha,evidence=strict_json(raw))
                    for ref,raw in store.contents.items() for sha in [hashlib.sha256(raw).hexdigest()]]
                rows=audio['events']
                for row in rows:row['modality']='audio'
                vital_rows,documents=self._vitals(session,[e for e in all_events if e.source=='synthetic-vitals-v1'])
                rows+=vital_rows
                prescription_rows,prescriptions=read_prescriptions(self.root,session,
                    [e for e in all_events if e.source=='synthetic-prescriptions-v1'])
                rows+=prescription_rows
                acoustic_rows,acoustics=read_acoustics(self.root,session,[e for e in all_events if e.source=='simulated-acoustic-pauses-v1'])
                rows+=acoustic_rows
                histories={r['event']['event_id']:event_review_history(UUID(r['event']['event_id']),connection=connection) for r in rows}
                detail=dict(session=audio['session'],registered_at=registration_times(connection).get(str(session_id)),events=rows,documents=audio_documents,
                    vitals=documents,prescriptions=prescriptions,review_histories=histories,integrity='verified' if rows else 'not_checked',
                    unsupported_sources=sorted({e.source for e in all_events if e.source not in ('simulated-audio-v1','synthetic-vitals-v1','synthetic-prescriptions-v1','simulated-acoustic-pauses-v1')}),
                    access_mode='read_only',clinical_validation=False)
                if acoustics:detail['acoustics']=acoustics
                return SessionDetail(encode_json(detail))
            except HistoryError:raise
            except (ValueError,KeyError,TypeError,AttributeError,OSError,OverflowError) as exc:
                raise HistoryError('evidence_invalid') from exc
