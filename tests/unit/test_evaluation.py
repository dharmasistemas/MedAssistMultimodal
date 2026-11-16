import pytest
from medassistmultimodal.domain.evaluation import RuleObservation as R,binary_metrics,stratified_metrics


def test_confusion_and_abstentions_known():
    rows=[R('P-a',0,p,s) for p,s in [(True,'deviation'),(False,'deviation'),(False,'no_deviation'),
          (True,'no_deviation'),(True,'not_analyzable'),(False,'not_analyzable')]]
    m=binary_metrics(rows)
    assert [m[k] for k in ['tp','fp','tn','fn','abstained_positive','abstained_negative']]==[1]*6
    assert m['precision']==m['recall_analyzable']==m['f1_analyzable']==.5
    assert m['coverage']==m['positive_coverage']==m['negative_coverage']==2/3
    assert m['effective_positive_detection']==1/3


def test_empty_and_abstention_are_not_perfect():
    assert binary_metrics([])['coverage'] is None
    m=binary_metrics([R('P-a',0,True,'not_analyzable')])
    assert m['precision'] is None and m['recall_analyzable'] is None and m['f1_analyzable'] is None
    assert m['coverage']==0 and m['effective_positive_detection']==0


def test_no_positive_predictions():
    m=binary_metrics([R('P-a',0,True,'no_deviation')])
    assert m['precision'] is None and m['recall_analyzable']==0 and m['f1_analyzable']==0


def test_strata_and_generator():
    m=stratified_metrics(r for r in [R('P-a',0,True,'deviation'),R('P-b',90,False,'no_deviation')])
    assert m['overall']['eligible']==2
    assert m['by_participant']['P-a']['tp']==1 and m['by_orientation']['90']['tn']==1


@pytest.mark.parametrize('args',[('',0,True,'deviation'),('P-a',True,True,'deviation'),
    ('P-a',91,True,'deviation'),('P-a',0,1,'deviation'),('P-a',0,True,'unknown')])
def test_invalid_observations(args):
    with pytest.raises(ValueError):R(*args)
