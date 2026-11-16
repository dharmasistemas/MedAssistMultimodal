"""Tarefa 2: imagens de inspeção local; sem regras, métricas ou consulta evaluation."""
import csv
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path

from medassistmultimodal.infrastructure.pose_inspection import normalized_pixel
from medassistmultimodal.infrastructure.video_pose import safe_local_file

ROOT=Path(__file__).resolve().parents[1]
SELECTION_SHA='38b9dfd44b75c2d9af033763e7867a73a1f63e22dd6f9d9813cccf45ff909b48'


def sha(path):
    h=hashlib.sha256()
    with safe_local_file(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def main():
    import cv2
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    selection_path=ROOT/'data/manifests/day09_inspection_selection_v1.json'
    if sha(selection_path)!=SELECTION_SHA:raise ValueError('Seleção v1 divergente')
    selection=json.loads(selection_path.read_text(encoding='utf-8'))
    assets=json.loads((ROOT/'data/manifests/day07_rgb_assets.json').read_text())
    model=safe_local_file(ROOT/assets['model']['path'])
    if sha(model)!=assets['model']['sha256']:raise ValueError('Modelo divergente')
    for path,expected in selection['input_sha256'].items():
        if sha(ROOT/path)!=expected:raise ValueError('Entrada da seleção divergente')
    output=ROOT/'data/interim/rehab26/day09_visuals_v1'
    output.mkdir(exist_ok=False)
    options=vision.PoseLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(model),delegate=python.BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.IMAGE,num_poses=1,min_pose_detection_confidence=.5,
        min_pose_presence_confidence=.5,min_tracking_confidence=.5,output_segmentation_masks=False)
    observations=[];checklist=[];sections=[];artifact_hashes={}
    connections=[(11,12),(11,23),(12,24),(23,24),(12,14),(14,16),(11,13),(13,15)]
    selected_ids={12:'12 shoulder',14:'14 elbow',16:'16 wrist',24:'24 hip'}
    capture=cv2.VideoCapture(str(safe_local_file(ROOT/assets['video']['path'])))
    if not capture.isOpened():raise ValueError('Vídeo indisponível')
    try:
        fps=float(capture.get(cv2.CAP_PROP_FPS))
        if abs(fps-30.)>.001:raise ValueError('FPS diverge da seleção')
        with vision.PoseLandmarker.create_from_options(options) as detector:
            for case in selection['cases']:
                cid=case['case_id'];available=case['rgb_available']
                if not available:
                    sections.append(f'<section><h2>{cid} — apenas NPY</h2><p>Sem vídeo local. Conferência visual não preparada; nenhuma imagem inventada.</p></section>')
                    continue
                if case['rgb_path']!=assets['video']['path'] or case['rgb_sha256']!=assets['video']['sha256']:
                    raise ValueError('Vídeo do caso divergente')
                if sha(ROOT/case['rgb_path'])!=case['rgb_sha256']:raise ValueError('Hash do vídeo divergente')
                directory=output/cid;directory.mkdir();columns=[];review_frames=[]
                for role in ['first','middle','last']:
                    index=case[role+'_frame']
                    if not capture.set(cv2.CAP_PROP_POS_FRAMES,index):raise ValueError('Seek não suportado')
                    before=capture.get(cv2.CAP_PROP_POS_FRAMES);ok,image=capture.read();after=capture.get(cv2.CAP_PROP_POS_FRAMES)
                    if not ok or abs(before-index)>.1 or abs(after-index-1)>.1:raise ValueError('Índice de leitura divergente')
                    height,width=image.shape[:2]
                    result=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)))
                    overlay=image.copy();points=[];pixels={}
                    if len(result.pose_landmarks)==1 and len(result.pose_landmarks[0])==33:
                        for i,p in enumerate(result.pose_landmarks[0]):
                            pixel=normalized_pixel(p.x,p.y,width,height)
                            points.append({'index':i,'x_normalized':p.x,'y_normalized':p.y,'z_relative':p.z,'visibility':p.visibility,
                                           'pixel':pixel,'drawn':pixel is not None})
                            if pixel is not None:pixels[i]=(pixel,p.visibility)
                        for a,b in connections:
                            if a in pixels and b in pixels:
                                low=min(pixels[a][1],pixels[b][1])<.5
                                cv2.line(overlay,pixels[a][0],pixels[b][0],(0,170,255) if low else (0,255,0),5)
                        for i,(pixel,visibility) in pixels.items():
                            color=(0,170,255) if visibility<.5 else (0,255,0)
                            cv2.circle(overlay,pixel,10 if i in selected_ids else 5,color,-1)
                            if i in selected_ids:
                                label=f'{selected_ids[i]} v={visibility:.2f}'
                                tx=min(max(8,pixel[0]+12),width-380);ty=max(28,pixel[1]-14)
                                cv2.putText(overlay,label,(tx,ty),cv2.FONT_HERSHEY_SIMPLEX,.75,(0,0,0),5)
                                cv2.putText(overlay,label,(tx,ty),cv2.FONT_HERSHEY_SIMPLEX,.75,color,2)
                    for name,img in [('original',image),('overlay',overlay)]:
                        path=directory/f'{role}_{name}.jpg'
                        if not cv2.imwrite(str(path),img,[cv2.IMWRITE_JPEG_QUALITY,92]):raise ValueError('Falha ao salvar imagem')
                        artifact_hashes[path.relative_to(ROOT).as_posix()]=sha(path)
                    observations.append({'case_id':cid,'role':role,'frame':index,'nominal_seconds':index/fps,
                        'decoder_before':before,'decoder_after':after,'image_width':width,'image_height':height,
                        'pose_count':len(result.pose_landmarks),'points':points,'review_status':'pending_visual_review'})
                    columns.append(f'<div><h3>{role}: frame {index} · {index/fps:.3f} s</h3><p>Original</p><a href="{cid}/{role}_original.jpg"><img src="{cid}/{role}_original.jpg"></a><p>Landmarks novos</p><a href="{cid}/{role}_overlay.jpg"><img src="{cid}/{role}_overlay.jpg"></a></div>')
                    small=cv2.resize(overlay,(360,640));cv2.rectangle(small,(0,0),(360,45),(0,0,0),-1)
                    cv2.putText(small,f'{cid} {role} f={index}',(8,28),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1)
                    review_frames.append(small)
                contact=directory/'overview.jpg';cv2.imwrite(str(contact),np.hstack(review_frames),[cv2.IMWRITE_JPEG_QUALITY,92]);artifact_hashes[contact.relative_to(ROOT).as_posix()]=sha(contact)
                checklist.append({'case_id':cid,'first_frame':case['first_frame'],'middle_frame':case['middle_frame'],'last_frame':case['last_frame'],
                    'points_follow_body':'','side_or_point_swaps':'','occlusion_or_low_visibility':'','interval_matches_repetition':'','notes':'','review_status':'pending'})
                label=case['reference_primary_code'] or 'Referência correta'
                sections.append(f'<section><h2>{cid} — {html.escape(label)} — orientação {case["orientation"]}°</h2><p>Rótulo do dataset, não diagnóstico nem nova decisão de regra. Clique na imagem para ampliar.</p><div class="grid">'+''.join(columns)+'</div></section>')
                print('Prepared',cid,flush=True)
    finally:capture.release()
    document='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Dia 9 — inspeção visual local</title>
<style>body{font:16px sans-serif;background:#141820;color:#eef;margin:24px;line-height:1.5}section{border-top:1px solid #789;margin-top:36px}a{color:#8cf}img{width:100%;max-width:420px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}@media(max-width:800px){.grid{grid-template-columns:1fr}}.note{background:#263345;padding:16px}</style>
<h1>Dia 9 — tarefa 2: inspeção visual</h1><div class="note"><p>Material local de pesquisa. Revisão humana pendente. Nenhuma regra ou limiar alterado.</p>
<p>Acima: imagem original. Abaixo: nova estimativa MediaPipe Full em modo IMAGE, independente por imagem. Não é o tracking VIDEO dos relatórios anteriores nem projeção dos NPY antigos.</p>
<p>Verde: visibilidade ≥ 0,5. Laranja: visibilidade &lt; 0,5 (referência experimental). Os pontos 12/14/16/24 são ombro/cotovelo/punho/quadril direitos. O rótulo “direito” é anatômico, não o lado direito da tela. Sem espelhamento.</p>
<p>Observe pontos fora do corpo, troca de lado, oclusão e correspondência do trecho. Três imagens não comprovam comportamento durante toda a repetição. Tempos nominais = índice/30; seek conferido pelo backend, sem comprovação independente de PTS/offset.</p>
<p>Registre comentários em review_checklist.csv ou informe os IDs no chat. Os campos permanecem pendentes até revisão efetiva. Não é necessário julgar clinicamente o exercício.</p></div>'''+''.join(sections)+'</html>'
    (output/'index.html').write_text(document,encoding='utf-8')
    (output/'frame_observations.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    with (output/'review_checklist.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(checklist[0]));writer.writeheader();writer.writerows(checklist)
    for name in ['index.html','frame_observations.json','review_checklist.csv']:
        artifact_hashes[(output/name).relative_to(ROOT).as_posix()]=sha(output/name)
    report={'date':'2026-11-01','task':'day09_task02','selection_sha256':SELECTION_SHA,'generator_sha256':sha(Path(__file__)),
        'model_sha256':assets['model']['sha256'],'video_sha256':assets['video']['sha256'],
        'rgb_cases':len(checklist),'npy_only_cases':len(selection['cases'])-len(checklist),'sampled_frames':len(observations),
        'frames_with_pose':sum(o['pose_count']==1 for o in observations),'mode':'MediaPipe Tasks IMAGE Full CPU, independent samples',
        'versions':{p:importlib.metadata.version(p) for p in ['mediapipe','opencv-contrib-python','numpy']},
        'local_index':(output/'index.html').relative_to(ROOT).as_posix(),'artifact_sha256':artifact_hashes,
        'review_status':'pending_visual_review','new_rule_evaluation':False,'clinical_validation':False,
        'limitations':['No raw participant names exported','Only ten existing RGB development cases; two NPY cases have no video',
                       'New IMAGE landmarks, not original NPY overlays','Seek indices checked against decoder only; visual synchronization pending',
                       'Three snapshots do not replace full interval/curve analysis']}
    (ROOT/'reports/DAY_09_TASK_02_2026-11-01.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Finished',len(checklist),'cases,',len(observations),'frames',flush=True)


if __name__=='__main__':main()
