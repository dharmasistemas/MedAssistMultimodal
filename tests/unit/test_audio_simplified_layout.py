import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID
from datetime import datetime, timezone

import pytest
from tests.unit.test_desktop_text import text_workspace
from tests.unit.test_desktop_history import persisted


@pytest.mark.parametrize('mode',['negated','unavailable','timeout','disabled'])
def test_readable_result_preserves_context_and_provider_failure(text_workspace,mode):
    from medassistmultimodal.desktop_audio_layout import audio_result_text
    s,db,_,_,_,_=text_workspace
    result=s.process(db,'PAT-001','A03',datetime.now(timezone.utc))
    detail=s.reader.detail(db,UUID(result.session_id));document=detail.document;doc=document['documents'][0]['evidence']
    if mode=='unavailable':
        doc['asr'].update(status='unavailable',result=None)
        doc['rules'].update(status='unavailable',items=None)
    elif mode=='timeout':doc['llm'].update(status='timeout',result=None)
    text=audio_result_text(SimpleNamespace(document=document))
    if mode=='negated':
        assert 'negado no relato atual' in text
        assert 'candidato à revisão humana' not in text
    elif mode=='unavailable':
        assert 'Transcrição indisponível' in text and 'Menções indisponíveis' in text
        assert 'Nenhuma menção configurada encontrada' not in text
    elif mode=='timeout':assert 'Prazo excedido' in text
    else:assert 'Desativada' in text


class FakePlayer:
    def __init__(self):self.opened=False;self.duration_ms=5000;self.mode='closed';self.path=None;self.closes=0
    def open(self,path):self.path=path;self.opened=True;self.mode='stopped'
    def play(self):self.mode='playing'
    def pause(self):self.mode='paused'
    def close(self):self.opened=False;self.mode='closed';self.closes+=1
    def status(self):return (1200 if self.opened else 0),self.mode


def check_audio_simplified_layout(tmp_path,text_workspace,tk_runtime):
    from medassistmultimodal.desktop_simplified import SimplifiedApp
    from tests.unit.test_desktop_workflow import pump
    s,db,provider,factory,transcriber,_=text_workspace
    root=tk.Toplevel(tk_runtime);player=FakePlayer()
    app=SimplifiedApp(root,reader=s.reader,workspace=s,project_root=tmp_path,audio_player=player)
    decoding=patch('medassistmultimodal.desktop_audio_layout.prepare_listening_audio',
                   side_effect=lambda path:SimpleNamespace(path=path,close=lambda:None))
    decoding.start()
    try:
        app.database.set(db);app.load_history();pump(root,app)
        app.tabs.select(app.audio_tab);app.case.set('A03');root.update()
        assert not app.use_cloud_text.get()
        app.audio_panel.play();pump(root,app);assert player.opened and player.mode=='playing'
        factory.assert_not_called();transcriber.transcribe_with_details.assert_not_called()
        app.audio_panel.pause();assert 'pausado' in app.audio_panel.clock.get()
        app.audio_panel.play();assert player.mode=='playing'
        app.case.set('A99');assert not player.opened
        app.case.set('A03');app.audio_panel.play();pump(root,app);app.use_cloud_text.set(True)
        with patch('medassistmultimodal.desktop_text.messagebox.askyesno',return_value=False):app.process_audio()
        assert not player.opened
        factory.assert_not_called();transcriber.transcribe_with_details.assert_not_called()
        with patch('medassistmultimodal.desktop_text.messagebox.askyesno',return_value=True):app.process_audio()
        pump(root,app)
        provider.generate.assert_called_once()
        assert app.audio_panel.history_ids
        selected=next(name for name,sid in app.audio_panel.history_ids.items()
                      if s.reader.detail(db,UUID(sid)).document['documents'][0]['evidence']['llm']['status']=='succeeded')
        app.audio_panel.history_value.set(selected);app.audio_panel.select_history();pump(root,app)
        text=app.audio_panel.result.get('1.0','end')
        assert 'Não senti dor.' in text and 'Sentimento do texto: Neutro' in text
        assert 'não é emoção vocal' in text
        assert not app.audio_panel.technical_open
        app.audio_panel.toggle_technical();root.update();assert app.audio.winfo_ismapped()
        app.audio_panel.kind.set('Pausas de áudio (piloto)');app.audio_panel.choose_kind()
        assert not app.use_cloud_text.get() and str(app.cloud_check.cget('state'))=='disabled'
        assert app.case.get()=='AP01'
        with patch.object(s,'register_scenario') as register,patch('medassistmultimodal.desktop_multimodal.messagebox.askyesno',return_value=False):app.process_audio()
        register.assert_not_called();provider.generate.assert_called_once()
        app.audio_panel.kind.set('Relato e transcrição');app.audio_panel.choose_kind();app.case.set('A03')
        app.audio_panel.play();app.patient.set('PAT-002');pump(root,app)
        assert not player.opened and not app.audio_panel.history_ids
        assert 'Contexto alterado' in app.audio_panel.result.get('1.0','end')
        root.geometry('900x600');root.update()
        assert app.audio_panel.result.winfo_height()>=80
        assert app.audio_panel.result.winfo_rootx()+app.audio_panel.result.winfo_width()<=app.audio_tab.winfo_rootx()+app.audio_tab.winfo_width()
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        decoding.stop();player.close();root.after_cancel(app.poll_id);root.destroy()
