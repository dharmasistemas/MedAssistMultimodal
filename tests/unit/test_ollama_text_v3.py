import io
import json
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from medassistmultimodal.application.text_analysis_v3 import SYSTEM_PROMPT_V3, analyze_text_v3
from medassistmultimodal.application.llm import LLMProviderInvalidResponseError, LLMProviderTimeoutError
from medassistmultimodal.providers.ollama_text_v3 import OllamaTextProviderV3,TextRuntimeV3


def envelope():
    return dict(model='gpt-oss:120b',done=True,done_reason='stop',prompt_eval_count=10,eval_count=20,
        message=dict(content=json.dumps(dict(sentiment='neutral',sentiment_evidence=[{'quote':'Não senti dor.'}],
                     terms=[dict(term='dor',quote='Não senti dor.')])),thinking='PRIVATE_REASONING'))


def adapter(raw=None,config=None):
    record={}
    def opener(request,timeout):
        record.update(payload=json.loads(request.data),timeout=timeout,url=request.full_url)
        return io.BytesIO(json.dumps(envelope() if raw is None else raw).encode())
    return OllamaTextProviderV3(config=config,allow_requests=True,opener=opener),record


def test_cloud_bridge_validates_envelope_then_domain_evidence_without_reasoning_trace():
    p,record=adapter();result=analyze_text_v3('Não senti dor.',p,source=p.config.source,model=p.config.model)
    assert result.analysis and result.analysis.terms[0].term=='dor'
    assert result.analysis.source=='ollama_cloud'
    assert record['payload']['think']=='low' and record['payload']['options']=={'temperature':0,'num_predict':1536}
    assert record['timeout']==180 and record['url']=='http://127.0.0.1:11434/api/chat'
    assert json.loads(record['payload']['messages'][1]['content'])=={'text':'Não senti dor.'}
    assert p.last_call['model_returned']=='gpt-oss:120b'
    assert p.last_call['metrics']['load_duration'] is None
    assert p.last_call['thinking_present'] and 'PRIVATE_REASONING' not in json.dumps(p.last_call)


def test_local_profile_cpu_context_and_provenance_are_explicit():
    raw=envelope();raw['model']='qwen2.5:7b-instruct'
    p,record=adapter(raw,TextRuntimeV3(backend='qwen_cpu',max_tokens=512))
    assert p.generate(system_prompt=SYSTEM_PROMPT_V3,text='Não senti dor.')
    assert record['payload']['options']['num_gpu']==0 and record['payload']['options']['num_ctx']==4096
    assert 'think' not in record['payload'] and p.last_call['source']=='ollama_local'


@pytest.mark.parametrize('fault',['model','missing_model','done','finish','length','content','metric_bool','metric_negative','null'])
def test_invalid_envelopes_rejected(fault):
    raw=envelope()
    if fault=='model':raw['model']='other-cloud'
    elif fault=='missing_model':raw.pop('model')
    elif fault=='done':raw['done']=False
    elif fault=='finish':raw.pop('done_reason')
    elif fault=='length':raw['done_reason']='length'
    elif fault=='content':raw['message']['content']=' '
    elif fault=='metric_bool':raw['eval_count']=True
    elif fault=='metric_negative':raw['eval_count']=-1
    elif fault=='null':raw=[]
    p,_=adapter(raw)
    with pytest.raises(LLMProviderInvalidResponseError):p.generate(system_prompt=SYSTEM_PROMPT_V3,text='dor')
    if fault=='length':assert p.last_call['error_category']=='truncated'
    if fault=='model':assert p.last_call['error_category']=='unexpected_model'


@pytest.mark.parametrize('body',['{bad','{"model":"a","model":"b"}','{"eval_count":NaN}'])
def test_strict_outer_json(body):
    p=OllamaTextProviderV3(allow_requests=True,opener=lambda *a,**kw:io.BytesIO(body.encode()))
    with pytest.raises(LLMProviderInvalidResponseError):p.generate(system_prompt=SYSTEM_PROMPT_V3,text='dor')


def test_disabled_requests_and_changed_endpoint_never_use_network():
    opener=Mock();p=OllamaTextProviderV3(opener=opener)
    with pytest.raises(ValueError):p.generate(system_prompt=SYSTEM_PROMPT_V3,text='dor')
    p.allow_requests=True;p.transport.base_url='https://elsewhere.example'
    with pytest.raises(ValueError):p.generate(system_prompt=SYSTEM_PROMPT_V3,text='dor')
    opener.assert_not_called()


@pytest.mark.parametrize('text',['','x'*4001,' '.join(['dor']*9)])
def test_invalid_capacity_before_network(text):
    opener=Mock();p=OllamaTextProviderV3(allow_requests=True,opener=opener)
    with pytest.raises(ValueError):p.generate(system_prompt=SYSTEM_PROMPT_V3,text=text)
    opener.assert_not_called()


def test_http_limit_and_timeout_are_recorded_without_retry():
    opener=Mock(side_effect=HTTPError('http://127.0.0.1:11434/api/chat',429,'limit',{},None))
    p=OllamaTextProviderV3(allow_requests=True,opener=opener)
    result=analyze_text_v3('Não senti dor.',p,source=p.config.source,model=p.config.model)
    assert result.analysis is None and result.mentions[0].context=='negated_current'
    assert p.last_call['http_status']==429 and opener.call_count==1
    opener.side_effect=TimeoutError()
    with pytest.raises(LLMProviderTimeoutError):p.generate(system_prompt=SYSTEM_PROMPT_V3,text='dor')
    assert p.last_call['error_category']=='timeout'


@pytest.mark.parametrize('config',[
    dict(backend='other'),dict(max_tokens=True),dict(max_tokens=0),dict(timeout_seconds=float('nan')),
    dict(timeout_seconds=True),dict(timeout_seconds=0),dict(timeout_seconds=601),
])
def test_invalid_runtime(config):
    with pytest.raises(ValueError):TextRuntimeV3(**config)


def test_local_conservative_budget_and_changed_prompt_rejected_before_network():
    opener=Mock();p=OllamaTextProviderV3(config=TextRuntimeV3(backend='qwen_cpu'),
                                      allow_requests=True,opener=opener)
    with pytest.raises(ValueError):p.generate(system_prompt=SYSTEM_PROMPT_V3,text='x'*4000)
    with pytest.raises(ValueError):p.generate(system_prompt='changed prompt',text='dor')
    opener.assert_not_called()


def test_literal_failure_remains_invalid_after_valid_transport_envelope():
    raw=envelope();raw['message']['content']=json.dumps(dict(sentiment='neutral',
        sentiment_evidence=[dict(quote='não senti dor.')],terms=[]))
    p,_=adapter(raw)
    result=analyze_text_v3('Não senti dor.',p,source=p.config.source,model=p.config.model)
    assert result.analysis is None and result.provider_error=='InvalidTextResponse'
    assert result.mentions[0].context=='negated_current'
