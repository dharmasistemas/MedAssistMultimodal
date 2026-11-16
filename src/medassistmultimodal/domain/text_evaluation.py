"""Exact textual-task metrics, separate from WER and alert interpretation."""
from collections import Counter


def exact_counts(predicted,expected):
    p,e=Counter(predicted),Counter(expected)
    tp=sum((p&e).values());fp=sum((p-e).values());fn=sum((e-p).values())
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def evaluate_text_result(result,reference):
    analysis=result.analysis
    phrases=() if analysis is None else set(p.lower() for p in analysis.key_phrases)
    return {'provider_valid':analysis is not None,'provider_error':result.provider_error,
        'sentiment_expected_provisional':reference['sentiment'],
        'sentiment_predicted':None if analysis is None else analysis.sentiment,
        'sentiment_correct':analysis is not None and analysis.sentiment==reference['sentiment'],
        'sentiment_abstained':analysis is not None and analysis.sentiment=='unknown',
        'key_phrases':exact_counts(phrases,set(reference['expected_key_phrases'])),
        'rule_context':exact_counts(((m.term,m.context) for m in result.mentions),
            ((m['term'],m['context']) for m in reference['mentions'])),
        'all_rule_contexts_match':[(m.term,m.context) for m in result.mentions]==[
            (m['term'],m['context']) for m in reference['mentions']]}
