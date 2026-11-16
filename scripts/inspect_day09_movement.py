"""Tarefa 3: curvas completas dos casos development, sem mudança de regras."""
import csv
from dataclasses import asdict
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path
import time

from medassistmultimodal.application.ex1_repetitions import Ex1Config
from medassistmultimodal.application.movement_inspection import inspect_pose,summarize_timeline
from medassistmultimodal.infrastructure.rehab26_landmarks import LandmarkSequence,Representation
from medassistmultimodal.infrastructure.video_pose import MediaPipePose,VideoFrame,safe_local_file

ROOT=Path(__file__).resolve().parents[1]
SELECTION_SHA='38b9dfd44b75c2d9af033763e7867a73a1f63e22dd6f9d9813cccf45ff909b48'


def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))


def sha(path):
    h=hashlib.sha256()
    with safe_local_file(ROOT/path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def main():
    import cv2
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    started=time.perf_counter()
    if sha('data/manifests/day09_inspection_selection_v1.json')!=SELECTION_SHA:raise ValueError('Seleção alterada')
    selected=read('data/manifests/day09_inspection_selection_v1.json')
    for path,expected in selected['input_sha256'].items():
        if sha(path)!=expected:raise ValueError('Entrada alterada')
    freeze=read('data/manifests/day08_evaluation_freeze.json')
    for path,expected in freeze['sha256'].items():
        if sha(path)!=expected:raise ValueError('Congelamento v1 alterado')
    config=Ex1Config(**read('configs/ex1_rules_v1.json'))
    manifest=read('data/manifests/rehab26_landmarks_manifest.json')
    if sha(manifest['local_index_path'])!=manifest['local_index_sha256']:raise ValueError('Índice divergente')
    members=read(manifest['local_index_path'])['files']
    assets=read('data/manifests/day07_rgb_assets.json')
    for asset in [assets['video'],assets['model']]:
        if sha(asset['path'])!=asset['sha256']:raise ValueError('Asset divergente')
    csv_path=ROOT/'data/interim/rehab26/day09_visuals_v1/review_checklist.csv'
    text=csv_path.read_text(encoding='utf-8-sig');dialect=csv.Sniffer().sniff(text,delimiters=',;')
    reviews={r['case_id']:r for r in csv.DictReader(text.splitlines(),dialect=dialect)}
    receipt=read('reports/DAY_09_TASK_02_REVIEW_2026-11-01.json')
    if sha(csv_path)!=receipt['source_sha256']:raise ValueError('Revisão mudou; registrar nova versão antes de analisar')
    output=ROOT/'data/interim/rehab26/day09_movement_v1';output.mkdir(exist_ok=False)
    report=[];figures=[];local_hashes={}
    def plot(case,source,samples,summary):
        cid=case['case_id'];fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True)
        xs=[s['frame'] for s in samples]
        for ax,name,limit,title in [(axes[0],'right_elbow',config.elbow_min_degrees,'Cotovelo direito'),
                                    (axes[1],'right_arm_trunk',config.arm_peak_min_degrees,'Braço–tronco direito')]:
            ax.plot(xs,[s['measurements'][name]['diagnostic_unfiltered_degrees'] for s in samples],color='.65',linestyle=':',label='Sem filtro de visibilidade: diagnóstico técnico apenas')
            ax.plot(xs,[s['measurements'][name]['degrees'] for s in samples],color='#0064aa',label='Medida com visibilidade v1')
            ax.axhline(limit,color='#b22',linestyle='--',label=f'Referência experimental v1: {limit:g}°')
            ax.set_ylabel('Graus');ax.set_ylim(-5,185);ax.set_title(title);ax.grid(alpha=.2);ax.legend(fontsize=8)
        for i in ['12','14','16','24']:axes[2].plot(xs,[s['visibility'][i] for s in samples],label='Ponto '+i)
        axes[2].axhline(config.min_visibility,color='#b22',linestyle='--',label='Visibilidade mínima v1')
        axes[2].set_ylim(-.05,1.05);axes[2].set_ylabel('Visibilidade estimada');axes[2].set_xlabel('Índice original do frame (tempo nominal = índice/30 s)');axes[2].legend(ncol=5,fontsize=8);axes[2].grid(alpha=.2)
        for ax in axes:
            for index in [case['first_frame'],case['middle_frame'],case['last_frame']]:ax.axvline(index,color='.7',linewidth=.6)
        fig.suptitle(f'{cid} | {source} | orientação {case["orientation"]}° | {case["reference_primary_code"] or "Referência correta"}\nLacunas preservadas; sem suavização/interpolação; valores não são diagnóstico clínico',fontsize=12)
        fig.tight_layout(rect=(0,0,1,.94));path=output/f'{cid}_{source}.png';fig.savefig(path,dpi=140);plt.close(fig)
        figures.append((cid,source,path.name));local_hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    def store(case,source,samples):
        summary=summarize_timeline(samples,first=case['first_frame'],last=case['last_frame'],fps=config.fps,elbow_limit=config.elbow_min_degrees)
        path=output/f'{case["case_id"]}_{source}_timeline.json'
        path.write_text(json.dumps(samples,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');local_hashes[path.relative_to(ROOT).as_posix()]=sha(path)
        plot(case,source,samples,summary)
        return summary
    for case in selected['cases']:
        cid=case['case_id'];first=case['first_frame'];last=case['last_frame']
        member=next(m for m in members if m['participant_ref']==case['participant_ref'] and m['representation']=='3d')
        with LandmarkSequence(ROOT/member['path'],representation=Representation.THREE_D,expected_sha256=case['npy_sha256']) as seq:
            npy=[inspect_pose(seq.frame(i),min_visibility=config.min_visibility) for i in range(first,last+1)]
        item={'case_id':cid,'orientation':case['orientation'],'first_frame':first,'last_frame':last,
              'reference_primary_code':case['reference_primary_code'],'npy':store(case,'NPY',npy),
              'previous_v1_rules':case['previous_v1_rules'],'rgb_video':None,'human_snapshot_review':reviews.get(cid),
              'rgb_available':case['rgb_available']}
        for rule,name in [('bent_elbow_proxy','right_elbow'),('low_elevation_proxy','right_arm_trunk')]:
            previous=next(x for x in case['previous_v1_rules'] if x['name']==rule)
            if abs(previous['coverage']-item['npy'][name]['coverage'])>1e-12:raise ValueError('Cobertura NPY não reproduz v1')
        if case['rgb_available']:
            capture=cv2.VideoCapture(str(safe_local_file(ROOT/case['rgb_path'])))
            try:
                if not capture.isOpened() or abs(capture.get(cv2.CAP_PROP_FPS)-config.fps)>.001:raise ValueError('Vídeo/FPS inválido')
                if not capture.set(cv2.CAP_PROP_POS_FRAMES,first) or abs(capture.get(cv2.CAP_PROP_POS_FRAMES)-first)>.1:raise ValueError('Seek divergente')
                samples=[]
                with MediaPipePose(ROOT/assets['model']['path']) as detector:
                    for i in range(first,last+1):
                        ok,image=capture.read()
                        if not ok or abs(capture.get(cv2.CAP_PROP_POS_FRAMES)-i-1)>.1:raise ValueError('Leitura/índice divergente')
                        pose=detector.detect(VideoFrame(i,i/config.fps,round(i*1000/config.fps),cv2.cvtColor(image,cv2.COLOR_BGR2RGB)))
                        samples.append(inspect_pose(pose,min_visibility=config.min_visibility))
                item['rgb_video']=store(case,'RGB_VIDEO',samples)
            finally:capture.release()
        report.append(item);print('Inspected',cid,flush=True)
    sections=[]
    for case in selected['cases']:
        cid=case['case_id'];parts=[f'<section><h2>{cid} — orientação {case["orientation"]}°</h2>']
        for _,source,name in [f for f in figures if f[0]==cid]:parts.append(f'<h3>{source}</h3><a href="{name}"><img src="{name}" alt="Curvas {cid} {source}"></a>')
        if cid in reviews:parts.append('<p>Observação humana nas três imagens: '+html.escape(reviews[cid]['notes'])+'</p>')
        else:parts.append('<p>Apenas NPY; sem revisão visual sobre vídeo desse participante.</p>')
        sections.append(''.join(parts)+'</section>')
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Dia 9 — curvas de movimento</title><style>body{font:17px sans-serif;max-width:1400px;margin:30px auto;padding:16px;line-height:1.5}img{width:100%}section{border-top:2px solid #aaa;margin-top:40px}</style><h1>Dia 9 — tarefa 3: medidas e qualidade</h1><p>NPY e RGB VIDEO são fontes diferentes. Cinza pontilhado: geometria sem filtro de visibilidade, apenas para inspeção técnica. Azul: medidas válidas pelo filtro v1; lacunas significam indisponibilidade, não ângulo zero. Linhas vermelhas são referências experimentais existentes, sem alteração.</p><p>IMAGE das três fotos da tarefa 2 difere do VIDEO completo aqui. Observações humanas não comprovam qualidade de cada frame. Não há nova decisão de regras ou diagnóstico clínico.</p>'''+''.join(sections)+'</html>'
    (output/'index.html').write_text(page,encoding='utf-8');local_hashes[(output/'index.html').relative_to(ROOT).as_posix()]=sha(output/'index.html')
    payload={'date':'2026-11-01','task':'day09_task03','selection_sha256':SELECTION_SHA,'review_csv_sha256':sha(csv_path),
        'generator_sha256':sha(Path(__file__)),'config':asdict(config),'npy_cases':12,'rgb_cases':10,
        'versions':{p:importlib.metadata.version(p) for p in ['mediapipe','opencv-contrib-python','numpy','matplotlib']},
        'elapsed_seconds':time.perf_counter()-started,'case_summaries':report,'local_artifact_sha256':local_hashes,
        'local_index':(output/'index.html').relative_to(ROOT).as_posix(),'rules_changed':False,'new_rule_classifications':False,
        'limitations':['All selected development intervals only','Unfiltered geometry never enters rule decisions',
                       'RGB VIDEO restarted per interval differs from three IMAGE snapshots','No interpolation, smoothing or legacy 2D conversion',
                       'No new holdout evaluation or clinical conclusion; mismatch interpretation belongs to later tasks']}
    (ROOT/'reports/DAY_09_TASK_03_2026-11-01.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Finished',len(report),'cases',flush=True)


if __name__=='__main__':main()
