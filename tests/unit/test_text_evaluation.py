from medassistmultimodal.domain.text_evaluation import exact_counts,evaluate_text_result
from medassistmultimodal.application.analyze_report_text import analyze_report_text


def test_multiset_counts_and_empty_denominators():
    assert exact_counts(['a','a','b'],['a','c'])==dict(tp=1,fp=2,fn=1,precision=1/3,recall=.5,f1=.4)
    r=exact_counts([],[])
    assert r['precision'] is r['recall'] is r['f1'] is None


def test_provider_missing_counted_without_losing_rules():
    result=analyze_report_text('Não senti dor.')
    ref={'sentiment':'neutral','expected_key_phrases':['dor'],
         'mentions':[{'term':'dor','context':'negated_current'}]}
    m=evaluate_text_result(result,ref)
    assert not m['provider_valid'] and not m['sentiment_correct']
    assert m['key_phrases']['fn']==1 and m['all_rule_contexts_match']
