import hashlib
import json
import sqlite3
import tkinter as tk
from unittest.mock import patch
from uuid import uuid4

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.application.register_prescriptions import prepare_prescriptions,register_prepared_prescriptions
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.demo.prescription_fixtures import build_prescription_cases
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.desktop_vitals import MultimodalHistoryReader
from medassistmultimodal.infrastructure.desktop_workspace import DesktopWorkspace
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_privacy import create_patient_context


@pytest.fixture
def prescription_db(tmp_path):
    database=tmp_path/'prescriptions.sqlite3';cases,_=build_prescription_cases();prepared={}
    cases['P04']['after']['items'][0]['dose_value']='0.12345678901234567890123456789'
    with sqlite3.connect(database) as connection:
        connection.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(connection)
        SQLitePatientRepository(connection).save(create_patient_context());connection.commit()
        for key in ('P01','P02','P03','P04','P06','P11','P14'):
            ref=f'data/interim/prescriptions/{key}.json'
            p=prepare_prescriptions(encode_json(cases[key]),run_id=uuid4(),evidence_ref=ref)
            path=tmp_path/ref;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(p.evidence)
            register_prepared_prescriptions(p,RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(connection)),path.read_bytes)
            prepared[key]=p
    return database,prepared


def test_prescription_readonly_snapshots_and_exact_decimal(tmp_path,prescription_db):
    from medassistmultimodal.desktop_multimodal import prescription_text
    database,p=prescription_db;before=database.read_bytes();reader=MultimodalHistoryReader(tmp_path)
    assert all(r.modalities==('Prescrições',) for r in reader.sessions(database.name,'PAT-001'))
    detail=reader.detail(database.name,p['P04'].session.session_id)
    result=detail.document['prescriptions'][0]['evidence']['result']
    dose=result['after']['items'][0]['dose_value']
    assert dose=='0.12345678901234567890123456789' and dose in prescription_text(detail)
    assert result['changes'][0]['field_changes'][0]['after']==dose
    assert not detail.document['unsupported_sources'] and database.read_bytes()==before


@pytest.mark.parametrize('key,expected',[('P02','Incluído'),('P03','Removido'),('P06','Modificado'),('P01','sem alterações'),('P11','Itens antes: 0 | Itens depois: 0')])
def test_prescription_change_types_and_empty_versions(tmp_path,prescription_db,key,expected):
    from medassistmultimodal.desktop_multimodal import prescription_text
    database,p=prescription_db;d=MultimodalHistoryReader(tmp_path).detail(database.name,p[key].session.session_id)
    assert expected in prescription_text(d)
    assert d.document['integrity']=='verified'


def test_unit_representation_warning_not_clinical_inference(tmp_path,prescription_db):
    from medassistmultimodal.desktop_multimodal import prescription_text
    database,p=prescription_db;d=MultimodalHistoryReader(tmp_path).detail(database.name,p['P14'].session.session_id)
    text=prescription_text(d)
    assert '1000 mg' in text and '1 g' in text
    assert 'sem inferir equivalência clínica ou aumento de dose' in text


@pytest.mark.parametrize('failure',['missing','hash','partial_group','metadata','snapshot','pointer'])
def test_bad_prescription_evidence_or_events_rejected(tmp_path,prescription_db,failure):
    database,p=prescription_db;p=p['P06'];path=tmp_path/'data/interim/prescriptions/P06.json'
    if failure=='missing':path.rename(path.with_suffix('.saved'))
    elif failure=='hash':path.write_bytes(b'changed fixture')
    elif failure=='snapshot':
        doc=json.loads(path.read_bytes());doc['result']['after']['items'][0]['dose_value']='999';path.write_bytes(encode_json(doc))
    else:
        with sqlite3.connect(database) as connection:
            if failure=='partial_group':connection.execute('DELETE FROM multimodal_events WHERE event_id=?',(str(p.events[-1].event_id),))
            elif failure=='metadata':connection.execute('UPDATE multimodal_events SET confidence=0.8 WHERE event_id=?',(str(p.events[-1].event_id),))
            else:connection.execute("UPDATE multimodal_events SET evidence_ref=replace(evidence_ref,'/result/changes/0','/result/changes/999') WHERE event_id=?",(str(p.events[-1].event_id),))
    with pytest.raises(HistoryError):MultimodalHistoryReader(tmp_path).detail(database.name,p.session.session_id)


def test_internal_snapshot_consistency_and_diff_validation(prescription_db):
    from medassistmultimodal.infrastructure.desktop_prescriptions import _checked_result
    _,p=prescription_db;p=p['P06']
    doc=json.loads(p.evidence)
    assert _checked_result(doc,p.session)['status']=='changed'
    doc['result']['changes'][0]['field_changes'][0]['after']='incorrect'
    with pytest.raises(ValueError):_checked_result(doc,p.session)


def test_missing_original_input_does_not_hide_complete_snapshots(tmp_path,prescription_db):
    database,p=prescription_db
    # This fixture writes no original input pair; snapshots are part of the evidence.
    d=MultimodalHistoryReader(tmp_path).detail(database.name,p['P06'].session.session_id).document
    assert d['prescriptions'][0]['evidence']['result']['before']['items']
    assert len(d['events'])==2 and d['access_mode']=='read_only'


def check_tk_prescription_consultation(tmp_path,prescription_db,tk_runtime):
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_multimodal import MultimodalApp
    database,p=prescription_db;root=tk.Toplevel(tk_runtime);root.withdraw()
    app=MultimodalApp(root,reader=MultimodalHistoryReader(tmp_path),workspace=DesktopWorkspace(tmp_path),project_root=tmp_path)
    try:
        app.database.set(database.name);app.load_history();pump(root,app)
        app.sessions.selection_set(str(p['P06'].session.session_id));app.select_session();pump(root,app)
        assert 'Modificado' in app.prescription_summary.get('1.0','end')
        assert len(app.prescription_items.get_children())==2
        event=app.events.get_children()[-1];app.events.selection_set(event);app.select_event()
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno') as confirm:app.submit_review(ReviewStatus.REVIEWED)
        confirm.assert_not_called();assert 'Prescrições: somente consulta' in app.status.get()
        app.database.set('missing.sqlite3');app.load_history();pump(root,app)
        assert not app.prescription_items.get_children() and app.state.detail is None
        assert 'Selecione uma sessão' in app.prescription_summary.get('1.0','end')
    finally:
        root.after_cancel(app.poll_id);root.destroy()
