"""Uma execução development NPY completa; anotações somente depois da segmentação."""
from collections import Counter
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

from medassistmultimodal.application.movement_inspection import inspect_pose
from medassistmultimodal.domain.temporal_quality import OriginalAngle,OriginalFrame,QualityProfile,assess_angular_quality
from medassistmultimodal.domain.temporal_segmentation import SegmentationProfile,segment_repetitions
from medassistmultimodal.domain.temporal_evaluation import FrameInterval,evaluate_intervals
from medassistmultimodal.infrastructure.rehab26_landmarks import LandmarkSequence,Representation
from medassistmultimodal.infrastructure.rehab26_metadata import load_metadata
from medassistmultimodal.infrastructure.video_pose import safe_local_file

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))


def sha(path):
    h=hashlib.sha256()
    with safe_local_file(ROOT/path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def main():
    start=time.perf_counter()
    for name in ['data/manifests/day10_protocol_v1.json','data/manifests/day10_execution_freeze_v1.json','data/manifests/day08_evaluation_freeze.json']:
        for path,expected in read(name)['sha256'].items():
            if sha(path)!=expected:raise ValueError('Congelamento divergente: '+path)
    cfg=read('configs/day10_video_experiment_v1.json');protocol=read('data/manifests/day10_protocol_v1.json')
    plan=read('data/manifests/rehab26_ex1_evaluation_plan_v1.json');manifest=read('data/manifests/rehab26_landmarks_manifest.json')
    ref=cfg['participant_ref']
    if not any(p['participant_ref']==ref and p['group']=='development' for p in plan['participants']):raise ValueError('Fonte fora de development')
    for path,expected in [(manifest['local_index_path'],manifest['local_index_sha256']),(plan['local_mapping_path'],plan['local_mapping_sha256'])]:
        if sha(path)!=expected:raise ValueError('Índice/mapeamento divergente')
    for name,expected in protocol['metadata_input_sha256'].items():
        if sha('data/raw/rehab26/metadata/v1/'+name)!=expected:raise ValueError('Metadado divergente')
    for name in ['reports/DAY_10_TASK_02_2026-11-02.json','reports/DAY_10_TASK_03_2026-11-02.json']:
        for path,expected in read(name)['file_sha256'].items():
            if sha(path)!=expected:raise ValueError('Implementação anterior mudou')
    member=next(m for m in read(manifest['local_index_path'])['files'] if m['participant_ref']==ref and m['representation']=='3d')
    quality_profile=QualityProfile(fps=cfg['fps'],min_visibility=cfg['quality']['min_visibility'],max_change_degrees=cfg['quality']['max_consecutive_angle_change_degrees'])
    s=cfg['segmentation'];seg_profile=SegmentationProfile(fps=cfg['fps'],low_degrees=s['low_inclusive_degrees'],high_degrees=s['high_inclusive_degrees'],confirmation_frames=s['confirmation_frames'],min_duration_frames=s['min_duration_frames_inclusive'],max_duration_frames=s['max_duration_frames_inclusive'])
    if seg_profile.grace_frames!=s['return_confirmation_grace_frames']:raise ValueError('Margem divergente')
    originals=[]
    with LandmarkSequence(ROOT/member['path'],representation=Representation.THREE_D,expected_sha256=protocol['primary_source']['expected_npy_sha256']) as sequence:
        if len(sequence)!=cfg['expected_frames']:raise ValueError('Número de frames divergente')
        for index in range(len(sequence)):
            row=inspect_pose(sequence.frame(index),min_visibility=quality_profile.min_visibility)
            angles={name:OriginalAngle(row['measurements'][name]['degrees'],row['measurements'][name]['reason']) for name in ['right_elbow','right_arm_trunk']}
            originals.append(OriginalFrame(index,**angles,visibility=tuple((i,row['visibility'][str(i)]) for i in [12,14,16,24])))
    evidence=f'rehab26-v1/{ref}/ex1/cam1/distributed-world-3d'
    quality=assess_angular_quality(originals,evidence_ref=evidence,profile=quality_profile)
    segmented=segment_repetitions(quality,profile=seg_profile)
    # Somente agora carregar intervalos anotados para avaliação, nunca para o segmentador.
    people=read(plan['local_mapping_path'])['participants'];source=next(p['source_person'] for p in people if p['participant_ref']==ref)
    metadata=load_metadata(ROOT/'data/raw/rehab26/metadata/v1')
    reps=sorted((p for p in metadata.repetitions if p.exercise_id==1 and p.person==source),key=lambda p:p.first_frame)
    if len(reps)!=cfg['expected_reference_repetitions']:raise ValueError('Quantidade de referências divergente')
    refs=[];excluded=[];annotations=[]
    for i,p in enumerate(reps,1):
        ident=f'ref-{i:03}'
        item={'reference_id':ident,'first_frame':p.first_frame,'last_frame':p.last_frame,'orientation':p.person_orientation,'repetition_number':p.repetition_number}
        if p.last_frame>=len(originals):excluded.append(item);continue
        annotations.append(item);refs.append(FrameInterval(ident,p.first_frame,p.last_frame))
    predictions=[FrameInterval(f'cycle-{i:03}',c.first_frame,c.last_frame) for i,c in enumerate(segmented.cycles,1)]
    metrics=evaluate_intervals(refs,predictions,min_iou=cfg['evaluation']['min_temporal_iou_inclusive'],fps=cfg['fps'],boundary_tolerance_frames=cfg['evaluation']['boundary_reporting_tolerance_frames_inclusive'])
    def coverage(frames):
        frames=tuple(frames);n=len(frames);out={}
        for name in ['right_elbow','right_arm_trunk']:
            before=sum(getattr(f.original,name).degrees is not None for f in frames)
            after=sum(getattr(f,name).usable_degrees is not None for f in frames)
            out[name]={'frames':n,'original_valid':before,'usable':after,'rejected_extra':before-after,
                'original_coverage':before/n if n else None,'usable_coverage':after/n if n else None,
                'fraction_of_original_valid_rejected':(before-after)/before if before else None,
                'original_unavailable_reasons':dict(Counter(getattr(f.original,name).reason for f in frames if getattr(f.original,name).degrees is None)),
                'quality_states':dict(Counter(getattr(f,name).state.value for f in frames))}
        return out
    by_orientation={}
    matched={m['reference_id'] for m in metrics['matches']}
    for angle in sorted({a['orientation'] for a in annotations}):
        ann=[a for a in annotations if a['orientation']==angle]
        frames=[quality.frames[i] for a in ann for i in range(a['first_frame'],a['last_frame']+1)]
        tp=sum(a['reference_id'] in matched for a in ann)
        by_orientation[str(angle)]={'reference_count':len(ann),'matched_references':tp,'missed_references':len(ann)-tp,'reference_recall':tp/len(ann),'coverage':coverage(frames)}
    output=ROOT/'data/interim/rehab26/day10_experiment_v1';output.mkdir(exist_ok=False)
    def local(name,obj):
        path=output/name;path.write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');return path.relative_to(ROOT).as_posix()
    timeline=local('quality_timeline.json',[asdict(f) for f in quality.frames])
    notices=local('segmentation_notices.json',[asdict(n) for n in segmented.notices])
    cycles=[{'prediction_id':f'cycle-{i:03}',**asdict(c),'duration_frames':c.duration_frames,'first_seconds':c.first_frame/cfg['fps'],'last_seconds':c.last_frame/cfg['fps']} for i,c in enumerate(segmented.cycles,1)]
    local_cycles=local('cycles_and_references.json',{'cycles':cycles,'references':annotations,'matches':metrics['matches']})
    cov=coverage(quality.frames)
    report={'date':'2026-11-02','task':'day10_task04','source':'distributed_npy_world_3d','group':'development','participant_ref':ref,'camera':1,
        'input_frames':len(originals),'references_total':len(reps),'excluded_references':excluded,'metrics':metrics,
        'quality_coverage':cov,'by_orientation':by_orientation,'jump_pairs_by_measure':dict(Counter(j.measure for j in quality.jumps)),
        'segmentation_notice_counts':dict(Counter(n.reason for n in segmented.notices)),
        'interrupted_attempts':sum(n.candidate_first_frame is not None for n in segmented.notices),
        'quality_profiles':asdict(quality_profile),'segmentation_profile':asdict(seg_profile),'complete_cycles':cycles,
        'baseline_has_minimum_viability':bool(segmented.cycles) and cov['right_arm_trunk']['usable']>0,
        'clinical_validation':False,'exercise_correctness_evaluated':False,'independent_evaluation':False,'parameters_adjusted':False,
        'npy_sha256':protocol['primary_source']['expected_npy_sha256'],'execution_freeze_sha256':sha('data/manifests/day10_execution_freeze_v1.json'),
        'local_artifact_sha256':{f:sha(f) for f in [timeline,notices,local_cycles]},'versions':{'numpy':importlib.metadata.version('numpy')},
        'elapsed_seconds':time.perf_counter()-start,
        'limitations':['One previously inspected development participant/camera only','Distributed NPY performance is not new RGB pipeline performance',
            'No clinical deviation classification or alert validation','All eligible references retained including low quality','No precision by orientation inferred for unmatched predictions',
            'Minimum viability is not performance acceptance; no threshold retuning']}
    with (ROOT/'reports/DAY_10_TASK_04_2026-11-02.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'frames':len(originals),'cycles':len(predictions),'references':len(refs),'metrics':{k:metrics[k] for k in ['tp','fp','fn','precision','recall','f1']},'coverage':cov['right_arm_trunk']},ensure_ascii=False))


if __name__=='__main__':main()
