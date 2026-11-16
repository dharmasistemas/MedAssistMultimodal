"""Executa primeira repetição anotada da gravação development adquirida no dia 7."""
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import statistics
import time

from medassistmultimodal.application.ex1_repetitions import Ex1Config, analyze_repetition
from medassistmultimodal.infrastructure.rehab26_landmarks import LandmarkSequence, Representation
from medassistmultimodal.infrastructure.rehab26_metadata import load_metadata
from medassistmultimodal.infrastructure.video_pose import VideoReader, MediaPipePose, IntervalPoseSequence, safe_local_file
from medassistmultimodal.domain.rehabilitation import CoordinateSpace, measure_rehabilitation

ROOT = Path(__file__).resolve().parents[1]


def main():
    def read(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))
    def sha(path):
        digest=hashlib.sha256()
        with safe_local_file(path).open('rb') as stream:
            for chunk in iter(lambda:stream.read(8*1024**2),b''):digest.update(chunk)
        return digest.hexdigest()
    assets=read('data/manifests/day07_rgb_assets.json');video=assets['video'];ref=video['participant_ref']
    plan=read('data/manifests/rehab26_ex1_evaluation_plan_v1.json')
    if not any(p['participant_ref']==ref and p['group']=='development' for p in plan['participants']):
        raise ValueError('Somente development autorizado neste script')
    mapping_path=ROOT/plan['local_mapping_path']
    if sha(mapping_path)!=plan['local_mapping_sha256']:raise ValueError('Mapeamento divergente')
    for name,expected in plan['input_sha256'].items():
        if sha(ROOT/'data/raw/rehab26/metadata/v1'/name)!=expected:raise ValueError('Metadado divergente')
    people=read(plan['local_mapping_path'])['participants']
    source=next(p['source_person'] for p in people if p['participant_ref']==ref)
    metadata=load_metadata(ROOT/'data/raw/rehab26/metadata/v1')
    rep=min((p for p in metadata.repetitions if p.exercise_id==1 and p.person==source),key=lambda p:p.first_frame)
    config=Ex1Config(**read('configs/ex1_rules_v1.json'))
    for asset in (assets['video'],assets['model']):
        if sha(ROOT/asset['path'])!=asset['sha256']:raise ValueError('Asset divergente')
    start=time.perf_counter();poses={};timestamps=[]
    with VideoReader(ROOT/video['path']) as reader:
        if abs(reader.info.fps-config.fps)>0.001:raise ValueError('FPS diverge do perfil Ex1 v1')
        info=asdict(reader.info)
        with MediaPipePose(ROOT/assets['model']['path']) as detector:
            for frame in reader.frames(rep.first_frame,rep.last_frame):
                poses[frame.index]=detector.detect(frame)
                timestamps.append({'frame':frame.index,'nominal_seconds':frame.nominal_seconds,
                                   'detector_timestamp_ms':frame.detector_timestamp_ms})
    elapsed=time.perf_counter()-start
    sequence=IntervalPoseSequence(poses,first=rep.first_frame,last=rep.last_frame)
    result=analyze_repetition(sequence,rep.first_frame,rep.last_frame,
        evidence_ref=f'rehab26-v1/{ref}/ex1/cam1/rgb#{rep.first_frame}-{rep.last_frame}',config=config)
    samples=result.pop('samples')
    # Comparação de duas estimativas MediaPipe, sem tratá-las como ground truth.
    manifest=read('data/manifests/rehab26_landmarks_manifest.json')
    if sha(ROOT/manifest['local_index_path'])!=manifest['local_index_sha256']:raise ValueError('Índice divergente')
    member=next(m for m in read(manifest['local_index_path'])['files'] if m['participant_ref']==ref and m['representation']=='3d')
    expected=next(m['sha256'] for m in manifest['files'] if m['participant_ref']==ref and m['representation']=='3d')
    differences={'right_elbow':[],'right_arm_trunk':[]}
    with LandmarkSequence(ROOT/member['path'],representation=Representation.THREE_D,expected_sha256=expected) as old:
        if rep.last_frame>=len(old):raise ValueError('Referência NPY curta')
        for sample in samples:
            previous=old.frame(sample['frame'])
            measures=measure_rehabilitation(dict(previous.landmarks),space=CoordinateSpace.WORLD_3D,min_visibility=config.min_visibility)
            for measure in measures[:2]:
                current=sample[measure.name]
                if current is not None and measure.value_degrees is not None:
                    differences[measure.name].append(abs(current-measure.value_degrees))
        npy_frames=len(old)
    comparison={name:{'paired_valid_frames':len(v),'mean_absolute_difference_degrees':statistics.mean(v) if v else None,
                       'max_absolute_difference_degrees':max(v) if v else None} for name,v in differences.items()}
    local=ROOT/'data/interim/rehab26/day07';local.mkdir(exist_ok=True)
    (local/'rgb_frame_measures.json').write_text(json.dumps({'samples':samples,'timestamps':timestamps},allow_nan=False),encoding='utf-8')
    report={'date':'2026-10-31','participant_ref':ref,'group':'development','camera':1,
        'selection':'first annotated repetition of selected development recording, before observing RGB results',
        'video':info,'npy_frames':npy_frames,'processed_frames':len(poses),'frames_with_world_pose':sum(bool(p.landmarks) for p in poses.values()),
        'pose_failures':{reason:sum(p.reason==reason for p in poses.values()) for reason in sorted({p.reason for p in poses.values() if p.reason})},
        'elapsed_seconds':elapsed,'processing_fps':len(poses)/elapsed,
        'versions':{name:importlib.metadata.version(name) for name in ['mediapipe','opencv-contrib-python','numpy']},
        'detector':{'api':'Tasks PoseLandmarker VIDEO','delegate':'CPU','model':'Full float16 version 1','num_poses':1,
                    'detection_threshold':.5,'presence_threshold':.5,'tracking_threshold':.5},
        'video_sha256':video['sha256'],'model_sha256':assets['model']['sha256'],
        'npy_sha256':expected,'config_sha256':sha(ROOT/'configs/ex1_rules_v1.json'),
        'result':result,'comparison':comparison,'evaluation_processed':False,
        'limitations':['One annotated repetition only; not full recording validation','CFR timestamps derived from index/FPS, not verified container PTS',
            'No visual manual synchronization approval; index-based correspondence only',
            'Different MediaPipe version/API/model from original NPY; angular differences are not accuracy',
            'No calibrated gravity; trunk unavailable; 2D legacy units remain unconfirmed',
            'No global correctness, automatic segmentation or persisted clinical alerts']}
    target=ROOT/'reports/REHAB26_RGB_PIPELINE_2026-10-31.json'
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['processed_frames','frames_with_world_pose','elapsed_seconds','comparison']}))


if __name__=='__main__':main()
