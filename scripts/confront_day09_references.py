"""Tarefa 4: confronta códigos específicos e critérios v1 em evidências existentes."""
import hashlib
import json
from pathlib import Path

from medassistmultimodal.infrastructure.rehab26_metadata import load_metadata
from medassistmultimodal.infrastructure.video_pose import safe_local_file

ROOT=Path(__file__).resolve().parents[1]
RULES={'bent_elbow_proxy':'ERR_BENT_ARM','low_elevation_proxy':'ERR_LOW_ABDUCTION'}


def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))


def sha(path):
    h=hashlib.sha256()
    with safe_local_file(ROOT/path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def criteria(summary,rule,config):
    name='right_elbow' if rule=='bent_elbow_proxy' else 'right_arm_trunk'
    if summary[name]['coverage']<config['min_coverage'] or summary[name]['valid_frames']==0:return 'not_analyzable'
    if rule=='bent_elbow_proxy':deviation=summary['elbow_below_limit']['fraction_valid']>=config['bent_fraction']
    else:deviation=summary[name]['max_degrees']<config['arm_peak_min_degrees']
    return 'deviation' if deviation else 'no_deviation'


def comparison(positive,status):
    if status=='not_analyzable':return 'abstention'
    if status=='not_available':return 'not_available'
    return ('TP' if positive else 'FP') if status=='deviation' else ('FN' if positive else 'TN')


def main():
    selection=read('data/manifests/day09_inspection_selection_v1.json')
    inspection=read('reports/DAY_09_TASK_03_2026-11-01.json')
    if sha('data/manifests/day09_inspection_selection_v1.json')!=inspection['selection_sha256']:raise ValueError('Seleção divergente')
    freeze=read('data/manifests/day08_evaluation_freeze.json')
    for path,expected in freeze['sha256'].items():
        if sha(path)!=expected:raise ValueError('Congelamento divergente')
    plan=read('data/manifests/rehab26_ex1_evaluation_plan_v1.json')
    if sha(plan['local_mapping_path'])!=plan['local_mapping_sha256']:raise ValueError('Mapeamento divergente')
    for name,expected in plan['input_sha256'].items():
        if sha('data/raw/rehab26/metadata/v1/'+name)!=expected:raise ValueError('Metadado divergente')
    for path,expected in inspection['local_artifact_sha256'].items():
        if sha(path)!=expected:raise ValueError('Artefato de inspeção divergente')
    review_path='data/interim/rehab26/day09_visuals_v1/review_checklist.csv'
    if sha(review_path)!=inspection['review_csv_sha256']:raise ValueError('Revisão mudou; registrar nova versão')
    dev={p['participant_ref'] for p in plan['participants'] if p['group']=='development'}
    people={p['source_person']:p['participant_ref'] for p in read(plan['local_mapping_path'])['participants']}
    metadata=load_metadata(ROOT/'data/raw/rehab26/metadata/v1')
    refs={(people[p.person],p.person_orientation,p.repetition_number):p for p in metadata.repetitions if p.exercise_id==1}
    config=read('configs/ex1_rules_v1.json');results=[]
    for case in selection['cases']:
        if case['participant_ref'] not in dev:raise ValueError('Caso fora de development')
        reference=refs[(case['participant_ref'],case['orientation'],case['repetition_number'])]
        if (reference.first_frame,reference.last_frame)!=(case['first_frame'],case['last_frame']):raise ValueError('Intervalo divergente')
        if reference.error_code!=case['reference_primary_code'] or list(reference.additional_errors)!=case['reference_additional_codes']:
            raise ValueError('Códigos divergentes')
        codes=set(reference.additional_errors)|({reference.error_code} if reference.error_code else set())
        observed=next(c for c in inspection['case_summaries'] if c['case_id']==case['case_id'])
        pairs={}
        for rule,code in RULES.items():
            positive=code in codes
            if positive!=case['reference_positive'][rule]:raise ValueError('Referência específica divergente')
            npy=criteria(observed['npy'],rule,config)
            if npy!=next(r['status'] for r in case['previous_v1_rules'] if r['name']==rule):raise ValueError('NPY não reproduz resultado anterior')
            rgb=criteria(observed['rgb_video'],rule,config) if observed['rgb_video'] else 'not_available'
            pairs[rule]={'reference_code':code,'positive':positive,'npy_v1_status':npy,'npy_comparison':comparison(positive,npy),
                         'rgb_v1_criteria_reconstructed':rgb,'rgb_comparison':comparison(positive,rgb)}
        jumps=[]
        if observed['rgb_video']:
            timeline=read(f'data/interim/rehab26/day09_movement_v1/{case["case_id"]}_RGB_VIDEO_timeline.json')
            candidates=[]
            for a,b in zip(timeline,timeline[1:]):
                av=a['measurements']['right_arm_trunk']['degrees'];bv=b['measurements']['right_arm_trunk']['degrees']
                if av is not None and bv is not None:candidates.append((abs(bv-av),a,b))
            if candidates:
                delta,a,b=max(candidates,key=lambda x:x[0])
                jumps=[{'measure':'right_arm_trunk','delta_degrees':delta,'frames':[a['frame'],b['frame']],
                        'visibility_before':a['visibility'],'visibility_after':b['visibility']}]
        results.append({'case_id':case['case_id'],'orientation':case['orientation'],'primary_code':reference.error_code,
                        'additional_codes':list(reference.additional_errors),'first_frame':reference.first_frame,'last_frame':reference.last_frame,
                        'comparison':pairs,'largest_rgb_consecutive_change':jumps,'human_snapshot_review':observed['human_snapshot_review']})
    inputs=['data/manifests/day09_inspection_selection_v1.json','reports/DAY_09_TASK_03_2026-11-01.json',
            'configs/ex1_rules_v1.json','data/raw/rehab26/metadata/v1/Error_types.csv','data/raw/rehab26/metadata/v1/Segmentation.csv',review_path]
    payload={'date':'2026-11-01','task':'day09_task04','group':'development','case_count':len(results),
        'input_sha256':{p:sha(p) for p in inputs},'generator_sha256':sha(Path(__file__)),
        'reference_definitions':{e.code:e.description for e in metadata.errors if e.exercise_id==1 and e.code in RULES.values()},
        'case_comparisons':results,'npy_previous_status_checks':len(results)*2,
        'user_confirmed':{'page_opens':True,'source_labels_understood':True,'comments_reproduced_correctly':True},
        'rules_changed':False,'new_pose_inference':False,'performance_evaluation':False,
        'limitations':['Purposive development sample, not independent evaluation','RGB statuses reconstructed from unchanged v1 criteria and existing summaries',
                       'Snapshot review is not full-interval or clinical validation','Codes checked against metadata; clinical adequacy of annotation not independently verified',
                       'No proposed replacement threshold or causal conclusion; task5 not started']}
    target=ROOT/'reports/DAY_09_TASK_04_2026-11-01.json'
    with target.open('x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print('Verified',len(results),'cases,',len(results)*2,'previous NPY statuses; no new inference or rule changes.')


if __name__=='__main__':main()
