import pytest
from medassistmultimodal.domain.word_error_rate import word_error_rate,normalized_words


@pytest.mark.parametrize('ref,hyp,counts,wer',[
    ('não senti dor','não senti dor',(0,0,0),0),
    ('não senti dor','senti dor',(0,1,0),1/3),
    ('senti dor','senti muita dor',(0,0,1),.5),
    ('senti dor','senti calor',(1,0,0),.5),
    ('dor','muita forte dor',(0,0,2),2),
    ('a b c','a x',(1,1,0),2/3),
    ('dor','',(0,1,0),1),
    ('','dor',(0,0,1),None),
    ('','',(0,0,0),None),
    ('HOJE, não senti dor.','hoje não senti dor',(0,0,0),0)])
def test_known_alignments(ref,hyp,counts,wer):
    r=word_error_rate(ref,hyp)
    assert (r.substitutions,r.deletions,r.insertions)==counts and r.wer==wer
    assert r==word_error_rate(ref,hyp)
    assert tuple(e.reference for e in r.alignment if e.reference is not None)==normalized_words(ref)
    assert tuple(e.hypothesis for e in r.alignment if e.hypothesis is not None)==normalized_words(hyp)


def test_unicode_accents_negation_and_punctuation():
    assert normalized_words('NA\u0303O;  dor-no ombro!')==('não','dor','no','ombro')
    assert word_error_rate('não','nao').substitutions==1
    with pytest.raises(ValueError):normalized_words(None)


def test_weighted_aggregate_is_not_mean_of_percentages():
    a=word_error_rate('dor','calor');b=word_error_rate('a b c d e f g h i','a b c d e f g h i')
    assert (a.substitutions+b.substitutions)/(a.reference_words+b.reference_words)==.1
