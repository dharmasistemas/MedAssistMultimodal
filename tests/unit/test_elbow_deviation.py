from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest

from medassistmultimodal.domain.elbow_deviation import detect_elbow_deviation
from medassistmultimodal.domain.temporal_quality import OriginalFrame, OriginalAngle
from medassistmultimodal.application.ex1_repetitions import Ex1Config
from medassistmultimodal.application.register_video import prepare_video, restore_video
from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.infrastructure.desktop_summary import SummaryService
from tests.unit.test_desktop_video import video_db
from tests.unit.test_structured_workspace import structured, request


def frames(values, first=897):
    return tuple(OriginalFrame(first+i, OriginalAngle(v) if v is not None else OriginalAngle(None,'no_pose'),
        OriginalAngle(90.), tuple((n,1.) for n in (12,14,16,24))) for i,v in enumerate(values))


@pytest.mark.parametrize('values,status,fraction', [
    ([149.,150.,150.,150.,150.], 'deviation', .2),
    ([150.]*5, 'no_deviation', 0.),
    ([149.]+[170.]*9, 'no_deviation', .1),
    ([149.]+[170.]*3+[None], 'deviation', .25),
    ([149.]+[170.]*2+[None]*2, 'not_analyzable', None),
    ([None]*5, 'not_analyzable', None),
])
def test_fixed_thresholds_and_denominators(values,status,fraction):
    result=detect_elbow_deviation(frames(values),897,896+len(values))
    assert result.status==status and result.bent_fraction==fraction
    assert result.coverage==sum(v is not None for v in values)/len(values)
    assert result.confidence is None and result.overall_correctness is None
    if status=='not_analyzable':assert result.evidence_frame is None


def test_missing_indices_reduce_coverage_and_visibility_equality():
    fs=frames([149.]*4)
    fs=tuple(replace(f,visibility=tuple((n,.5) for n in (12,14,16,24))) for f in fs)
    assert detect_elbow_deviation(fs,897,901).coverage==.8
    assert detect_elbow_deviation(fs,897,902).status=='not_analyzable'
    bad=replace(fs[0],visibility=((12,.49),(14,.5),(16,.5),(24,.5)))
    with pytest.raises(ValueError):detect_elbow_deviation((bad,),897,897)


@pytest.mark.parametrize('first,last',[(True,2),(-1,2),(3,2)])
def test_bad_interval(first,last):
    with pytest.raises(ValueError):detect_elbow_deviation((),first,last)


def test_duplicate_unsorted_outside_and_untyped_frames():
    fs=frames([150.,170.])
    for bad in ((fs[0],fs[0]),tuple(reversed(fs)),(fs[0],),({},)):
        with pytest.raises(ValueError):detect_elbow_deviation(bad,898,899)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1,181,True])
def test_invalid_angle(value):
    with pytest.raises(ValueError):OriginalAngle(value)


def prepare_v2(old,reference,values):
    source=json.loads(old.evidence)['source']
    source.update(first_frame=897,last_frame=896+len(values),camera=1,
        declared_frames=15149,coordinate_space='mediapipe_tasks_world_meters')
    return prepare_video(frames(values),source,run_id=uuid4(),processed_at=datetime.now(timezone.utc),
        evidence_ref=reference,analyze_elbow=True)


def test_profile_preserves_frozen_v1_numbers():
    result=detect_elbow_deviation(frames([170.]),897,897);config=Ex1Config()
    for field in ('min_visibility','min_coverage','elbow_min_degrees'):
        assert getattr(result,field)==getattr(config,field)
    assert result.fraction_threshold==config.bent_fraction


def test_detector_uses_original_angles_not_temporal_mask(video_db):
    _,_,old,_=video_db
    p=prepare_v2(old,'test.json',[100.,170.,170.,170.,170.])
    d=json.loads(p.evidence)
    assert d['elbow_analysis']['coverage']==1
    assert d['elbow_analysis']['status']=='deviation'
    assert d['summary']['coverage']['right_elbow'] < 1
    assert d['interval_basis']=='caller_supplied_not_automatic_segmentation'


@pytest.mark.parametrize('values,status,candidates',[
    ([140.]*5,'deviation',1),([170.]*5,'no_deviation',0),([None]*5,'not_analyzable',0)])
def test_v2_persistence_read_review_export_and_legacy(video_db,tmp_path,values,status,candidates):
    service,db,old,_=video_db
    ref=(service.writable_path(db).parent/f'new_{uuid4()}.json').relative_to(tmp_path).as_posix()
    prepared=prepare_v2(old,ref,values)
    doc=json.loads(prepared.evidence)
    assert doc['elbow_analysis']['status']==status
    assert len(doc['deviation_candidates'])==candidates
    assert restore_video(doc,ref)==prepared
    assert all(e.confidence is None and e.patient_id is None for e in prepared.events)
    assert sum('item=/deviation_candidates/' in e.evidence_ref for e in prepared.events)==candidates
    service._persist_video(db,prepared)
    detail=service.reader.detail(db,prepared.session.session_id).document
    assert detail['integrity']=='verified'
    # Existing v1 evidence is still verified without rewriting it or adding an analysis.
    legacy=service.reader.detail(db,old.session.session_id).document
    assert legacy['videos'][0]['evidence']['schema_version']=='rgb-video-evidence-v1'
    assert 'elbow_analysis' not in legacy['videos'][0]['evidence']
    reports=SummaryService(tmp_path,reader=service.reader)
    snapshot=reports.build(db,'PAT-001',[str(prepared.session.session_id)])
    assert 'ex1-world-v1/bent_elbow_proxy' in snapshot.document['text']
    reports.export(snapshot)
    if candidates:
        event=prepared.events[-1]
        service.review(db,prepared.session.session_id,request({'event_id':str(event.event_id)},scope='technical_simulation'),event.evidence_ref)
        assert service.reader.detail(db,prepared.session.session_id).document['review_histories'][str(event.event_id)]
    file=tmp_path/ref
    doc['elbow_analysis']['status']='no_deviation' if candidates else 'deviation'
    file.write_text(json.dumps(doc),encoding='utf-8')
    with pytest.raises(HistoryError,match='evidence_invalid'):service.reader.detail(db,prepared.session.session_id)


@pytest.mark.parametrize('field,value',[('camera',2),('coordinate_space','pixels'),('declared_frames',897)])
def test_v2_rejects_unsupported_source(video_db,field,value):
    _,_,old,_=video_db
    prepared=prepare_v2(old,'test.json',[140.]*5);doc=json.loads(prepared.evidence)
    doc['source'][field]=value
    with pytest.raises(ValueError):restore_video(doc,'test.json')
