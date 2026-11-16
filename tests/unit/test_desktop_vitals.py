import hashlib
import json
import sqlite3
import time
import tkinter as tk
from uuid import uuid4
from unittest.mock import patch

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.application.register_vitals import prepare_vitals,register_prepared_vitals
from medassistmultimodal.demo.synthetic_vitals import write_bundle
from medassistmultimodal.infrastructure.desktop_vitals import MultimodalHistoryReader
from medassistmultimodal.infrastructure.desktop_workspace import DesktopWorkspace
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from medassistmultimodal.domain.events import ReviewStatus
from tests.unit.test_privacy import create_patient_context


@pytest.fixture
def vital_db(tmp_path):
    bundle=tmp_path/'data/synthetic/vitals_v1';write_bundle(bundle)
    # Border fixture: declared valid pressure pair is rejected by domain validation.
    input_path=bundle/'V13.json';payload=json.loads(input_path.read_bytes())
    for channel in ('systolic','diastolic'):
        payload['samples'][6][channel]['quality']='valid'
        payload['samples'][6][channel].pop('reason',None)
    input_path.write_text(json.dumps(payload),encoding='utf-8')
    manifest_path=bundle/'manifest.json';manifest=json.loads(manifest_path.read_bytes())
    manifest['files']['V13.json']['sha256']=hashlib.sha256(input_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
    database=tmp_path/'history.sqlite3';prepared={}
    with sqlite3.connect(database) as connection:
        connection.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(connection)
        SQLitePatientRepository(connection).save(create_patient_context());connection.commit()
        for scenario in ('V01','V02','V12','V13'):
            ref=f'data/interim/vitals/{scenario}.json'
            p=prepare_vitals((bundle/(scenario+'.json')).read_bytes(),run_id=uuid4(),evidence_ref=ref)
            evidence=tmp_path/ref;evidence.parent.mkdir(parents=True,exist_ok=True);evidence.write_bytes(p.evidence)
            register_prepared_vitals(p,RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(connection)),evidence.read_bytes)
            prepared[scenario]=p
    return database,prepared


def test_read_v02_occurrence_raw_units_and_readonly_hashes(tmp_path,vital_db):
    database,prepared=vital_db;reader=MultimodalHistoryReader(tmp_path)
    before=hashlib.sha256(database.read_bytes()).hexdigest()
    rows=reader.sessions(database.name,'PAT-001');assert all(r.modalities==('Vitais',) for r in rows)
    data=reader.detail(database.name,prepared['V02'].session.session_id).document
    assert data['integrity']=='verified' and len(data['events'])==2
    record=data['vitals'][0];raw=record['raw_series']
    assert raw['status']=='verified' and len(raw['samples'])==48
    occurrence=record['evidence']['result']['occurrences'][0]
    assert occurrence['unit']=='bpm' and occurrence['rule_id']=='heart_rate_high'
    assert hashlib.sha256(database.read_bytes()).hexdigest()==before
    with reader._connection(database.name) as connection:
        with pytest.raises(sqlite3.OperationalError):connection.execute('DELETE FROM multimodal_events')


def test_v12_no_coverage_is_not_normality(tmp_path,vital_db):
    database,p=vital_db;reader=MultimodalHistoryReader(tmp_path)
    d=reader.detail(database.name,p['V12'].session.session_id)
    from medassistmultimodal.desktop_multimodal import vital_text
    assert all(c['fraction']==0 for c in d.document['vitals'][0]['evidence']['result']['coverage'])
    text=vital_text(d)
    assert 'Sem amostras válidas' in text and 'não indica normalidade' in text
    assert all(v['value'] is None for v in d.document['vitals'][0]['raw_series']['samples'])


def test_no_occurrences_is_valid_result(tmp_path,vital_db):
    database,p=vital_db;d=MultimodalHistoryReader(tmp_path).detail(database.name,p['V01'].session.session_id)
    assert len(d.document['events'])==1
    from medassistmultimodal.desktop_multimodal import vital_text
    assert 'Nenhuma ocorrência detectada pelo perfil aplicado' in vital_text(d)


@pytest.mark.parametrize('failure,status',[('missing','unavailable'),('hash','divergent'),('manifest','divergent')])
def test_raw_series_unavailable_or_changed_preserves_verified_result(tmp_path,vital_db,failure,status):
    database,p=vital_db;input_path=tmp_path/'data/synthetic/vitals_v1/V02.json'
    if failure=='missing':input_path.rename(input_path.with_suffix('.saved'))
    elif failure=='hash':input_path.write_bytes(b'changed fixture')
    else:(input_path.parent/'manifest.json').write_text('{}')
    d=MultimodalHistoryReader(tmp_path).detail(database.name,p['V02'].session.session_id).document
    assert d['integrity']=='verified' and d['vitals'][0]['raw_series']['status']==status
    assert d['vitals'][0]['raw_series']['samples']==[]
    assert len(d['events'])==2


@pytest.mark.parametrize('failure',['missing','hash','schema','metadata','partial_group','patient'])
def test_invalid_evidence_or_event_group_rejected(tmp_path,vital_db,failure):
    database,p=vital_db;p=p['V02'];path=tmp_path/'data/interim/vitals/V02.json'
    if failure=='missing':path.rename(path.with_suffix('.saved'))
    elif failure=='hash':path.write_bytes(b'changed')
    elif failure=='schema':
        doc=json.loads(path.read_bytes());doc['schema_version']='unknown';path.write_text(json.dumps(doc))
    else:
        with sqlite3.connect(database) as connection:
            if failure=='metadata':connection.execute('UPDATE multimodal_events SET is_mock=1 WHERE event_id=?',(str(p.events[-1].event_id),))
            elif failure=='partial_group':connection.execute('DELETE FROM multimodal_events WHERE event_id=?',(str(p.events[-1].event_id),))
            else:connection.execute("UPDATE multimodal_sessions SET started_at='2026-11-03T14:00:00.000000+00:00' WHERE session_id=?",(str(p.session.session_id),))
    with pytest.raises(HistoryError):MultimodalHistoryReader(tmp_path).detail(database.name,p.session.session_id)


def test_normalized_pressure_quality_is_visible(tmp_path,vital_db):
    database,p=vital_db
    d=MultimodalHistoryReader(tmp_path).detail(database.name,p['V13'].session.session_id).document
    samples=d['vitals'][0]['raw_series']['samples']
    assert any(s['quality']=='invalid' and s['reported_quality']=='valid' and s['reason'] for s in samples)


def test_audio_stays_supported(tmp_path):
    from tests.unit.test_desktop_history import persisted
    # Exercise the existing fixture factory without requesting another historical DB.
    fixture_generator=persisted.__wrapped__(tmp_path)
    database,p,store,t=fixture_generator
    reader=MultimodalHistoryReader(tmp_path)
    d=reader.detail(database.name,p.session.session_id)
    assert len(d.document['documents'])==1 and not d.document['vitals']
    from medassistmultimodal.desktop_multimodal import vital_text
    assert 'não contém registros de sinais vitais' in vital_text(d)


def check_tk_vitals_selection_samples_and_review_block(tmp_path,vital_db,tk_runtime):
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_multimodal import MultimodalApp
    database,p=vital_db;root=tk.Toplevel(tk_runtime);root.withdraw()
    app=MultimodalApp(root,reader=MultimodalHistoryReader(tmp_path),workspace=DesktopWorkspace(tmp_path),project_root=tmp_path)
    try:
        app.database.set(database.name);app.load_history();pump(root,app)
        app.sessions.selection_set(str(p['V02'].session.session_id));app.select_session();pump(root,app)
        assert 'Cenário: V02' in app.vitals_summary.get('1.0','end')
        assert len(app.samples.get_children())==48
        event=app.events.get_children()[-1];app.events.selection_set(event);app.select_event()
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno') as confirm:app.submit_review(ReviewStatus.REVIEWED)
        confirm.assert_not_called();assert 'somente consulta' in app.status.get()
        app.database.set('missing.sqlite3');app.load_history();pump(root,app)
        assert app.state.status=='error' and not app.samples.get_children()
        assert 'Selecione uma sessão' in app.vitals_summary.get('1.0','end')
    finally:
        root.after_cancel(app.poll_id);root.destroy()
