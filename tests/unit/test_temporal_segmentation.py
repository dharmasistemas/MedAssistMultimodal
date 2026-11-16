from dataclasses import replace,FrozenInstanceError
import pytest
from medassistmultimodal.domain.temporal_quality import OriginalFrame,OriginalAngle,QualityProfile,assess_angular_quality
from medassistmultimodal.domain.temporal_segmentation import SegmentationProfile,segment_repetitions

VIS=((12,1.),(14,1.),(16,1.),(24,1.))


def quality(values,offset=0,neutral=True,elbows=None):
    rows=[OriginalFrame(offset+i,OriginalAngle(elbows[i] if elbows else 90.),
        OriginalAngle(v) if v is not None else OriginalAngle(None,'low_visibility'),VIS) for i,v in enumerate(values)]
    return assess_angular_quality(rows,evidence_ref='synthetic/cycles',
        profile=QualityProfile(version='synthetic-neutral' if neutral else 'day10-angular-quality-v1',max_change_degrees=180. if neutral else 30.))


def cycle(duration=15):
    # Início 3; retorno baixo em 3+duration-1; confirmação dois frames depois.
    return [20.]*3+[40.,60.,60.,60.]+[80.]*(duration-5)+[20.]*3


@pytest.mark.parametrize('duration',[15,450])
def test_inclusive_duration_and_confirmation_grace(duration):
    result=segment_repetitions(quality(cycle(duration),offset=100))
    assert len(result.cycles)==1
    c=result.cycles[0]
    assert c.first_frame==103 and c.last_frame==103+duration-1
    assert c.confirmed_at_frame==c.last_frame+2 and c.duration_frames==duration
    assert c.first_frame<=c.peak_frame<=c.last_frame


@pytest.mark.parametrize('duration,reason',[(14,'too_short'),(451,'duration_exceeded')])
def test_outside_duration_not_completed(duration,reason):
    result=segment_repetitions(quality(cycle(duration)))
    assert not result.cycles and any(n.reason==reason for n in result.notices)


def test_multiple_cycles_no_overlap_or_duplicate():
    values=cycle(20)+cycle(25)[3:]
    result=segment_repetitions(quality(values))
    assert len(result.cycles)==2
    assert result.cycles[0].last_frame<result.cycles[1].first_frame
    assert result.cycles[1].duration_frames==25


def test_threshold_equalities_low_high_and_start_above_low():
    values=[30.]*3+[30.1,60.,60.,60.]+[60.]*10+[30.]*3
    c=segment_repetitions(quality(values)).cycles[0]
    assert c.first_frame==3 and c.last_frame==17 and c.confirmed_at_frame==19


def test_single_high_spike_and_incomplete_high_confirmation():
    values=[20.]*3+[40.,60.,60.,59.,20.,20.,20.]
    result=segment_repetitions(quality(values))
    assert not result.cycles and any(n.reason=='never_reached_high' for n in result.notices)


def test_preactivation_cancel_counts_current_low_for_new_warmup():
    values=[20.]*3+[40.,50.,20.,20.,20.,40.,60.,60.,60.]+[80.]*10+[20.]*3
    result=segment_repetitions(quality(values))
    assert result.notices[0].reason=='never_reached_high'
    assert len(result.cycles)==1 and result.cycles[0].first_frame==8


def test_after_short_rejection_requires_new_warmup():
    values=cycle(14)+[20.,20.]+cycle(20)[3:]
    result=segment_repetitions(quality(values))
    assert len(result.cycles)==1 and result.cycles[0].duration_frames==20
    assert result.notices[0].reason=='too_short'


def test_return_confirmation_restarts_after_excursion():
    values=[20.]*3+[40.,60.,60.,60.]+[80.]*10+[20.,20.,40.,20.,20.,20.]
    c=segment_repetitions(quality(values)).cycles[0]
    assert c.last_frame==20 and c.confirmed_at_frame==22


def test_quality_gap_aborts_and_does_not_bridge():
    values=cycle(30);values[12]=None
    result=segment_repetitions(quality(values))
    assert not result.cycles and result.unavailable_frames==1
    notice=next(n for n in result.notices if n.reason=='quality_gap')
    assert notice.candidate_first_frame==3 and notice.original_quality_reason=='low_visibility'


def test_recover_only_after_new_low_confirmation():
    values=[20.]*3+[40.,60.,60.,60.,None]+[80.]*4+cycle(20)
    result=segment_repetitions(quality(values))
    assert len(result.cycles)==1 and result.cycles[0].first_frame==15


def test_unavailable_breaks_initial_warmup():
    result=segment_repetitions(quality([20.,20.,None,20.,20.,60.,60.,60.]))
    assert not result.cycles and not any(n.reason=='incomplete_eof' for n in result.notices)


def test_starts_high_or_low_without_cycle():
    assert not segment_repetitions(quality([80.]*30)).cycles
    assert not segment_repetitions(quality([20.]*30)).cycles
    assert segment_repetitions(quality([])).input_frames==0


@pytest.mark.parametrize('values',[[20.]*3+[40.],[20.]*3+[40.,60.,60.,60.],[20.]*3+[40.,60.,60.,60.]+[80.]*10+[20.,20.]])
def test_eof_never_completes_attempt(values):
    result=segment_repetitions(quality(values))
    assert not result.cycles and result.notices[-1].reason=='incomplete_eof'


def test_timeout_is_bounded_even_without_return():
    result=segment_repetitions(quality([20.]*3+[80.]*500))
    notices=[n for n in result.notices if n.reason=='duration_exceeded']
    assert len(notices)==1 and notices[0].frame_index==454


def test_full_quality_pipeline_rejects_suspect_but_elbow_is_independent():
    values=cycle(25)
    smooth=[20.]*3+[40.,60.,60.,60.]+[80.]*20+[60.,40.,20.,20.,20.]
    accepted=segment_repetitions(quality(smooth,neutral=False))
    assert len(accepted.cycles)==1
    suspect=segment_repetitions(quality(values,neutral=False))  # Retorno 80→20.
    assert not suspect.cycles and any(n.quality_flags==('angular_discontinuity',) for n in suspect.notices)
    elbows=[90.]*len(smooth);elbows[8]=0.
    assert len(segment_repetitions(quality(smooth,neutral=False,elbows=elbows)).cycles)==1


def test_input_indices_immutability_and_contradictory_usable_value():
    source=quality(cycle());result=segment_repetitions(source)
    with pytest.raises(FrozenInstanceError):result.cycles[0].first_frame=0
    duplicate=replace(source,frames=(source.frames[0],source.frames[0]))
    with pytest.raises(ValueError):segment_repetitions(duplicate)
    bad=replace(source.frames[0].right_arm_trunk,usable_degrees=99.)
    with pytest.raises(ValueError):segment_repetitions(replace(source,frames=(replace(source.frames[0],right_arm_trunk=bad),)))
    assert source.frames[0].right_arm_trunk.usable_degrees==20.


@pytest.mark.parametrize('kwargs',[{'fps':60.},{'fps':True},{'low_degrees':60.,'high_degrees':60.},
    {'high_degrees':float('nan')},{'confirmation_frames':True},{'min_duration_frames':0},
    {'min_duration_frames':451},{'version':''}])
def test_invalid_profiles(kwargs):
    with pytest.raises(ValueError):SegmentationProfile(**kwargs)
