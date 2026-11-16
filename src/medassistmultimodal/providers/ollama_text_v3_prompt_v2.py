"""Explicit prompt-v2 / contract-v3 text bridge over existing Ollama transport; no automatic requests."""
from dataclasses import dataclass
import json
import math
from time import perf_counter

from medassistmultimodal.application.llm import (
    LLMRequest, LLMProviderInvalidResponseError, LLMProviderTimeoutError, LLMProviderError,
)
from medassistmultimodal.application.text_analysis_v3_prompt_v2 import SYSTEM_PROMPT_V3
from medassistmultimodal.domain.text_analysis_v3 import check_input, TextCapacityError
from .ollama import OllamaProvider
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import URLError


@dataclass(frozen=True, slots=True)
class TextRuntimeV3:
    backend: str = 'gpt_oss_cloud'
    max_tokens: int = 1536
    timeout_seconds: float = 180.0

    def __post_init__(self):
        if self.backend not in ('gpt_oss_cloud', 'qwen_cpu'):
            raise ValueError('Only explicit cloud GPT-OSS or local CPU Qwen profiles supported')
        if type(self.max_tokens) is not int or not 256 <= self.max_tokens <= 4096:
            raise ValueError('Bounded integer output budget required')
        if (isinstance(self.timeout_seconds,bool) or not isinstance(self.timeout_seconds,(int,float))
                or not math.isfinite(self.timeout_seconds) or not 1 <= self.timeout_seconds <= 600):
            raise ValueError('Finite socket timeout between 1 and 600 seconds required')

    @property
    def model(self):
        return 'gpt-oss:120b-cloud' if self.backend=='gpt_oss_cloud' else 'qwen2.5:7b-instruct'

    @property
    def source(self):
        return 'ollama_cloud' if self.backend=='gpt_oss_cloud' else 'ollama_local'


class _V3Transport(OllamaProvider):
    def __init__(self,config,opener):
        super().__init__(base_url='http://127.0.0.1:11434',timeout_seconds=config.timeout_seconds,opener=opener)
        self.config=config;self.last_call={}

    def _build_payload(self,request):
        payload=super()._build_payload(request)
        if self.config.backend=='gpt_oss_cloud':payload['think']='low'
        else:payload['options'].update(num_ctx=4096,num_gpu=0)
        return payload

    def _raise_http_error(self,error):
        self.last_call['http_status']=error.code
        self.last_call['error_category']='authorization_or_limit' if error.code in (401,402,403,429) else 'http_error'
        super()._raise_http_error(error)

    def _parse_response(self,*,response_body,requested_model,latency_ms):
        def pairs(items):
            result={}
            for key,value in items:
                if key in result:raise ValueError('Duplicate response key')
                result[key]=value
            return result
        def reject(value):raise ValueError('Nonfinite response value')
        try:
            self.last_call['error_category']='envelope_json'
            if len(response_body)>262144:raise ValueError('Response too large')
            raw=json.loads(response_body,object_pairs_hook=pairs,parse_constant=reject)
            if not isinstance(raw,dict):raise ValueError('Response object required')
            aliases=(self.config.model,'gpt-oss:120b') if self.config.backend=='gpt_oss_cloud' else (self.config.model,)
            self.last_call['error_category']='unexpected_model'
            if raw.get('model') not in aliases:raise ValueError('Unexpected or missing model')
            self.last_call['error_category']='truncated' if raw.get('done_reason')=='length' else 'incomplete_response'
            if raw.get('done') is not True or raw.get('done_reason')!='stop':
                raise ValueError('Incomplete/truncated response')
            metrics={}
            self.last_call['error_category']='invalid_metrics'
            for key in ('total_duration','load_duration','prompt_eval_duration','eval_duration',
                        'prompt_eval_count','prompt_eval_cached_count','eval_count'):
                value=raw.get(key)
                if value is not None and (type(value) is not int or value<0):
                    raise ValueError('Invalid usage/duration metric')
                metrics[key]=value
            self.last_call['error_category']='invalid_content'
            response=super()._parse_response(response_body=response_body,requested_model=requested_model,
                                              latency_ms=latency_ms)
            self.last_call.update(model_returned=raw['model'],finish_reason='stop',
                content=response.content,metrics=metrics,thinking_present=bool(raw['message'].get('thinking')),
                error_category=None)
            return response
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            raise LLMProviderInvalidResponseError('Invalid v3 Ollama envelope') from exc


def check_runtime_input(config,text):
    check_input(text)
    user_prompt=json.dumps({'text':text},ensure_ascii=False)
    if config.backend=='qwen_cpu':
        if len(SYSTEM_PROMPT_V3.encode())+len(user_prompt.encode())+128+config.max_tokens>4096:
            raise TextCapacityError('Conservative local token budget exceeded')
    return user_prompt


class OllamaTextProviderV3:
    """Returns only final content. Caller applies v3 evidence validation afterward."""

    def __init__(self,*,config=None,allow_requests=False,opener=None):
        self.config=TextRuntimeV3() if config is None else config
        if not isinstance(self.config,TextRuntimeV3) or type(allow_requests) is not bool:
            raise ValueError('Typed config and explicit request permission required')
        self.allow_requests=allow_requests
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):raise URLError('Redirect forbidden')
        local=build_opener(ProxyHandler({}),NoRedirect())
        self.transport=_V3Transport(self.config,opener or local.open)

    @property
    def last_call(self):return dict(self.transport.last_call)

    def generate(self,*,system_prompt,text):
        user_prompt=check_runtime_input(self.config,text)
        if system_prompt!=SYSTEM_PROMPT_V3:raise ValueError('Frozen v3 system prompt required')
        if not self.allow_requests:raise ValueError('Requests disabled; preparation/offline mode')
        if self.transport.base_url!='http://127.0.0.1:11434':raise ValueError('Fixed loopback proxy required')
        self.transport.last_call=dict(source=self.config.source,model_requested=self.config.model,
                                      http_status=None,metrics=None)
        started=perf_counter()
        try:
            response=self.transport.generate(LLMRequest(system_prompt,user_prompt,self.config.model,
                                                       temperature=0,max_tokens=self.config.max_tokens))
            return response.content
        except LLMProviderTimeoutError:
            self.transport.last_call['error_category']='timeout'
            raise
        except LLMProviderError:
            if not self.transport.last_call.get('error_category'):
                self.transport.last_call['error_category']='transport_error'
            raise
        finally:
            self.transport.last_call['seconds']=perf_counter()-started
