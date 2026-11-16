"""Three real local decodes on a fresh work copy; no speech/language model."""
import os
os.environ['MKL_THREADING_LAYER']='SEQUENTIAL'
os.environ['OMP_NUM_THREADS']='4'
os.environ['HF_HUB_OFFLINE']='1'

from pathlib import Path
from uuid import UUID
import argparse
import hashlib
import json
import time
import tkinter as tk

from medassistmultimodal.desktop_summary import SummaryApp
from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
from medassistmultimodal.infrastructure.desktop_summary import SummaryService
from medassistmultimodal.infrastructure.desktop_acoustics import INVENTORY,RECEIPT
from medassistmultimodal.application.register_vitals import strict_json,encode_json

ROOT=Path(__file__).resolve().parents[1]
SOURCE='data/interim/audio/desktop_workspaces_v1/a62bde4e-4ce6-4c3d-bfaf-e867474659ce/audio.sqlite3'
OUTPUT='data/interim/audio/acoustic_pilot_v1'
REFERENCES='specs/acoustic_pilot_listen_references_v1.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,doc):
    with path.open('xb') as f:f.write(encode_json(doc))


def annotation_page(output,refs):
    # Deliberately omit every model/detector interval and prediction from the annotation page.
    cases=[dict(case_id=k,path=v['path'],sha256=v['sha256']) for k,v in refs['cases'].items()]
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Anotação humana de pausas</title>
<style>body{font:17px system-ui;max-width:900px;margin:30px auto;padding:16px}section{border:1px solid #ccc;border-radius:10px;padding:20px;margin:20px 0}button{padding:9px;margin:5px}audio{width:100%}li{margin:8px}input{width:100px}</style>
<h1>Referência temporal humana</h1><p>Ouça e marque pausas internas de pelo menos 0,60 s. Esta página não mostra a saída do detector. Não marque sons de expiração automaticamente como silêncio.</p>
<p>Use os botões no tempo atual ou digite os tempos em segundos. Confira cada lista. Lista vazia revisada significa que você não identificou pausas longas; não é diagnóstico.</p><main id="cases"></main><button id="save">Salvar referência temporal em JSON</button><p id="message"></p>
<script>
const cases=CASE_DATA;const state={};
for(const c of cases){state[c.case_id]={intervals:[],reviewed:false};const section=document.createElement('section');
section.innerHTML=`<h2>${c.case_id}</h2><audio controls preload="metadata" src="../elevenlabs_tests/${c.path.split('/').pop()}"></audio><p>Início: <input class="start" type="number" min="0" step="0.01"> Fim: <input class="end" type="number" min="0" step="0.01"></p><button class="markstart">Marcar início atual</button><button class="markend">Marcar fim atual</button><button class="add">Adicionar intervalo</button><ul></ul><label><input class="review" type="checkbox"> Ouvi e conferi esta lista</label>`;
const audio=section.querySelector('audio'),start=section.querySelector('.start'),end=section.querySelector('.end'),list=section.querySelector('ul'),review=section.querySelector('.review');
const reset=()=>{review.checked=false;state[c.case_id].reviewed=false;};
const render=()=>{list.innerHTML='';state[c.case_id].intervals.forEach((p,i)=>{const li=document.createElement('li');li.textContent=`${p.start_seconds.toFixed(2)}–${p.end_seconds.toFixed(2)} s `;const b=document.createElement('button');b.textContent='Remover';b.onclick=()=>{state[c.case_id].intervals.splice(i,1);reset();render();};li.append(b);list.append(li);});};
section.querySelector('.markstart').onclick=()=>{start.value=audio.currentTime.toFixed(2);};section.querySelector('.markend').onclick=()=>{end.value=audio.currentTime.toFixed(2);};
section.querySelector('.add').onclick=()=>{const a=Number(start.value),b=Number(end.value);const xs=state[c.case_id].intervals;
if(start.value===''||end.value===''||!Number.isFinite(a)||!Number.isFinite(b)||a<=0||b<=a||b-a<0.6-1e-9||!Number.isFinite(audio.duration)||b>=audio.duration||xs.some(p=>a<p.end_seconds&&b>p.start_seconds)){alert('Informe intervalo interno válido de pelo menos 0,60 s, sem sobreposição.');return;}
xs.push({start_seconds:a,end_seconds:b});xs.sort((p,q)=>p.start_seconds-q.start_seconds);reset();render();};
review.onchange=()=>{state[c.case_id].reviewed=review.checked;};document.querySelector('#cases').append(section);}
document.querySelector('#save').onclick=()=>{if(cases.some(c=>!state[c.case_id].reviewed)){alert('Confira as três listas antes de salvar.');return;}
const result={version:'acoustic-temporal-reference-v1',source:'human_manual_audio_annotation',review_status:'provided_by_listener_pending_project_import',clinical_validation:false,cases:Object.fromEntries(cases.map(c=>[c.case_id,{...c,...state[c.case_id]}]))};
const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='acoustic_temporal_reference_v1.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.querySelector('#message').textContent='Salve o JSON no projeto e informe o caminho. Nenhum intervalo do detector foi usado nesta página.';};
</script></html>'''
    with (output/'temporal_review.html').open('x',encoding='utf-8') as f:f.write(page.replace('CASE_DATA',json.dumps(cases,ensure_ascii=False)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:raise ValueError('Explicit --execute required')
    output=ROOT/OUTPUT;output.mkdir(parents=True,exist_ok=False)
    refs=strict_json((ROOT/REFERENCES).read_bytes())
    names=[SOURCE,REFERENCES,INVENTORY,RECEIPT,'specs/acoustic_pilot_listen_review_v1.csv',
        'specs/acoustic_pause_pilot_v1.md','src/medassistmultimodal/domain/internal_pauses.py',
        'src/medassistmultimodal/domain/audio_features.py','src/medassistmultimodal/application/analyze_acoustic_pauses.py',
        'src/medassistmultimodal/application/register_acoustics.py','src/medassistmultimodal/providers/acoustic_local.py',
        'src/medassistmultimodal/infrastructure/desktop_acoustics.py','src/medassistmultimodal/infrastructure/structured_workspace.py',
        'scripts/evaluate_acoustic_pilot.py',*[v['path'] for v in refs['cases'].values()]]
    hashes={n:sha(ROOT/n) for n in names}
    for r in refs['cases'].values():
        assert hashes[r['path']]==r['sha256'] and r['review_status']=='reviewed_by_project_user'
    write(output/'config.json',dict(date='2026-11-13',source=SOURCE,dependency_sha256=hashes,
        profile='internal-pauses-v1',planned_cases=['AP01','AP02','AP03'],retries=0,
        references_used_only_for_evaluation=True,asr_runs=0,llm_calls=0,temporal_reference='pending_human_intervals'))
    workspace=TextWorkspace(ROOT);db=workspace.create_copy(SOURCE,'PAT-001');write(output/'workspace.json',dict(database=db))
    rows=[]
    for key,ref in refs['cases'].items():
        outcome=workspace.register_scenario(db,'PAT-001','acoustics',key)
        if not outcome.persisted:raise RuntimeError('Persistence pending; do not decode again')
        detail=workspace.reader.detail(db,UUID(outcome.session_id)).document;doc=detail['acoustics'][0]['evidence'];a=doc['assessment']
        predicted='frequent_pauses' if a['status']=='signal' else 'not_frequent' if a['status']=='no_signal' else 'insufficient_evidence'
        row=dict(case_id=key,session_id=outcome.session_id,run_id=outcome.run_id,
            reference=ref['expected_pause_pattern'],prediction=predicted,
            correct=predicted==ref['expected_pause_pattern'],assessment=a,processing_seconds=doc['processing_seconds'],
            events=len(detail['events']),candidates=len(doc['candidates']),reference_exhalation=ref['exhalation_audible'],
            temporal_accuracy=None,temporal_reference_status='pending',evidence=detail['acoustics'][0]['reference'])
        write(output/f'{key}.json',dict(**row,detail=detail));rows.append(row);print(key,predicted,'pauses',a['long_pause_count'],flush=True)
    before=sha(ROOT/db);root=tk.Tk();root.withdraw();app=SummaryApp(root,reader=workspace.reader,workspace=workspace,project_root=ROOT)
    def pump():
        deadline=time.monotonic()+45
        while app.worker.busy:
            root.update();time.sleep(.005)
            if time.monotonic()>deadline:raise RuntimeError('UI deadline')
        root.update()
    try:
        app.database.set(db);app.load_history();pump()
        app.structured_modality.set('Pausas de áudio');app.refresh_structured_cases()
        assert tuple(app.structured_choices.cget('values'))==('AP01','AP02','AP03')
        for r in rows:
            app.sessions.selection_set(r['session_id']);app.select_session();pump()
            assert 'ASR e LLM não executados' in app.audio.get('1.0','end')
            assert len(app.events.get_children())==r['events']
        app.load_report_catalog();pump();app.report_sessions.selection_set([r['session_id'] for r in rows]);root.update()
        app.generate_report();pump();assert app.report_snapshot is not None
        report_id=app.report_snapshot.document['report_id'];app.export_report();pump()
        report_path=f'data/interim/multimodal/reports_v1/{report_id}'
        assert (ROOT/report_path/'manifest.json').is_file()
        write(output/'ui_checks.json',dict(sessions_checked=3,report_directory=report_path,visual_inspection=False,automated_reviews=0))
    finally:
        if app.worker.busy:app.worker.thread.join(45);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()
    assert before==sha(ROOT/db) and hashes=={n:sha(ROOT/n) for n in names}
    annotation_page(output,refs)
    write(output/'summary.json',dict(database=db,rows=rows,correct=sum(r['correct'] for r in rows),attempts=3,
        report_directory=report_path,asr_runs=0,llm_calls=0,automated_reviews=0,
        source_and_inputs_unchanged=True,temporal_metrics=None,temporal_reference_status='pending_human_annotation',
        clinical_validation=False))
    print('COMPLETE',db,flush=True)


if __name__=='__main__':main()
