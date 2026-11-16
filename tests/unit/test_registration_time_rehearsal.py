from datetime import datetime, timezone
from uuid import UUID
import sqlite3
import pytest
from tests.unit.test_structured_workspace import structured
from medassistmultimodal.infrastructure.rehearsal import create_rehearsal
from medassistmultimodal.desktop_anomaly_layout import anomaly_result_text

@pytest.mark.parametrize('modality,case',[('vitals','V02'),('prescriptions','P06'),('prescriptions','E02')])
def test_real_registration_separate_from_nominal_and_retry(tmp_path,structured,modality,case):
    service,db,_=structured
    start=datetime.now(timezone.utc)
    outcome=service.register_scenario(db,'PAT-001',modality,case)
    detail=service.reader.detail(db,UUID(outcome.session_id)).document
    stamp=datetime.fromisoformat(detail['registered_at'])
    assert start.timestamp()-.01 <= stamp.timestamp() <= datetime.now(timezone.utc).timestamp()
    assert stamp != datetime.fromisoformat(detail['session']['started_at'])
    service.retry_structured(db,outcome.run_id)
    assert service.reader.detail(db,UUID(outcome.session_id)).document['registered_at']==detail['registered_at']
    row=next(r for r in service.reader.sessions(db,'PAT-001') if r.session_id==outcome.session_id)
    assert row.display_at==detail['registered_at']
    text=anomaly_result_text(type('Detail',(),{'document':detail})())
    assert 'Registro no aplicativo:' in text and 'Horário nominal do cenário:' in text

def test_selected_database_preserves_audit_and_source(tmp_path,structured):
    service,db,_=structured
    one=service.register_scenario(db,'PAT-001','vitals','V02')
    two=service.register_scenario(db,'PAT-001','vitals','V01')
    before=(tmp_path/db).read_bytes()
    manifest=create_rehearsal(tmp_path,db,[one.session_id])
    assert (tmp_path/db).read_bytes()==before
    assert [r.session_id for r in service.reader.sessions(manifest['database'],'PAT-001')]==[one.session_id]
    assert service.reader.detail(manifest['database'],UUID(one.session_id)).document==service.reader.detail(db,UUID(one.session_id)).document
    assert manifest['evidence_dependencies'] and manifest['audit_records']==1
    with pytest.raises(ValueError):create_rehearsal(tmp_path,db,[str(UUID(int=0))])
    with pytest.raises(ValueError):create_rehearsal(tmp_path,db,[])

def test_missing_audit_does_not_invent_time(tmp_path,structured):
    service,db,_=structured
    run=service.register_scenario(db,'PAT-001','vitals','V02')
    with sqlite3.connect(tmp_path/db) as c:c.execute('DELETE FROM audit_records')
    d=service.reader.detail(db,UUID(run.session_id)).document
    assert d['registered_at'] is None
    assert 'não disponível na auditoria' in anomaly_result_text(type('D',(),{'document':d})())
