"""Read existing four-modality results through summary UI; no models, reviews or DB writes."""
from medassistmultimodal.desktop_summary import SummaryApp
from medassistmultimodal.desktop_text import TextWorkspace
from medassistmultimodal.application.register_vitals import strict_json,encode_json
from pathlib import Path
import hashlib
import time
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]


def main():
    output=ROOT/'data/interim/multimodal/summary_ui_v1';output.mkdir(exist_ok=False)
    audio=strict_json((ROOT/'data/interim/audio/text_ui_gpt_oss_v1/summary.json').read_bytes())
    video=strict_json((ROOT/'data/interim/rehab26/video_ui_v2/summary.json').read_bytes())
    database=audio['database'];selected=(audio['session_id'],'db11026c-682d-5f28-8763-38576e82f705',
        '46bef36c-d66d-5408-baf6-a3714cd1ac94',video['session_id'])
    before=hashlib.sha256((ROOT/database).read_bytes()).hexdigest()
    (output/'config.json').write_bytes(encode_json(dict(date='2026-11-10',database=database,session_ids=selected,
        database_sha256=before,models_executed=0,code_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in [
        'src/medassistmultimodal/desktop_summary.py','src/medassistmultimodal/infrastructure/desktop_summary.py','scripts/verify_summary_ui.py']})))
    root=tk.Tk();root.withdraw();workspace=TextWorkspace(ROOT)
    app=SummaryApp(root,reader=workspace.reader,workspace=workspace,project_root=ROOT)
    def pump():
        deadline=time.monotonic()+20
        while app.worker.busy:
            root.update();time.sleep(.005)
            if time.monotonic()>deadline:raise RuntimeError('Verification deadline exceeded')
        root.update()
    try:
        app.database.set(database);app.load_history();pump();app.load_report_catalog();pump()
        app.report_sessions.selection_set(selected);root.update();app.generate_report();pump()
        assert app.report_snapshot is not None,app.status.get()
        snapshot=app.report_snapshot;document=snapshot.document
        assert len(document['patient_sessions'])==3 and len(document['dataset_sessions'])==1
        assert 'DATASET INDEPENDENTE' in app.report_text.get('1.0','end')
        app.export_report();pump();assert 'Exportação concluída:' in app.status.get(),app.status.get()
        directory=f"data/interim/multimodal/reports_v1/{document['report_id']}"
        assert strict_json((ROOT/directory/'summary.json').read_bytes())==document
        assert (ROOT/directory/'summary.txt').read_text(encoding='utf-8')==document['text']
        assert app.summary_service.export(snapshot)==directory
        assert hashlib.sha256((ROOT/database).read_bytes()).hexdigest()==before
        summary=dict(date='2026-11-10',database=database,selected_session_ids=selected,export_directory=directory,
            report_id=document['report_id'],counts=document['counts'],patient_sessions=3,dataset_sessions=1,
            models_executed=0,reviews_created=0,database_unchanged=True,export_replay_without_duplication=True,
            visual_inspection=False,clinical_validation=False)
        (output/'summary.json').write_bytes(encode_json(summary));print(encode_json(summary).decode('utf-8'))
    finally:
        if app.worker.busy:app.worker.thread.join(20)
        root.after_cancel(app.poll_id);root.destroy()


if __name__=='__main__':main()
