"""Offline file/SQLite verification with explicit ASR mock; no real model calls."""
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from uuid import UUID, uuid5

from medassistmultimodal.application.audio import Transcript, TranscriptSegment, AudioNoSpeechError
from medassistmultimodal.application.patient_context import Patient, PatientContext
from medassistmultimodal.application.process_audio import ProcessAudio, AudioProcessingRequest, ProviderIdentity
from medassistmultimodal.application.register_audio import prepare_audio_registration
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.domain.audio_features import AudioFeatures
from medassistmultimodal.infrastructure.audio_evidence_store import AudioEvidenceStore
from medassistmultimodal.infrastructure.sqlite_audio_registration import register_audio_sqlite, query_audio_session
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from medassistmultimodal.providers.whisper_local import WhisperRun, checked_path

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = UUID('da15da15-0000-4000-8000-000000000003')


class OfflineTranscriber:
    def __init__(self, text): self.text = text; self.calls = 0
    def transcribe_with_details(self, audio_ref, *, language='pt-BR'):
        self.calls += 1
        if self.text is None: raise AudioNoSpeechError('offline fixture')
        path = checked_path(audio_ref, ROOT); sha = hashlib.sha256(path.read_bytes()).hexdigest()
        transcript = Transcript(self.text, 'pt-BR', 'mock', f'{audio_ref}#sha256={sha}',
                                (TranscriptSegment(0,1,self.text),))
        features = AudioFeatures('energy-descriptors-v1',16000,16000,1,.1,.2,.02,.01,.2,())
        return WhisperRun(transcript, features, sha, 0)


def main():
    out = checked_path('data/interim/audio/day15_persistence_offline_v1', ROOT)
    out.mkdir(exist_ok=False)
    (out/'origin.json').write_bytes(encode_json({'origin':'offline_fixture_not_person_audio'}))
    (out/'permission.json').write_bytes(encode_json({'scope':'artificial_test_bytes_only'}))
    (out/'fixture.wav').write_bytes(b'offline mock fixture; not a playable recording')
    audio_ref = (out/'fixture.wav').relative_to(ROOT).as_posix()
    sha = hashlib.sha256((out/'fixture.wav').read_bytes()).hexdigest()
    database = out/'audio.sqlite3'; database.touch(exist_ok=False)
    instant = datetime(2026,11,7,12,tzinfo=timezone.utc)
    prepared = []; counts=[]
    with closing(sqlite3.connect(database)) as db:
        db.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(db)
        patients = SQLitePatientRepository(db)
        patients.save(PatientContext(Patient('PAT-001','Pessoa fictícia PAT-001',date(1970,1,1),
                                            'not_specified',True),(),(),()));db.commit()
        store = AudioEvidenceStore(ROOT)
        for name,text,llm in [('current','Senti tontura.',False),('negated','Não senti dor.',False),
                               ('llm_missing','Senti tontura.',True),('asr_failed',None,False)]:
            transcriber = OfflineTranscriber(text)
            request = AudioProcessingRequest(run_id=uuid5(NAMESPACE,name),session_id=uuid5(NAMESPACE,name+'/session'),
                patient_id='PAT-001',session_timestamp=instant,processing_timestamp=instant,
                audio_ref=audio_ref,expected_sha256=sha,
                origin_ref=(out/'origin.json').relative_to(ROOT).as_posix(),
                permission_ref=(out/'permission.json').relative_to(ROOT).as_posix(),
                origin_kind='human_recording',permission_declared=True,llm_enabled=llm)
            processor = ProcessAudio(root=ROOT,patient_exists=lambda pid:patients.get_by_id(pid) is not None,
                transcriber=transcriber,asr_identity=ProviderIdentity('offline_fixture','mock','1','mock',True))
            result = processor.execute(request)
            item = prepare_audio_registration(result,evidence_ref=(out/f'{name}.json').relative_to(ROOT).as_posix())
            first = register_audio_sqlite(item,connection=db,store=store)
            assert register_audio_sqlite(item,connection=db,store=store)==first and transcriber.calls==1
            prepared.append(item)
            counts.append(dict(case=name,status=result.status,events=len(item.events),audit_id=first))
    with closing(sqlite3.connect(database)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        views = [query_audio_session(p.session.session_id,connection=db,store=store) for p in prepared]
        totals = {table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in
                  ('multimodal_sessions','multimodal_events','audit_records')}
    assert tuple(totals.values())==(4,7,4)
    (out/'export.json').write_bytes(encode_json(views))
    (out/'summary.json').write_bytes(encode_json(dict(date='2026-11-07',asr_is_mock=True,
        real_model_calls=0,retentative_duplicated=False,cases=counts,totals=totals,
        sqlite_reopened=True,evidence_hashes_verified=True,clinical_validation=False)))
    print(encode_json(dict(output=out.relative_to(ROOT).as_posix(),cases=counts,totals=totals)).decode())


if __name__ == '__main__': main()
