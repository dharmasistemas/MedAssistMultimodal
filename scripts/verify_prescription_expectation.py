"""Synthetic expectation flow on a new work copy; no models or automated review."""
from pathlib import Path
from uuid import UUID
import argparse
import hashlib
import time
import tkinter as tk

from medassistmultimodal.desktop_multimodal import MultimodalApp
from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
from medassistmultimodal.infrastructure.desktop_summary import SummaryService
from medassistmultimodal.application.register_vitals import encode_json,strict_json
from medassistmultimodal.demo.prescription_expectations import expectation_cases

ROOT=Path(__file__).resolve().parents[1]
SOURCE='data/interim/audio/desktop_workspaces_v1/1a943131-cc8a-47e9-8ed5-92a0b138e47f/audio.sqlite3'
OUTPUT='data/interim/prescriptions/expectation_ui_v1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,doc):
    with path.open('xb') as f:f.write(encode_json(doc))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:raise ValueError('Explicit --execute required')
    output=ROOT/OUTPUT;output.mkdir(parents=True,exist_ok=False)
    cases,refs=expectation_cases();before=sha(ROOT/SOURCE)
    names=['src/medassistmultimodal/domain/prescription_expectation.py',
        'src/medassistmultimodal/application/register_prescription_expectation.py',
        'src/medassistmultimodal/demo/prescription_expectations.py',
        'src/medassistmultimodal/infrastructure/structured_workspace.py',
        'src/medassistmultimodal/infrastructure/desktop_prescriptions.py',
        'src/medassistmultimodal/domain/prescriptions.py',
        'scripts/verify_prescription_expectation.py']
    hashes={n:sha(ROOT/n) for n in names}
    write(output/'config.json',dict(source=SOURCE,source_sha256=before,dependency_sha256=hashes,
        references=refs,inputs_sha256={k:hashlib.sha256(encode_json(v)).hexdigest() for k,v in cases.items()},
        clinical_validation=False,models=0,automated_reviews=0))
    workspace=TextWorkspace(ROOT);db=workspace.create_copy(SOURCE,'PAT-001')
    write(output/'workspace.json',dict(database=db))
    rows=[]
    for case in cases:
        result=workspace.register_scenario(db,'PAT-001','prescriptions',case)
        assert result.persisted
        detail=workspace.reader.detail(db,UUID(result.session_id)).document
        doc=detail['prescriptions'][0]['evidence'];a=doc['expectation']
        assert a['status']==refs[case]
        assert all(r['event']['review_status']=='pending_review' for r in detail['events'])
        assert workspace.retry_structured(db,result.run_id)==result
        write(output/f'{case}.json',dict(case_id=case,session_id=result.session_id,reference=refs[case],detail=detail))
        rows.append(dict(case_id=case,session_id=result.session_id,status=a['status'],reason=a['reason'],
            events=len(detail['events']),candidates=len(doc['expectation_candidates']),
            evidence=detail['prescriptions'][0]['reference']))
    bank_before=sha(ROOT/db)
    root=tk.Tk();root.withdraw();app=MultimodalApp(root,reader=workspace.reader,workspace=workspace,project_root=ROOT)
    def pump():
        deadline=time.monotonic()+30
        while app.worker.busy:
            root.update();time.sleep(.005)
            if time.monotonic()>deadline:raise RuntimeError('UI check exceeded deadline')
        root.update()
    try:
        app.database.set(db);app.load_history();pump()
        for row in rows:
            app.sessions.selection_set(row['session_id']);app.select_session();pump()
            text=app.prescription_summary.get('1.0','end')
            assert {'compatible':'Compatível com o plano','divergent':'Divergência do plano','indeterminate':'Expectativa indeterminada'}[row['status']] in text
            assert sum('Divergência do plano' in str(app.events.item(i,'values')) for i in app.events.get_children())==row['candidates']
        write(output/'ui_checks.json',dict(sessions_checked=8,visual_inspection=False,automated_reviews=0))
    finally:
        if app.worker.busy:app.worker.thread.join(30);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()
    reports=SummaryService(ROOT);snapshot=reports.build(db,'PAT-001',[r['session_id'] for r in rows]);export=reports.export(snapshot)
    assert bank_before==sha(ROOT/db) and before==sha(ROOT/SOURCE)
    assert hashes=={n:sha(ROOT/n) for n in names}
    write(output/'summary.json',dict(database=db,rows=rows,reference_matches=8,
        counts={k:sum(r['status']==k for r in rows) for k in ('compatible','divergent','indeterminate')},
        report_directory=export,new_events=sum(r['events'] for r in rows),
        candidates=sum(r['candidates'] for r in rows),source_unchanged=True,
        read_export_database_unchanged=True,cloud_calls=0,automated_reviews=0,clinical_validation=False))
    print(db,flush=True);print(output.relative_to(ROOT).as_posix(),flush=True)


if __name__=='__main__':main()
