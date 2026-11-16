from copy import deepcopy
from dataclasses import asdict
import json
from uuid import UUID,uuid4

import pytest

from medassistmultimodal.demo.prescription_expectations import expectation_cases
from medassistmultimodal.domain.prescriptions import compare_prescriptions
from medassistmultimodal.domain.prescription_expectation import assess_expectation
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.application.register_prescription_expectation import prepare_prescription_expectation,checked_expectation
from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.infrastructure.desktop_summary import SummaryService
from tests.unit.test_structured_workspace import structured,counts,request


def assess(bundle):
    r=compare_prescriptions(encode_json(bundle['pair']))
    return assess_expectation(r.before,r.after,bundle['plan'])


@pytest.mark.parametrize('case',[f'E{i:02}' for i in range(1,9)])
def test_declared_references_and_context_not_modified(case):
    cases,refs=expectation_cases();b=cases[case];original=deepcopy(b)
    actual=assess(b)
    assert actual.status==refs[case] and b==original
    assert bool(actual.differences)==(refs[case]=='divergent')
    assert actual.clinical_validation is False and actual.confidence is None


@pytest.mark.parametrize('field,value,reason',[
    ('patient_id','PAT-002','identity_mismatch'),('prescription_set_id','OTHER','identity_mismatch'),
    ('before_canonical_sha256','0'*64,'base_mismatch'),('target_version',99,'version_mismatch'),
    ('declared_at','2026-11-05T09:00:00+00:00','plan_time_incompatible'),
    ('declared_at','2026-11-01T09:00:00+00:00','plan_time_incompatible')])
def test_inapplicable_plan_is_indeterminate(field,value,reason):
    b=expectation_cases()[0]['E01'];b['plan'][field]=value
    r=assess(b);assert r.status=='indeterminate' and r.reason==reason


@pytest.mark.parametrize('mutation',['extra','missing','bad_hash','bool_version','naive_time','duplicate','unit','dose'])
def test_malformed_plan_rejected(mutation):
    b=expectation_cases()[0]['E01'];p=b['plan']
    if mutation=='extra':p['expected_status']='compatible'
    elif mutation=='missing':del p['expected_items']
    elif mutation=='bad_hash':p['before_canonical_sha256']='bad'
    elif mutation=='bool_version':p['target_version']=True
    elif mutation=='naive_time':p['declared_at']='2026-11-03T12:00:00'
    elif mutation=='duplicate':p['expected_items']*=2
    elif mutation=='unit':p['expected_items'][0]['dose_unit']='unknown'
    else:p['expected_items'][0]['dose_value']='NaN'
    with pytest.raises(ValueError):assess(b)


def test_decimal_exact_and_numeric_dose_not_lexicographic():
    b=expectation_cases()[0]['E01'];b['pair']['after']['items'][0]['dose_value']='15.000'
    assert assess(b).status=='compatible'
    b['pair']['after']['items'][0]['dose_value']='15.00000000000000000000001'
    assert assess(b).status=='divergent'


def test_plan_is_not_derived_from_observed_version():
    b=expectation_cases()[0]['E01'];plan=deepcopy(b['plan'])
    assert assess(b).status=='compatible'
    b['pair']['after']['items'][0]['frequency_per_day']=3
    result=assess(b)
    assert b['plan']==plan and result.status=='divergent'
    assert result.differences[0].field=='frequency_per_day'


@pytest.mark.parametrize('case',[f'E{i:02}' for i in range(1,9)])
def test_workspace_registration_reader_retry_summary_and_legacy(tmp_path,structured,case):
    s,db,source=structured;before=source.read_bytes()
    outcome=s.register_scenario(db,'PAT-001','prescriptions',case)
    assert outcome.persisted
    d=s.reader.detail(db,UUID(outcome.session_id)).document
    doc=d['prescriptions'][0]['evidence'];expected=expectation_cases()[1][case]
    assert doc['schema_version']=='prescription-evidence-v2' and doc['expectation']['status']==expected
    assert len(doc['expectation_candidates'])==int(expected=='divergent')
    assert sum('/expectation_candidates/' in row['event']['evidence_ref'] for row in d['events'])==int(expected=='divergent')
    assert all(row['event']['review_status']=='pending_review' for row in d['events'])
    initial=counts(tmp_path,db);assert s.retry_structured(db,outcome.run_id)==outcome
    assert counts(tmp_path,db)==initial and source.read_bytes()==before
    report=SummaryService(tmp_path);snapshot=report.build(db,'PAT-001',[outcome.session_id])
    assert 'plano' in snapshot.document['text'].lower() or expected=='indeterminate'
    report.export(snapshot)
    legacy=s.register_scenario(db,'PAT-001','prescriptions','P06')
    old=s.reader.detail(db,UUID(legacy.session_id)).document['prescriptions'][0]['evidence']
    assert old['schema_version']=='prescription-evidence-v1' and 'expectation' not in old


def test_recomputation_and_complete_candidate_group(tmp_path,structured):
    import sqlite3
    from contextlib import closing
    s,db,_=structured;r=s.register_scenario(db,'PAT-001','prescriptions','E02')
    d=s.reader.detail(db,UUID(r.session_id)).document;doc=d['prescriptions'][0]['evidence']
    changed=deepcopy(doc);changed['expectation']['status']='compatible'
    with pytest.raises(ValueError):checked_expectation(changed)
    event=next(x['event'] for x in d['events'] if '/expectation_candidates/' in x['event']['evidence_ref'])
    with closing(sqlite3.connect(tmp_path/db)) as c:
        c.execute('DELETE FROM multimodal_events WHERE event_id=?',(event['event_id'],));c.commit()
    with pytest.raises(HistoryError,match='evidence_invalid'):s.reader.detail(db,UUID(r.session_id))


def test_review_replay_preserves_evidence_and_rejects_reset(tmp_path,structured):
    s,db,_=structured;r=s.register_scenario(db,'PAT-001','prescriptions','E02')
    d=s.reader.detail(db,UUID(r.session_id)).document
    e=next(x['event'] for x in d['events'] if '/expectation_candidates/' in x['event']['evidence_ref'])
    path=tmp_path/e['evidence_ref'].split('#')[0];original=path.read_bytes()
    req=request(e);a=s.review(db,UUID(r.session_id),req,e['evidence_ref'])
    assert s.review(db,UUID(r.session_id),req,e['evidence_ref'])==a
    assert len(s.reader.detail(db,UUID(r.session_id)).document['review_histories'][e['event_id']])==1
    with pytest.raises(HistoryError,match='registration_conflict'):s.retry_structured(db,r.run_id)
    assert original==path.read_bytes()


def test_bad_evidence_prevents_review(tmp_path,structured):
    s,db,_=structured;r=s.register_scenario(db,'PAT-001','prescriptions','E02')
    d=s.reader.detail(db,UUID(r.session_id)).document;e=d['events'][-1]['event']
    (tmp_path/e['evidence_ref'].split('#')[0]).write_bytes(b'altered')
    with pytest.raises(HistoryError):s.review(db,UUID(r.session_id),request(e),e['evidence_ref'])


def check_tk_prescription_expectation(tmp_path,structured,tk_runtime):
    import tkinter as tk
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_multimodal import MultimodalApp
    s,db,_=structured;r=s.register_scenario(db,'PAT-001','prescriptions','E02')
    root=tk.Toplevel(tk_runtime);root.withdraw()
    app=MultimodalApp(root,reader=s.reader,workspace=s,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app)
        app.structured_modality.set('Prescrições');app.refresh_structured_cases()
        assert 'E02' in app.structured_choices.cget('values')
        app.sessions.selection_set(r.session_id);app.select_session();pump(root,app)
        text=app.prescription_summary.get('1.0','end')
        assert 'Divergência do plano sintético' in text and 'Esperado: 15' in text and 'Observado: 20' in text
        assert any('Divergência do plano' in str(app.events.item(i,'values')) for i in app.events.get_children())
    finally:
        root.after_cancel(app.poll_id);root.destroy()
