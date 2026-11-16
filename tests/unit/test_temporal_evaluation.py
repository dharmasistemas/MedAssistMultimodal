import pytest
from medassistmultimodal.domain.temporal_evaluation import FrameInterval as I,temporal_iou,evaluate_intervals


def test_inclusive_endpoints_and_iou_equality():
    assert temporal_iou(I('r',10,10),I('p',10,10))==1
    assert temporal_iou(I('r',0,9),I('p',10,19))==0
    m=evaluate_intervals([I('r',0,9)],[I('p',0,4)])
    assert m['tp']==1 and m['matches'][0]['iou']==.5


def test_no_match_below_threshold_and_one_to_one():
    assert evaluate_intervals([I('r',0,9)],[I('p',0,3)])['fn']==1
    m=evaluate_intervals([I('r',0,9)],[I('p1',0,9),I('p2',0,9)])
    assert (m['tp'],m['fp'],m['fn'])==(1,1,0)
    assert len({x['prediction_id'] for x in m['matches']})==1


def test_priority_iou_then_absolute_start_error():
    m=evaluate_intervals([I('r',10,19)],[I('lower',10,15),I('best',10,19)])
    assert m['matches'][0]['prediction_id']=='best'
    m=evaluate_intervals([I('r',10,19)],[I('later',12,21),I('earlier',8,17)])
    assert m['matches'][0]['prediction_id']=='earlier'


def test_known_confusion_and_signed_errors():
    m=evaluate_intervals([I('r1',10,39),I('r2',100,129)],[I('p1',12,37),I('p2',200,220)])
    assert (m['tp'],m['fp'],m['fn'])==(1,1,1)
    assert m['precision']==m['recall']==m['f1']==.5
    assert m['matches'][0]['start_error_frames']==2 and m['matches'][0]['end_error_frames']==-2
    assert m['boundary_errors']['start']['mean_absolute_seconds']==2/30


def test_zero_denominators_not_perfect_and_no_exclusion_by_quality():
    empty=evaluate_intervals([],[])
    assert empty['precision'] is None and empty['recall'] is None and empty['f1'] is None
    m=evaluate_intervals([I('low_quality_ref',0,20)],[])
    assert m['fn']==1 and m['recall']==0 and m['f1']==0 and m['precision'] is None
    assert m['boundary_errors']['end']['max_absolute_frames'] is None


@pytest.mark.parametrize('first,last',[(-1,10),(10,9),(True,10)])
def test_invalid_interval(first,last):
    with pytest.raises(ValueError):I('x',first,last)


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):evaluate_intervals([I('r',0,10),I('r',20,30)],[])


@pytest.mark.parametrize('offset,within',[(15,True),(16,False)])
def test_boundary_tolerance_is_descriptive_and_inclusive(offset,within):
    m=evaluate_intervals([I('r',100,199)],[I('p',100+offset,199+offset)])
    assert m['tp']==1 and m['matches'][0]['both_boundaries_within_tolerance'] is within
