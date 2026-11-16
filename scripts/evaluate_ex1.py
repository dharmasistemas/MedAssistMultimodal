"""Dia 8: RGB development e NPY por grupo, sob protocolo/configuração congelados."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from medassistmultimodal.application.ex1_repetitions import Ex1Config,analyze_repetition
from medassistmultimodal.domain.evaluation import RuleObservation,stratified_metrics
from medassistmultimodal.infrastructure.rehab26_landmarks import LandmarkSequence,Representation
from medassistmultimodal.infrastructure.rehab26_metadata import load_metadata
from medassistmultimodal.infrastructure.video_pose import VideoReader,MediaPipePose,IntervalPoseSequence,safe_local_file

ROOT=Path(__file__).resolve().parents[1]
CODES={'bent_elbow_proxy':'ERR_BENT_ARM','low_elevation_proxy':'ERR_LOW_ABDUCTION'}


def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))


def sha(path):
    h=hashlib.sha256()
    with safe_local_file(ROOT/path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def write(path,payload):
    (ROOT/path).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def attach(result,rep,ref):
    result.pop('samples')
    codes=set(rep.additional_errors)|({rep.error_code} if rep.error_code else set())
    result.update(participant_ref=ref,orientation=rep.person_orientation,repetition_number=rep.repetition_number,
                  reference_positive={name:code in codes for name,code in CODES.items()})
    return result


def metrics(results):
    return {name:stratified_metrics(RuleObservation(r['participant_ref'],r['orientation'],
        r['reference_positive'][name],next(x['status'] for x in r['rules'] if x['name']==name)) for r in results) for name in CODES}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['rgb','landmarks'],required=True);args=parser.parse_args()
    freeze=read('data/manifests/day08_evaluation_freeze.json')
    for path,expected in freeze['sha256'].items():
        if sha(path)!=expected:raise ValueError('Congelamento divergente: '+path)
    plan=read('data/manifests/rehab26_ex1_evaluation_plan_v1.json')
    manifest=read('data/manifests/rehab26_landmarks_manifest.json')
    for path,expected in [(plan['local_mapping_path'],plan['local_mapping_sha256']),
                          (manifest['local_index_path'],manifest['local_index_sha256'])]:
        if sha(path)!=expected:raise ValueError('Índice/mapeamento divergente')
    for path,expected in plan['input_sha256'].items():
        if sha('data/raw/rehab26/metadata/v1/'+path)!=expected:raise ValueError('Metadado divergente')
    people={p['source_person']:p['participant_ref'] for p in read(plan['local_mapping_path'])['participants']}
    groups={p['participant_ref']:p['group'] for p in plan['participants']}
    meta=load_metadata(ROOT/'data/raw/rehab26/metadata/v1')
    config=Ex1Config(**read('configs/ex1_rules_v1.json'))
    started=time.perf_counter()
    common={'date':'2026-10-31','freeze_sha256':sha('data/manifests/day08_evaluation_freeze.json'),
            'camera':1,'config':asdict(config),'clinical_validation':False,'automatic_segmentation':False}
    if args.stage=='landmarks':
        members=read(manifest['local_index_path'])['files']
        for group in ['development','evaluation']:
            results=[];inputs=[]
            for m in members:
                ref=m['participant_ref']
                if groups[ref]!=group or m['representation']!='3d':continue
                expected=next(f['sha256'] for f in manifest['files'] if f['participant_ref']==ref and f['representation']=='3d')
                with LandmarkSequence(ROOT/m['path'],representation=Representation.THREE_D,expected_sha256=expected) as seq:
                    inputs.append({'participant_ref':ref,'sha256':expected})
                    for rep in meta.repetitions:
                        if rep.exercise_id==1 and people[rep.person]==ref:
                            result=analyze_repetition(seq,rep.first_frame,rep.last_frame,config=config,
                                evidence_ref=f'rehab26-v1/{ref}/ex1/cam1/3d#{rep.first_frame}-{rep.last_frame}')
                            results.append(attach(result,rep,ref))
                print(group,ref,len(results),flush=True)
            expected_count=plan['summary'][group]['repetitions']
            if len(results)!=expected_count:raise ValueError('Quantidade do grupo divergente')
            write(f'reports/EX1_NPY_{group.upper()}_2026-10-31.json',
                {**common,'source':'distributed_npy_world_3d','group':group,'inputs':inputs,
                 'metrics':metrics(results),'results':results,'repetitions':len(results),
                 'limitations':['Not evaluation of newly extracted RGB pipeline','Only camera 1 and 3D proxies',
                                'Reference intervals, not automatic segmentation','No global correctness classification']})
    else:
        assets=read('data/manifests/day07_rgb_assets.json');ref=assets['video']['participant_ref']
        if groups[ref]!='development':raise ValueError('RGB somente development')
        for asset in [assets['video'],assets['model']]:
            if sha(asset['path'])!=asset['sha256']:raise ValueError('Asset divergente')
        repetitions=sorted((rep for rep in meta.repetitions if rep.exercise_id==1 and people[rep.person]==ref),key=lambda r:r.first_frame)
        selected={}
        for rep in repetitions:selected.setdefault((rep.person_orientation,rep.correctness_score),rep)
        selected=sorted(selected.values(),key=lambda r:r.first_frame)
        by_start={rep.first_frame:rep for rep in selected};results=[];checklist=[]
        active=None;detector=None;poses={};decoded=0
        with VideoReader(ROOT/assets['video']['path']) as reader:
            if abs(reader.info.fps-config.fps)>.001:raise ValueError('FPS divergente')
            info=asdict(reader.info)
            try:
                for frame in reader.frames(0,reader.info.declared_frames-1):
                    decoded+=1
                    if frame.index in by_start:
                        active=by_start[frame.index];poses={};detector=MediaPipePose(ROOT/assets['model']['path'])
                    if active is not None:
                        poses[frame.index]=detector.detect(frame)
                        if frame.index==active.last_frame:
                            detector.__exit__();detector=None
                            seq=IntervalPoseSequence(poses,first=active.first_frame,last=active.last_frame)
                            result=analyze_repetition(seq,active.first_frame,active.last_frame,config=config,
                                evidence_ref=f'rehab26-v1/{ref}/ex1/cam1/rgb#{active.first_frame}-{active.last_frame}')
                            results.append(attach(result,active,ref))
                            checklist.append({'first_frame':active.first_frame,'middle_frame':(active.first_frame+active.last_frame)//2,
                                'last_frame':active.last_frame,'orientation':active.person_orientation,'review_status':'pending_visual_review'})
                            print('RGB repetition',len(results),'of',len(selected),flush=True);active=None
            finally:
                if detector is not None:detector.__exit__()
        if len(results)!=len(selected):raise ValueError('Seleção incompleta')
        member=next(m for m in read(manifest['local_index_path'])['files'] if m['participant_ref']==ref and m['representation']=='3d')
        expected=next(m['sha256'] for m in manifest['files'] if m['participant_ref']==ref and m['representation']=='3d')
        with LandmarkSequence(ROOT/member['path'],representation=Representation.THREE_D,expected_sha256=expected) as seq:npy_count=len(seq)
        tail_annotations=sum(rep.last_frame>=npy_count for rep in repetitions)
        write('reports/EX1_RGB_DEVELOPMENT_2026-10-31.json',
            {**common,'source':'new_rgb_tasks_world_3d','group':'development','participant_ref':ref,
             'video_sha256':assets['video']['sha256'],'model_sha256':assets['model']['sha256'],
             'video':info,'decoded_frames':decoded,'npy_frames':npy_count,'difference_frames':decoded-npy_count,
             'annotations_outside_npy':tail_annotations,'selected_repetitions':len(results),
             'inferred_frames':sum(r['expected_frames'] for r in results),'elapsed_seconds':time.perf_counter()-started,
             'selection':'first repetition for each orientation/correctness_score, fixed before inference',
             'metrics':metrics(results),'results':results,'visual_checklist':checklist,
             'tail_cause':'unconfirmed; length difference alone does not establish cause or offset',
             'limitations':['Single development participant, camera 1 only','Visual review pending, no independent synchronization proof',
                 'Detector restarted per selected interval; not continuous inference benchmark','No new RGB evaluation participant acquired']})
    print('Finished',args.stage,'seconds',round(time.perf_counter()-started,2),flush=True)


if __name__=='__main__':main()
