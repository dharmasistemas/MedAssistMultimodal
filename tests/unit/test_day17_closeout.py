from contextlib import closing
import json
import sqlite3
from unittest.mock import patch
from uuid import UUID

import pytest

from scripts.verify_day17_flow import collect_export
from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.infrastructure.sqlite_audio_registration import register_audio_sqlite
from medassistmultimodal.infrastructure.desktop_vitals import MultimodalHistoryReader
from tests.unit.test_structured_workspace import structured, request
from tests.unit.test_register_audio import make


@pytest.fixture
def integrated(tmp_path,structured):
    service,db,source=structured
    prepared,store,transcriber=make(tmp_path)
    with closing(sqlite3.connect(tmp_path/db)) as c:
        c.execute('PRAGMA foreign_keys=ON');register_audio_sqlite(prepared,connection=c,store=store)
    v=service.register_scenario(db,'PAT-001','vitals','V02')
    p=service.register_scenario(db,'PAT-001','prescriptions','P06')
    return service,db,prepared,v,p,transcriber


def test_export_three_modalities_after_reopen_no_inference_or_write(tmp_path,integrated):
    service,db,a,v,p,transcriber=integrated;before=(tmp_path/db).read_bytes()
    doc=collect_export(tmp_path,db)
    assert doc['summary']['sessions']==3
    assert set(doc['summary']['events_by_modality'])=={'audio','vitals','prescriptions'}
    assert doc['summary']['events']==len(a.events)+4
    assert doc['clinical_report'] is False and doc['causal_correlation_validated'] is False
    assert collect_export(tmp_path,db)==json.loads(json.dumps(doc))
    assert (tmp_path/db).read_bytes()==before
    transcriber.transcribe_with_details.assert_called_once()  # Fixture preparation only.


def test_export_preserves_current_review_and_immutable_original(tmp_path,integrated):
    service,db,a,v,p,_=integrated
    detail=service.reader.detail(db,UUID(v.session_id)).document;event=detail['events'][-1]['event']
    evidence=tmp_path/event['evidence_ref'].split('#')[0];before=evidence.read_bytes()
    req=request(event);service.review(db,UUID(v.session_id),req,event['evidence_ref'])
    service.review(db,UUID(v.session_id),req,event['evidence_ref'])
    export=collect_export(tmp_path,db)
    assert export['summary']['review_audits']==1 and export['summary']['review_status']['reviewed']==1
    assert evidence.read_bytes()==before
    assert collect_export(tmp_path,db)==export


@pytest.mark.parametrize('failure',['missing','tampered'])
def test_export_rejects_unverified_evidence(tmp_path,integrated,failure):
    service,db,a,v,p,_=integrated
    doc=service.reader.detail(db,UUID(p.session_id)).document
    evidence=tmp_path/doc['prescriptions'][0]['reference']
    if failure=='missing':evidence.rename(tmp_path/'saved.json')
    else:evidence.write_bytes(b'changed')
    with pytest.raises(HistoryError):collect_export(tmp_path,db)


def test_export_rejects_unknown_modality_instead_of_silent_omission(tmp_path,integrated):
    _,db,a,_,_,_=integrated
    with closing(sqlite3.connect(tmp_path/db)) as c:
        c.execute("UPDATE multimodal_events SET source='unknown-provider' WHERE event_id=?",(str(a.events[0].event_id),));c.commit()
    with pytest.raises(HistoryError):collect_export(tmp_path,db)


def test_export_detects_concurrent_database_change(tmp_path,integrated):
    _,db,_,_,_,_=integrated;original=MultimodalHistoryReader.detail;changed=[]
    def detail(reader,database,session):
        result=original(reader,database,session)
        if not changed:
            with closing(sqlite3.connect(tmp_path/db)) as c:
                c.execute("UPDATE multimodal_events SET review_status='reviewed' WHERE event_id=?",(result.document['events'][0]['event']['event_id'],));c.commit()
            changed.append(True)
        return result
    with patch.object(MultimodalHistoryReader,'detail',detail):
        with pytest.raises(HistoryError,match='export_conflict'):collect_export(tmp_path,db)


def test_empty_patient_export_does_not_invent_modalities(tmp_path,structured):
    _,db,_=structured;doc=collect_export(tmp_path,db)
    assert doc['sessions']==[] and doc['summary']['events']==0 and doc['summary']['events_by_modality']=={}
