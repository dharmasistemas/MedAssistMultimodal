import tkinter as tk
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from tests.unit.test_structured_workspace import structured


@pytest.mark.parametrize('modality,case,expected',[
    ('vitals','V01','Nenhuma ocorrência deste perfil'),
    ('vitals','V02','ocorrência(s) do perfil experimental'),
    ('prescriptions','E01','Compatível com o plano sintético'),
    ('prescriptions','E02','Divergência do plano sintético'),
    ('prescriptions','E03','Expectativa indeterminada'),
    ('prescriptions','E04','equivalência não interpretada'),
    ('prescriptions','P06','Expectativa não avaliada'),
])
def test_anomaly_summary_preserves_rule_outcome(tmp_path,structured,modality,case,expected):
    from medassistmultimodal.desktop_anomaly_layout import anomaly_result_text
    s,db,_=structured;outcome=s.register_scenario(db,'PAT-001',modality,case)
    detail=s.reader.detail(db,UUID(outcome.session_id))
    text=anomaly_result_text(detail)
    assert expected in text
    assert 'sem LLM' in text
    assert 'sintético' in text or 'sintéticos' in text
    if case=='E02':
        assert 'esperado 15; observado 20' in text
        assert 'Não determina segurança terapêutica' in text
    if case=='V01':assert 'não comprova normalidade' in text


def test_missing_raw_data_and_zero_coverage_are_not_normality(tmp_path,structured):
    from medassistmultimodal.desktop_anomaly_layout import anomaly_result_text
    s,db,_=structured;outcome=s.register_scenario(db,'PAT-001','vitals','V01')
    data=s.reader.detail(db,UUID(outcome.session_id)).document
    data['vitals'][0]['raw_series']['status']='unavailable'
    data['vitals'][0]['evidence']['result']['coverage'][0]['valid_samples']=0
    text=anomaly_result_text(SimpleNamespace(document=data))
    assert 'Sem dados válidos' in text and 'não foram reconstruídas' in text
    assert 'não comprova normalidade' in text


def check_anomaly_simplified_layout(tmp_path,structured,tk_runtime):
    from medassistmultimodal.desktop_simplified import SimplifiedApp
    from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
    from tests.unit.test_desktop_workflow import pump
    s,db,source=structured
    ids={case:s.register_scenario(db,'PAT-001',modality,case).session_id
         for modality,case in [('vitals','V01'),('vitals','V02'),('prescriptions','E01'),('prescriptions','E02'),('prescriptions','E03')]}
    before=source.read_bytes();factory=Mock(side_effect=AssertionError('LLM must not be called'))
    workspace=TextWorkspace(tmp_path,text_provider_factory=factory)
    root=tk.Toplevel(tk_runtime)
    app=SimplifiedApp(root,reader=workspace.reader,workspace=workspace,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app)
        app.tabs.select(app.anomaly_tab);root.update()
        assert app.anomaly_panel.kinds.cget('values')==('Vitais','Prescrições')
        assert not app.structured_actions.winfo_manager()
        assert len(app.anomaly_panel.history_ids)==5
        assert not app.anomaly_tabs.winfo_ismapped()
        for case,expected in [('V01','Nenhuma ocorrência'),('V02','ocorrência(s)'),('E01','Compatível'),('E02','Divergência'),('E03','indeterminada')]:
            name=next(name for name,sid in app.anomaly_panel.history_ids.items() if sid==ids[case])
            app.anomaly_panel.history_value.set(name);app.anomaly_panel.select_history();pump(root,app)
            assert app.tabs.select()==str(app.anomaly_tab)
            assert expected in app.anomaly_panel.result.get('1.0','end')
        app.anomaly_panel.toggle_technical();root.update()
        assert app.anomaly_tabs.winfo_ismapped()
        assert 'Expectativa indeterminada' in app.prescription_summary.get('1.0','end')
        app.anomaly_panel.toggle_technical()
        app.structured_modality.set('Prescrições');app.refresh_structured_cases();app.structured_case.set('E02')
        app.use_cloud_text.set(True)
        count=len(app.state.rows)
        with patch('medassistmultimodal.desktop_multimodal.messagebox.askyesno',return_value=False),patch.object(workspace,'register_scenario') as register:
            app.register_structured_scenario()
        register.assert_not_called()
        with patch('medassistmultimodal.desktop_multimodal.messagebox.askyesno',return_value=True):
            app.register_structured_scenario()
        pump(root,app)
        assert len(app.anomaly_panel.history_ids)==count+1
        factory.assert_not_called()
        root.geometry('900x600');root.update()
        assert app.anomaly_panel.result.winfo_height()>=80
        assert app.anomaly_panel.result.winfo_rootx()+app.anomaly_panel.result.winfo_width()<=app.anomaly_tab.winfo_rootx()+app.anomaly_tab.winfo_width()
        app.patient.set('PAT-002')
        assert not app.anomaly_panel.history_ids
        assert 'PAT-002' in app.anomaly_panel.origin.get()
        assert 'Divergência' not in app.anomaly_panel.result.get('1.0','end')
        assert source.read_bytes()==before
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        app.audio_panel.stop();root.after_cancel(app.poll_id);root.destroy()
