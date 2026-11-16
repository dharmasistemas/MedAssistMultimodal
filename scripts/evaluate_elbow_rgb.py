"""One exclusive development evaluation; references never enter process_video."""
import os
os.environ['MKL_THREADING_LAYER']='SEQUENTIAL'
os.environ['OMP_NUM_THREADS']='4'
os.environ['HF_HUB_OFFLINE']='1'

from pathlib import Path
from uuid import UUID
import argparse
import time

from medassistmultimodal.infrastructure.desktop_video import VideoWorkspace,ELBOW_CASES,assets,digest
from medassistmultimodal.infrastructure.desktop_summary import SummaryService
from medassistmultimodal.application.register_vitals import strict_json,encode_json

ROOT=Path(__file__).resolve().parents[1]
OUTPUT='data/interim/rehab26/elbow_rgb_v1'
SOURCE='data/interim/audio/desktop_workspaces_v1/e78e5b27-bd4d-4a62-95c7-231c918cb262/audio.sqlite3'


def exclusive(path,doc):
    with path.open('xb') as f:f.write(encode_json(doc))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:raise ValueError('Explicit --execute required')
    directory=ROOT/OUTPUT;directory.mkdir(parents=True,exist_ok=False)
    workspace=VideoWorkspace(ROOT);manifest=assets(ROOT)
    selection='data/manifests/day09_inspection_selection_v1.json'
    cases=strict_json((ROOT/selection).read_bytes())['cases']
    planned=[c for c in cases if c['case_id'] in ELBOW_CASES]
    assert len(planned)==10
    assert all(ELBOW_CASES[c['case_id']]==(c['first_frame'],c['last_frame']) and c['rgb_available'] for c in planned)
    dependencies=[SOURCE,selection,'configs/ex1_rules_v1.json',
        'src/medassistmultimodal/domain/elbow_deviation.py',
        'src/medassistmultimodal/application/register_video.py',
        'src/medassistmultimodal/infrastructure/desktop_video.py',
        'src/medassistmultimodal/infrastructure/video_pose.py',
        'src/medassistmultimodal/application/movement_inspection.py',
        'src/medassistmultimodal/domain/rehabilitation.py',__file__]
    hashes={str(Path(n).relative_to(ROOT) if Path(n).is_absolute() else n):digest(ROOT/n) for n in dependencies}
    exclusive(directory/'config.json',dict(date='2026-11-12',cases=list(ELBOW_CASES),assets=manifest,
        dependency_sha256=hashes,profile='ex1-world-v1/bent_elbow_proxy',
        parameters=dict(min_visibility=.5,min_coverage=.8,elbow_min_degrees=150,bent_fraction=.2),
        reference_role='evaluation_only',selection='known_development_not_holdout',
        retries=0,clinical_validation=False,automatic_segmentation=False))
    database=workspace.create_copy(SOURCE,'PAT-001')
    exclusive(directory/'workspace.json',dict(database=database,source=SOURCE))
    rows=[]
    for c in planned:
        case=c['case_id'];first,last=ELBOW_CASES[case];start=time.monotonic()
        print(case,'processing',first,last,flush=True)
        try:
            outcome=workspace.process_video(database,first,last,case_id=case)
            if not outcome.persisted:raise RuntimeError('Persistence failed; preserve prepared run, no inference retry')
            detail=workspace.reader.detail(database,UUID(outcome.session_id)).document
            analysis=detail['videos'][0]['evidence']['elbow_analysis']
            positive='ERR_BENT_ARM' in [c['reference_primary_code'],*c['reference_additional_codes']]
            status=analysis['status']
            classification=('abstention_positive' if positive else 'abstention_negative') if status=='not_analyzable' else (
                'TP' if positive and status=='deviation' else 'FP' if status=='deviation' else 'FN' if positive else 'TN')
            row=dict(case_id=case,session_id=outcome.session_id,run_id=outcome.run_id,
                analysis=analysis,reference_positive=positive,classification=classification,
                seconds=time.monotonic()-start,events=len(detail['events']),
                evidence=detail['videos'][0]['reference'],sha256=detail['videos'][0]['sha256'])
            exclusive(directory/f'{case}.json',row);rows.append(row)
            print(case,classification,'coverage',analysis['coverage'],flush=True)
        except Exception as exc:
            exclusive(directory/f'{case}_failure.json',dict(case_id=case,type=type(exc).__name__,message=str(exc)))
            raise
    counts={key:sum(r['classification']==key for r in rows) for key in ('TP','FP','FN','TN','abstention_positive','abstention_negative')}
    tp,fp,fn=counts['TP'],counts['FP'],counts['FN']
    divide=lambda a,b:a/b if b else None
    report=SummaryService(ROOT,reader=workspace.reader)
    snapshot=report.build(database,'PAT-001',[r['session_id'] for r in rows]);export=report.export(snapshot)
    after={n:digest(ROOT/n) for n in hashes}
    assert hashes==after,'Inputs changed during evaluation'
    summary=dict(database=database,rows=rows,counts=counts,
        analyzable_fraction=divide(sum(r['analysis']['status']!='not_analyzable' for r in rows),len(rows)),
        precision_analyzable=divide(tp,tp+fp),recall_analyzable=divide(tp,tp+fn),
        recall_all_reference_positives=divide(tp,tp+fn+counts['abstention_positive']),
        excluded_no_rgb=[c['case_id'] for c in cases if not c['rgb_available']],
        report_directory=str(export),source_hashes_unchanged=True,
        clinical_validation=False,selection='known_development',real_pose_runs=len(rows),
        inferred_frames=sum(r['analysis']['expected_frames'] for r in rows),cloud_calls=0,automated_reviews=0)
    exclusive(directory/'summary.json',summary)
    print('COMPLETE',database,counts,flush=True)


if __name__=='__main__':main()
