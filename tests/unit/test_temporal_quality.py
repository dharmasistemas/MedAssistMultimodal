from dataclasses import FrozenInstanceError,asdict
import math
import pytest

from medassistmultimodal.domain.temporal_quality import (OriginalAngle as A,OriginalFrame as F,
    QualityProfile,QualityState as S,assess_angular_quality)

VIS=((12,1.),(14,1.),(16,1.),(24,1.))


def frame(index,elbow,arm=90.,**kwargs):
    angle=lambda value:A(value) if value is not None else A(None,'low_visibility')
    return F(index,angle(elbow),angle(arm),kwargs.get('visibility',VIS))


def assess(rows,**kwargs):return assess_angular_quality(rows,evidence_ref='synthetic/quality',**kwargs)


@pytest.mark.parametrize('values',[(0.,30.),(30.,0.),(90.,90.)])
def test_limit_inclusive_and_continuous_motion(values):
    result=assess([frame(i,v) for i,v in enumerate(values)])
    assert not result.jumps
    assert all(f.right_elbow.state is S.ACCEPTED for f in result.frames)


@pytest.mark.parametrize('values',[(0.,math.nextafter(30.,math.inf)),(math.nextafter(30.,math.inf),0.),(180.,0.)])
def test_above_limit_flags_both_endpoints_and_preserves_values(values):
    rows=[frame(i,v) for i,v in enumerate(values)];result=assess(rows)
    assert len(result.jumps)==1
    assert [f.right_elbow.original.degrees for f in result.frames]==list(values)
    assert all(f.right_elbow.state is S.SUSPECT and f.right_elbow.usable_degrees is None for f in result.frames)
    assert all(f.right_arm_trunk.state is S.ACCEPTED for f in result.frames)


def test_no_cascade_or_last_accepted_reference():
    result=assess([frame(0,0.),frame(1,60.),frame(2,80.)])
    assert [f.right_elbow.state for f in result.frames]==[S.SUSPECT,S.SUSPECT,S.ACCEPTED]
    assert result.frames[2].right_elbow.usable_degrees==80.


def test_all_original_pairs_preserved_at_shared_endpoint():
    result=assess([frame(0,0.),frame(1,100.),frame(2,0.)])
    assert len(result.jumps)==2
    assert len(result.frames[1].right_elbow.jump_pairs)==2
    assert result.frames[1].right_elbow.technical_flags==('angular_discontinuity',)


def test_missing_does_not_become_zero_or_bridge_gap():
    result=assess([frame(10,0.),frame(11,None),frame(12,180.)])
    assert not result.jumps
    missing=result.frames[1].right_elbow
    assert missing.state is S.UNAVAILABLE and missing.original.reason=='low_visibility'
    assert missing.usable_degrees is None and not missing.technical_flags
    assert result.frames[0].nominal_seconds==10/30


def test_measure_independence_and_both_can_be_flagged():
    result=assess([frame(0,20.,20.),frame(1,20.,80.)])
    assert all(f.right_elbow.state is S.ACCEPTED for f in result.frames)
    assert all(f.right_arm_trunk.state is S.SUSPECT for f in result.frames)
    both=assess([frame(0,0.,0.),frame(1,100.,100.)])
    assert len(both.jumps)==2


def test_empty_single_frame_and_input_immutability():
    assert assess([]).frames==()
    original=frame(99,150.);snapshot=asdict(original)
    result=assess(iter([original]))
    assert result.frames[0].right_elbow.state is S.ACCEPTED
    assert result.frames[0].original is original and asdict(original)==snapshot
    with pytest.raises(FrozenInstanceError):result.frames[0].original.frame_index=0


@pytest.mark.parametrize('indices',[(0,2),(1,1),(2,1)])
def test_skipped_duplicate_or_unsorted_indices_are_contract_errors(indices):
    with pytest.raises(ValueError):assess([frame(i,90.) for i in indices])


@pytest.mark.parametrize('value',[True,-1.,181.,math.nan,math.inf,10**1000])
def test_invalid_angle_is_not_silent_abstention(value):
    with pytest.raises(ValueError):A(value)


def test_reason_and_visibility_consistency():
    with pytest.raises(ValueError):A(None)
    with pytest.raises(ValueError):A(90.,'low_visibility')
    with pytest.raises(ValueError):assess([frame(0,90.,visibility=((12,1.),(14,.49),(16,1.),(24,1.)))])
    boundary=frame(0,90.,visibility=((12,.5),(14,.5),(16,.5),(24,.5)))
    assert assess([boundary]).frames[0].right_elbow.state is S.ACCEPTED
    absent=F(0,A(None,'missing_landmark'),A(90.),((12,1.),(14,1.),(16,None),(24,1.)))
    result=assess([absent]);assert result.frames[0].right_elbow.state is S.UNAVAILABLE
    assert result.frames[0].right_arm_trunk.state is S.ACCEPTED


@pytest.mark.parametrize('fps',[True,0.,29.97,60.,math.nan,math.inf])
def test_unsupported_fps_rejected(fps):
    with pytest.raises(ValueError):QualityProfile(fps=fps)


@pytest.mark.parametrize('limit',[0.,-1.,181.,True,math.nan])
def test_invalid_profile_limit(limit):
    with pytest.raises(ValueError):QualityProfile(max_change_degrees=limit)


def test_malformed_structures_and_evidence_rejected():
    with pytest.raises(ValueError):F(True,A(90.),A(90.),VIS)
    with pytest.raises(ValueError):F(0,A(90.),A(90.),VIS+((12,1.),))
    with pytest.raises(ValueError):F(0,A(90.),A(90.),((12,True),(14,1.),(16,1.),(24,1.)))
    with pytest.raises(ValueError):assess_angular_quality([],evidence_ref=' ')
    with pytest.raises(ValueError):assess([{}])
