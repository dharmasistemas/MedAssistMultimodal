import tkinter as tk
from types import SimpleNamespace
from unittest.mock import Mock,patch
from uuid import UUID

import pytest
from tests.unit.test_structured_workspace import structured,request
from tests.unit.test_desktop_summary import summary_data


@pytest.mark.parametrize('modality,item,fragment,expected',[
    ('audio',{'term':'dor','classification':'candidate_for_human_review'},'/rules/0','Candidato'),
    ('audio',{'term':'dor','classification':'context_only'},'/rules/0','Contexto'),
    ('vitals',{'quality':'missing'},'/quality_intervals/0','Qualidade'),
    ('vitals',{'rule_id':'fixture','channel':'spo2'},'/occurrences/0','Candidato'),
    ('prescriptions',{'kind':'modified'},'/changes/0','Alteração'),
    ('prescriptions',{},'/expectation_candidates/0','Candidato'),
    ('video',{},'/cycles/0','Técnico'),
    ('video',{},'/deviation_candidates/0','Candidato'),
    ('acoustics',{},'/candidates/0','Candidato'),
    ('acoustics',{},'/summary','Resumo'),
])
def test_review_categorization_does_not_turn_all_events_into_alerts(modality,item,fragment,expected):
    from medassistmultimodal.desktop_review_layout import event_kind
    row={'modality':modality,'evidence_item':item,'event':{'evidence_ref':'fixture#sha256=x&item='+fragment}}
    assert event_kind(row)[0]==expected


def test_report_preview_keeps_independent_sources_and_no_clinical_claims(summary_data):
    from medassistmultimodal.desktop_review_layout import report_preview_text
    service,db,ids,_,_,_=summary_data
    snapshot=service.build(db,'PAT-001',ids);before=snapshot.payload
    text=report_preview_text(snapshot)
    assert 'PACIENTE FICTÍCIO' in text and 'DATASET INDEPENDENTE' in text
    assert 'Não senti dor.' in text and 'não comprova normalidade' not in text  # Positive vital fixture.
    assert 'sem correlação' in text.lower() and 'prévia é resumida' in text
    assert snapshot.payload==before


def check_review_simplified_layout(tmp_path,summary_data,tk_runtime):
    from medassistmultimodal.desktop_simplified import SimplifiedApp
    from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
    from medassistmultimodal.domain.events import ReviewStatus
    from tests.unit.test_desktop_workflow import pump
    service,db,ids,_,source,_=summary_data;before=source.read_bytes()
    provider=Mock(side_effect=AssertionError('no provider during review'))
    w=TextWorkspace(tmp_path,text_provider_factory=provider,transcriber_factory=provider)
    root=tk.Toplevel(tk_runtime);app=SimplifiedApp(root,reader=w.reader,workspace=w,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app)
        app.load_report_catalog();pump(root,app)
        assert len(app.review_panel.catalog)==4
        assert app.review_tab.winfo_children().index(app.events.master) > app.review_tab.winfo_children().index(app.review_views)
        assert app.summary_page.winfo_children().index(app.report_sessions.master) > app.summary_page.winfo_children().index(app.review_panel.export_surface)
        for sid in ids:
            name=next(name for name,row in app.review_panel.catalog.items() if row['session_id']==sid)
            app.review_panel.choice.set(name);app.review_panel.select_result();pump(root,app)
            assert app.state.detail.document['session']['session_id']==sid
            assert app.tabs.select()==str(app.review_tab)
        app.review_views.select(1);root.update()
        row=ids[0];bbox=app.report_sessions.bbox(row)
        app.review_panel.toggle_report_row(SimpleNamespace(y=bbox[1]+3));root.update()
        assert app.report_sessions.selection()==(row,)
        app.review_panel.toggle_report_row(SimpleNamespace(y=bbox[1]+3));root.update()
        assert not app.report_sessions.selection()
        app.report_sessions.selection_set(ids);root.update();app.generate_report();pump(root,app)
        assert app.report_snapshot and 'DATASET INDEPENDENTE' in app.review_panel.preview.get('1.0','end')
        app.export_report();pump(root,app);assert 'Exportação concluída' in app.status.get()
        app.open_review()
        assert app.review_views.index(app.review_views.select())==0
        name=next(name for name,r in app.review_panel.catalog.items() if r['session_id']==ids[1])
        app.review_panel.choice.set(name);app.review_panel.select_result();pump(root,app)
        data=app.state.detail.document
        event=next(r['event']['event_id'] for r in data['events'] if 'rule_id' in r['evidence_item'])
        app.events.selection_set(event);app.select_event();root.update()
        assert 'Candidato' in app.review_panel.detail.get('1.0','end')
        assert str(app.review_panel.review_button.cget('state'))=='normal'
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno') as confirm:
            app.submit_review(ReviewStatus.REVIEWED)
        confirm.assert_not_called()
        app.reviewer.set('fixture-reviewer');app.reason.set('Offline UI fixture; not clinical validation')
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=False):app.submit_review(ReviewStatus.REVIEWED)
        assert app.pending_review is None
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=True):app.submit_review(ReviewStatus.REVIEWED)
        pump(root,app)
        assert app.tabs.select()==str(app.review_tab)
        assert app.report_snapshot is None
        assert str(app.review_panel.review_button.cget('state'))=='disabled'
        assert 'fixture-reviewer' in app.review_panel.detail.get('1.0','end')
        assert 'Offline UI fixture' in app.review_panel.detail.get('1.0','end')
        app.retry_review();pump(root,app)
        assert len(w.reader.detail(db,UUID(ids[1])).document['review_histories'][event])==1
        app.review_panel.toggle_review_technical();root.update()
        assert app.event_detail.winfo_ismapped()
        app.review_views.select(1);app.generate_report();pump(root,app)
        assert app.report_snapshot
        detail=w.reader.detail(db,UUID(ids[2])).document
        candidate=detail['events'][-1]['event']
        w.review(db,UUID(ids[2]),request(candidate),candidate['evidence_ref'])
        app.export_report();pump(root,app)
        assert app.report_snapshot is None and 'mudaram' in app.status.get()
        root.geometry('900x600');root.update()
        assert app.review_panel.preview.winfo_height()>=60
        app.patient.set('PAT-002')
        assert not app.review_panel.catalog and app.state.detail is None
        assert not app.events.get_children()
        assert str(app.review_panel.review_button.cget('state'))=='disabled'
        assert source.read_bytes()==before
        provider.assert_not_called()
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        app.audio_panel.stop();root.after_cancel(app.poll_id);root.destroy()
