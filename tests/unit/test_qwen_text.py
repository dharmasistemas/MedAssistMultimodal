from unittest.mock import patch
import json
import pytest
from medassistmultimodal.providers.qwen_text import QwenTextAnalyzer,MODEL
from medassistmultimodal.application.llm import LLMResponse,LLMProviderInvalidResponseError,LLMProviderTimeoutError
from medassistmultimodal.application.audio import AudioProviderUnavailableError,TextAnalysis
from medassistmultimodal.application.analyze_report_text import analyze_report_text


def response(data,**kwargs):
    return LLMResponse(json.dumps(data,ensure_ascii=False),'ollama',kwargs.get('model',MODEL),1,
                       finish_reason=kwargs.get('finish','stop'))


def valid():return {'sentiment':'negative','sentiment_evidence':[{'start':0,'end':9,'quote':'Senti dor'}],
                     'key_phrases':[{'start':6,'end':9,'quote':'dor'}]}


def test_local_request_strict_evidence_and_old_mock_compatibility():
    a=QwenTextAnalyzer()
    with patch.object(a.provider,'generate',return_value=response(valid())) as call:
        r=a.analyze('Senti dor.')
    req=call.call_args.args[0]
    assert req.model==MODEL and req.temperature==0 and req.max_tokens==768
    assert r.source=='ollama_qwen' and r.key_phrases==('dor',) and r.input_sha256
    assert all('Senti dor.'[e.start:e.end]==e.quote for e in r.evidence)
    assert TextAnalysis('neutral',()).source=='mock'


@pytest.mark.parametrize('fault',['extra','duplicate','quote','offset','bool','sentiment','empty_evidence',
    'markdown','length','model','too_many','duplicate_evidence','null'])
def test_invalid_model_output(fault):
    a=QwenTextAnalyzer();d=valid();kw={}
    if fault=='extra':d['diagnosis']='x'
    elif fault=='quote':d['key_phrases'][0]['quote']='calor'
    elif fault=='offset':d['key_phrases'][0]['end']=100
    elif fault=='bool':d['key_phrases'][0]['start']=True
    elif fault=='sentiment':d['sentiment']='diagnosis'
    elif fault=='empty_evidence':d['sentiment_evidence']=[]
    elif fault=='length':kw['finish']='length'
    elif fault=='model':kw['model']='gpt-oss:120b-cloud'
    elif fault=='too_many':d['key_phrases']*=9
    elif fault=='duplicate_evidence':d['key_phrases']*=2
    elif fault=='null':d=None
    r=response(d,**kw)
    if fault=='markdown':r=LLMResponse('```json\n{}\n```','ollama',MODEL,1)
    if fault=='duplicate':r=LLMResponse('{"sentiment":"unknown","sentiment":"neutral","sentiment_evidence":[],"key_phrases":[]}','ollama',MODEL,1)
    with patch.object(a.provider,'generate',return_value=r),pytest.raises(LLMProviderInvalidResponseError):a.analyze('Senti dor.')


def test_failure_and_invalid_json_never_remove_deterministic_mentions():
    a=QwenTextAnalyzer()
    for error in (LLMProviderTimeoutError('timeout'),LLMProviderInvalidResponseError('invalid')):
        with patch.object(a.provider,'generate',side_effect=error):
            result=analyze_report_text('Não senti dor.',a)
        assert result.analysis is None and result.provider_error
        assert result.mentions[0].context=='negated_current'


@pytest.mark.parametrize('text',['',' ', 'a'*4001])
def test_invalid_input_before_generation(text):
    a=QwenTextAnalyzer()
    with patch.object(a.provider,'generate') as call,pytest.raises(ValueError):a.analyze(text)
    call.assert_not_called()


def test_endpoint_cannot_be_changed_to_cloud():
    a=QwenTextAnalyzer();a.provider.base_url='https://ollama.com'
    with pytest.raises(ValueError):a.analyze('texto')


def test_unknown_abstention_is_valid():
    a=QwenTextAnalyzer()
    with patch.object(a.provider,'generate',return_value=response({'sentiment':'unknown','sentiment_evidence':[],'key_phrases':[]})):
        assert a.analyze('texto').sentiment=='unknown'
