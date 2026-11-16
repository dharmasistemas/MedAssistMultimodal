"""Whisper local -> rules -> evidence -> SQLite, plus explicit technical fixtures."""
import os
os.environ['MKL_THREADING_LAYER']='SEQUENTIAL'
os.environ['OMP_NUM_THREADS']='4'
os.environ['HF_HUB_OFFLINE']='1'

from contextlib import closing
from datetime import date,datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import UUID,uuid5

from medassistmultimodal.application.audio import Transcript,TranscriptSegment
from medassistmultimodal.application.llm import LLMProviderTimeoutError
from medassistmultimodal.application.patient_context import Patient,PatientContext
from medassistmultimodal.application.process_audio import ProcessAudio,AudioProcessingRequest,ProviderIdentity
from medassistmultimodal.application.register_audio import prepare_audio_registration
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.audio_features import AudioFeatures
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.audio_evidence_store import AudioEvidenceStore
from medassistmultimodal.infrastructure.sqlite_audio_registration import register_audio_sqlite,query_audio_session
from medassistmultimodal.infrastructure.sqlite_event_review import review_event_sqlite,event_review_history
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from medassistmultimodal.providers.whisper_local import LocalWhisperTranscriber,WhisperRun,checked_path

ROOT=Path(__file__).resolve().parents[1]
NAMESPACE=UUID('da15da15-0000-4000-8000-000000000005')


class CountedWhisper:
    def __init__(self,provider):self.provider=provider;self.calls=0
    def transcribe_with_details(self,*args,**kwargs):
        self.calls+=1;return self.provider.transcribe_with_details(*args,**kwargs)


class SimulatedTextTimeout:
    def __init__(self):self.calls=0
    def generate(self,**kwargs):
        self.calls+=1;raise LLMProviderTimeoutError('explicit offline timeout fixture')


class TechnicalReviewFixture:
    def transcribe_with_details(self,audio_ref,*,language='pt-BR'):
        sha=hashlib.sha256(checked_path(audio_ref,ROOT).read_bytes()).hexdigest()
        transcript=Transcript('Senti tontura.','pt-BR','mock',f'{audio_ref}#sha256={sha}',
                              (TranscriptSegment(0,1,'Senti tontura.'),))
        features=AudioFeatures('energy-descriptors-v1',16000,16000,1,.1,.2,.02,.01,.2,())
        return WhisperRun(transcript,features,sha,0)


def main():
    manifest_path=ROOT/'data/manifests/day13_whisper_assets.json'
    manifest=json.loads(manifest_path.read_bytes())
    for f in manifest['model']['files']:
        path=checked_path(str(ROOT/manifest['model']['local_path']/f['name']),ROOT)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=f['sha256']:raise ValueError('Model changed')
    corpus_path=ROOT/'data/interim/audio/simulated_v1/collection_status.json'
    corpus=json.loads(corpus_path.read_bytes())
    selected={case:next(c for c in corpus['clips'] if c['case_id']==case) for case in ('A08','A03')}
    for c in selected.values():
        if not c['human_verified'] or not c['consent_ref']:raise ValueError('Permission/reference missing')
        if hashlib.sha256(checked_path(c['actual_audio_path'],ROOT).read_bytes()).hexdigest()!=c['audio_sha256']:
            raise ValueError('Audio changed')
    out=checked_path('data/interim/audio/day15_real_flow_v1',ROOT);out.mkdir(exist_ok=False)
    code=['src/medassistmultimodal/application/process_audio.py',
          'src/medassistmultimodal/application/register_audio.py',
          'src/medassistmultimodal/infrastructure/sqlite_audio_registration.py',
          'src/medassistmultimodal/infrastructure/sqlite_event_review.py']
    config=dict(date='2026-11-07',started_at=datetime.now(timezone.utc).isoformat(),
        real_asr_cases=['A08','A03'],technical_asr_fixture=True,cloud_calls=0,
        llm_timeout_is_simulated=True,model_revision=manifest['model']['revision'],
        device='cpu',compute_type='int8',cpu_threads=4,
        nominal_session_timestamp='2026-11-07T12:00:00+00:00',
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in code},
        audio_sha256={k:c['audio_sha256'] for k,c in selected.items()},
        clinical_review_performed=False,references_passed_to_whisper=False)
    (out/'config.json').write_bytes(encode_json(config))
    database=out/'audio.sqlite3';database.touch(exist_ok=False)
    whisper=CountedWhisper(LocalWhisperTranscriber(root=ROOT,model_directory=manifest['model']['local_path']))
    timeout=SimulatedTextTimeout();store=AudioEvidenceStore(ROOT);prepared=[];rows=[]
    with closing(sqlite3.connect(database)) as db:
        db.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(db)
        patients=SQLitePatientRepository(db)
        patients.save(PatientContext(Patient('PAT-001','Pessoa fictícia PAT-001',date(1970,1,1),
                                            'not_specified',True),(),(),()));db.commit()
        for name,case,kind in [('A08_real','A08','real'),('A03_real_timeout','A03','timeout'),
                               ('review_fixture','A08','fixture')]:
            c=selected[case]
            identity=(ProviderIdentity('fixture','offline','1','mock',True) if kind=='fixture' else
                      ProviderIdentity('faster-whisper','small-ct2',manifest['runtime']['version'],'whisper',False))
            processor=ProcessAudio(root=ROOT,patient_exists=lambda pid:patients.get_by_id(pid) is not None,
                transcriber=TechnicalReviewFixture() if kind=='fixture' else whisper,asr_identity=identity,
                text_provider=timeout if kind=='timeout' else None,
                text_identity=ProviderIdentity('simulated-timeout','offline','1','mock',True) if kind=='timeout' else None)
            request=AudioProcessingRequest(run_id=uuid5(NAMESPACE,name),session_id=uuid5(NAMESPACE,name+'/session'),
                patient_id='PAT-001',session_timestamp=datetime(2026,11,7,12,tzinfo=timezone.utc),
                processing_timestamp=datetime.now(timezone.utc),audio_ref=c['actual_audio_path'],
                expected_sha256=c['audio_sha256'],origin_ref=corpus_path.relative_to(ROOT).as_posix(),
                permission_ref=c['consent_ref'],origin_kind='human_recording',permission_declared=True,
                llm_enabled=kind=='timeout')
            result=processor.execute(request)
            assert result.status==('degraded' if kind=='timeout' else 'completed'),result.document
            p=prepare_audio_registration(result,evidence_ref=(out/f'{name}.json').relative_to(ROOT).as_posix())
            audit=register_audio_sqlite(p,connection=db,store=store)
            assert register_audio_sqlite(p,connection=db,store=store)==audit
            prepared.append(p)
            rows.append(dict(case=name,status=result.status,events=len(p.events),asr_mock=identity.is_mock,
                             asr_seconds=result.document['asr']['seconds'],llm_status=result.document['llm']['status']))
            print(name,result.status,len(p.events),'events',flush=True)
        fixture=prepared[-1];before=store.read(fixture.evidence_ref)
        review=EventReviewRequest(review_id=uuid5(NAMESPACE,'technical-review'),event_id=fixture.events[1].event_id,
            reviewer_ref='demo-reviewer',reviewed_at=datetime.now(timezone.utc),
            reason='Technical simulation only; not a clinical review.',target_status=ReviewStatus.REVIEWED,
            scope='technical_simulation')
        review_id=review_event_sqlite(review,connection=db)
        assert review_event_sqlite(review,connection=db)==review_id
        assert store.read(fixture.evidence_ref)==before and whisper.calls==2 and timeout.calls==1
    with closing(sqlite3.connect(database)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        views=[query_audio_session(p.session.session_id,connection=db,store=store) for p in prepared]
        for view in views:
            for row in view['events']:
                row['review_history']=event_review_history(UUID(row['event']['event_id']),connection=db)
        assert all(row['event']['review_status']=='pending_review' for view in views[:2] for row in view['events'])
        totals={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in
                ('multimodal_sessions','multimodal_events','audit_records')}
    assert tuple(totals.values())==(3,8,4),totals
    (out/'export.json').write_bytes(encode_json(views))
    summary=dict(date='2026-11-07',real_whisper_calls=2,cloud_calls=0,simulated_llm_timeout_calls=1,
        technical_review_simulated=True,clinical_review_performed=False,evidence_unchanged_by_review=True,
        persistence_retries_without_duplication=True,sqlite_reopened=True,cases=rows,totals=totals)
    (out/'summary.json').write_bytes(encode_json(summary));print(encode_json(summary).decode(),flush=True)


if __name__=='__main__':main()
