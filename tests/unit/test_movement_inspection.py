from types import SimpleNamespace
import pytest
from medassistmultimodal.application.movement_inspection import inspect_pose,summarize_timeline
from medassistmultimodal.domain.rehabilitation import CoordinateSpace,Landmark


def sample(i,angle,reason=None):
    return {'frame':i,'measurements':{n:{'degrees':angle,'reason':reason} for n in ['right_elbow','right_arm_trunk']}}


def test_runs_do_not_bridge_missing_frames_or_count_equality():
    rows=[sample(10,140),sample(11,140),sample(12,None,'low_visibility'),sample(13,140),sample(14,150)]
    s=summarize_timeline(rows,first=10,last=14,fps=30.,elbow_limit=150.)
    assert s['right_elbow']['coverage']==.8
    assert s['elbow_below_limit']['runs']==[[10,11],[13,13]]
    assert s['elbow_below_limit']['fraction_valid']==.75
    assert s['elbow_below_limit']['longest_run_frame_exposure_seconds']==2/30


def test_all_missing_is_not_zero_angle():
    s=summarize_timeline([sample(0,None,'no_pose')],first=0,last=0,fps=30.,elbow_limit=150.)
    assert s['right_elbow']['min_degrees'] is None and s['right_elbow']['coverage']==0
    assert s['elbow_below_limit']['fraction_valid'] is None


def test_unfiltered_diagnostic_separate_from_usable_measure():
    pts={12:Landmark((0.,0.,0.),1.),14:Landmark((1.,0.,0.),.49),16:Landmark((2.,0.,0.),1.),24:Landmark((0.,1.,0.),1.)}
    f=SimpleNamespace(frame_index=0,coordinate_space=CoordinateSpace.WORLD_3D,landmarks=tuple(pts.items()),reason=None)
    s=inspect_pose(f,min_visibility=.5)['measurements']['right_elbow']
    assert s['degrees'] is None and s['reason']=='low_visibility'
    assert s['diagnostic_unfiltered_degrees']==180.


def test_only_consecutive_valid_samples_contribute_jump():
    s=summarize_timeline([sample(0,10),sample(1,None,'no_pose'),sample(2,170)],first=0,last=2,fps=30.,elbow_limit=150.)
    assert s['right_elbow']['max_consecutive_change_degrees'] is None


@pytest.mark.parametrize('indices',[[1],[0,0],[1,0]])
def test_incomplete_or_duplicate_timeline_rejected(indices):
    with pytest.raises(ValueError):summarize_timeline([sample(i,90) for i in indices],first=0,last=1,fps=30.,elbow_limit=150.)
