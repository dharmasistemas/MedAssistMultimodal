import hashlib
import json
from unittest.mock import Mock

import pytest

from medassistmultimodal.domain.text_analysis_v3 import (
    validate_text_response_v3, evaluate_text_v3, InvalidTextResponse, TextCapacityError,
)
from medassistmultimodal.application.text_analysis_v3 import analyze_text_v3
from medassistmultimodal.application.llm import LLMProviderTimeoutError


def data(items=(), quote='Não senti dor.'):
    return dict(sentiment='neutral', sentiment_evidence=[{'quote':quote}], terms=list(items))


def parse(d, text='Não senti dor.'):
    return validate_text_response_v3(json.dumps(d), text, source='mock', model='offline')


def test_repeated_term_with_separate_quotes_and_intervals():
    text='Se eu sentir falta de ar, vou avisar. Agora não estou com falta de ar.'
    quotes=text.split('. ');quotes[0]+='.'
    result=parse(data([dict(term='falta de ar',quote=q) for q in quotes],quotes[0]),text)
    assert len(result.terms)==2
    assert result.terms[0].term_start != result.terms[1].term_start
    assert all(text[t.term_start:t.term_end]==t.literal_term for t in result.terms)


@pytest.mark.parametrize('text,term,quote',[
    ('dor e dor','dor','dor'), ('aaa','dor','aa'),
    ('Dor no peito.','dor','Dor'), ('dor e dor.','dor','dor e dor.'),
    ('Parei por dor.','dor','parei por dor.'),('Não senti dor.','calor','Não senti dor.'),
    ('Não senti dor.','dor','senti dores'),
])
def test_bad_or_ambiguous_term_evidence(text,term,quote):
    with pytest.raises(InvalidTextResponse):parse(data([dict(term=term,quote=quote)],text),text)


def test_unicode_case_and_longest_match():
    text='🙂 DOR NO PEITO.'
    result=parse(data([dict(term='dor no peito',quote=text)],text),text)
    term=result.terms[0]
    assert term.term_start==2 and term.term_end==14 and term.literal_term=='DOR NO PEITO'


def test_duplicate_same_occurrence_with_different_quotes_rejected():
    with pytest.raises(InvalidTextResponse):
        parse(data([dict(term='dor',quote='dor'),dict(term='dor',quote='Não senti dor.')]))


@pytest.mark.parametrize('fault',['extra','empty','too_many','duplicate','offset','sentiment','null'])
def test_strict_schema(fault):
    d=data()
    if fault=='extra':d['diagnosis']='x'
    elif fault=='empty':d['sentiment_evidence']=[]
    elif fault=='too_many':d['terms']=[dict(term='dor',quote='dor')]*9
    elif fault=='duplicate':d['sentiment_evidence']*=2
    elif fault=='offset':d['sentiment_evidence'][0]['start']=0
    elif fault=='sentiment':d['sentiment']=None
    elif fault=='null':d=None
    with pytest.raises(InvalidTextResponse):parse(d)


@pytest.mark.parametrize('raw',['```json\n{}\n```','{"sentiment":NaN}',
    '{"sentiment":"unknown","sentiment":"neutral"}'])
def test_invalid_json(raw):
    with pytest.raises(InvalidTextResponse):
        validate_text_response_v3(raw,'dor',source='mock',model='offline')


def test_unknown_empty_and_no_terms():
    assert parse(dict(sentiment='unknown',sentiment_evidence=[],terms=[])).sentiment=='unknown'


def test_over_capacity_rejected_before_provider():
    provider=Mock()
    with pytest.raises(TextCapacityError):analyze_text_v3(' '.join(['dor']*9),provider)
    provider.generate.assert_not_called()


@pytest.mark.parametrize('text',['',' ', 'x'*4001])
def test_bad_input_before_provider(text):
    provider=Mock()
    with pytest.raises(ValueError):analyze_text_v3(text,provider)
    provider.generate.assert_not_called()


def test_provider_failure_and_invalid_evidence_preserve_rules():
    provider=Mock()
    provider.generate.side_effect=LLMProviderTimeoutError('timeout')
    result=analyze_text_v3('Não senti dor.',provider)
    assert result.analysis is None and result.mentions[0].context=='negated_current'
    provider.generate.side_effect=None;provider.generate.return_value=json.dumps(data(quote='calor'))
    assert analyze_text_v3('Não senti dor.',provider).provider_error=='InvalidTextResponse'
    assert analyze_text_v3('Não senti dor.').provider_error=='provider_not_configured'


def test_metrics_occurrences_not_quote_length_and_sentiment_review_gate():
    text='Não senti dor.';result=parse(data([dict(term='dor',quote=text)]))
    ref=dict(input_sha256=hashlib.sha256(text.encode()).hexdigest(),
             terms=[dict(term='dor',term_start=10,term_end=13)],sentiment='neutral',
             review_status='draft',sentiment_review_status='pending')
    metrics=evaluate_text_v3(result,ref,input_text=text)
    assert metrics['term_occurrences']['tp']==1 and metrics['unique_terms']['tp']==1
    assert metrics['sentiment_correct'] is None and not metrics['sentiment_scorable']
    ref.update(review_status='approved',sentiment_review_status='approved')
    assert evaluate_text_v3(result,ref,input_text=text)['sentiment_correct'] is True
    assert evaluate_text_v3(None,ref,input_text=text)['term_occurrences']['fn']==1
    with pytest.raises(ValueError):evaluate_text_v3(result,ref,input_text=text+' ')


def test_omitted_repeated_occurrence_is_fn_even_if_unique_term_found():
    text='dor antes; dor depois'
    result=parse(data([dict(term='dor',quote='dor antes')],text),text)
    ref=dict(input_sha256=hashlib.sha256(text.encode()).hexdigest(),
             terms=[dict(term='dor',term_start=0,term_end=3),dict(term='dor',term_start=11,term_end=14)])
    metrics=evaluate_text_v3(result,ref,input_text=text)
    assert metrics['term_occurrences']['fn']==1 and metrics['unique_terms']['fn']==0
