"""Two authorized local probes with the frozen revised prompt; no new cloud calls."""
import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import URLError

from medassistmultimodal.application.llm import LLMRequest
from medassistmultimodal.application.text_analysis_v3_prompt_v2 import SYSTEM_PROMPT_V3, analyze_text_v3
from medassistmultimodal.application.register_vitals import encode_json, strict_json
from medassistmultimodal.domain.text_analysis_v3 import check_input, evaluate_text_v3
from medassistmultimodal.providers.ollama_text_v3_prompt_v2 import _V3Transport

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = 'data/interim/audio/qwen_prompt_v2_auto_probe_2026-11-08_v1'
KEYS = ('A03_whisper', 'A05_whisper')


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    backend: str = 'qwen_auto'
    model: str = 'qwen2.5:7b-instruct'
    source: str = 'ollama_local'
    timeout_seconds: float = 180.0
    max_tokens: int = 1536


class AutoTransport(_V3Transport):
    def _build_payload(self, request):
        payload = super()._build_payload(request)
        payload['options'].pop('num_gpu', None)
        return payload


def local_opener():
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): raise URLError('Redirect forbidden')
    return build_opener(ProxyHandler({}), NoRedirect()).open


class ProbeProvider:
    def __init__(self, *, allow_requests=False, opener=None):
        self.config = ProbeConfig()
        self.allow_requests = allow_requests
        self.transport = AutoTransport(self.config, opener or local_opener())

    @property
    def last_call(self): return dict(self.transport.last_call)

    def generate(self, *, system_prompt, text):
        check_input(text)
        if system_prompt != SYSTEM_PROMPT_V3 or not self.allow_requests:
            raise ValueError('Frozen prompt and explicit execution required')
        if self.transport.base_url != 'http://127.0.0.1:11434': raise ValueError('Loopback required')
        self.transport.last_call = dict(model_requested=self.config.model, source=self.config.source)
        started = perf_counter()
        try:
            return self.transport.generate(LLMRequest(system_prompt, json.dumps({'text': text}, ensure_ascii=False),
                self.config.model, temperature=0, max_tokens=self.config.max_tokens)).content
        finally:
            self.transport.last_call['seconds'] = perf_counter()-started


def metadata(path):
    with local_opener()('http://127.0.0.1:11434'+path, timeout=10) as stream:
        return json.load(stream)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args(argv)
    references='specs/text_analysis_references_v3.json'
    approval='reports/TEXT_V3_REFERENCES_APPROVAL_2026-11-06.json'
    digest=lambda p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    if digest(references)!=strict_json((ROOT/approval).read_bytes())['sha256'][references]:
        raise ValueError('Approved references changed')
    refs=strict_json((ROOT/references).read_bytes())['cases']
    config=ProbeConfig()
    old_model='data/interim/audio/day14_qwen_post_update_A03_v1/config.json'
    expected=strict_json((ROOT/old_model).read_bytes())['digest']
    dependencies=[references,approval,old_model,'scripts/probe_qwen_prompt_v2.py',
        'src/medassistmultimodal/application/text_analysis_v3_prompt_v2.py',
        'src/medassistmultimodal/providers/ollama_text_v3_prompt_v2.py',
        'src/medassistmultimodal/providers/ollama.py','src/medassistmultimodal/domain/text_analysis_v3.py',
        'src/medassistmultimodal/domain/text_context.py','src/medassistmultimodal/domain/text_evaluation.py']
    comparisons={}
    for key in KEYS:
        check_input(refs[key]['input_text'])
        if hashlib.sha256(refs[key]['input_text'].encode()).hexdigest()!=refs[key]['input_sha256']:
            raise ValueError('Input reference hash mismatch')
        previous=f'data/interim/audio/day16_text_v3_prompt_v2_gpt_oss_cloud_v1/{key}.json'
        dependencies.append(previous);comparisons[key]=strict_json((ROOT/previous).read_bytes())
        if comparisons[key]['input_sha256']!=refs[key]['input_sha256']:raise ValueError('Comparison input differs')
    plan=dict(date='2026-11-08',runtime=asdict(config),num_ctx=4096,gpu_selection='automatic_no_num_gpu_override',
        order=KEYS,model_digest=expected,prompt_sha256=hashlib.sha256(SYSTEM_PROMPT_V3.encode()).hexdigest(),
        prompt_utf8_bytes=len(SYSTEM_PROMPT_V3.encode()),output_budget=1536,cloud_calls=0,retries=0,
        context_note='4096-token runtime context; no tokenizer preflight; UTF8 bytes are not token counts',
        corpus_known=True,independent_validation=False,sha256={p:digest(p) for p in dependencies})
    if not args.execute:
        print(encode_json(plan).decode());return
    tags=metadata('/api/tags')
    if not any(m['name']==config.model and m['digest']==expected for m in tags['models']):
        raise ValueError('Expected local model unavailable; no pull or model switch')
    out=ROOT/OUTPUT;out.mkdir(exist_ok=False)
    (out/'config.json').write_bytes(encode_json(dict(plan=plan,ollama_version=metadata('/api/version'),
        started_at=datetime.now(timezone.utc).isoformat())))
    provider=ProbeProvider(allow_requests=True);results=[]
    for key in KEYS:
        ref=refs[key];text=ref['input_text']
        result=analyze_text_v3(text,provider,source=config.source,model=config.model)
        metrics=evaluate_text_v3(result.analysis,ref,input_text=text,provider_error=result.provider_error)
        try:
            loaded=[{k:m.get(k) for k in ('name','digest','size_vram','context_length')}
                for m in metadata('/api/ps').get('models',[]) if m.get('name')==config.model]
        except Exception:loaded=None
        row=dict(key=key,input_sha256=ref['input_sha256'],result=asdict(result),metrics=metrics,
            provider=provider.last_call,loaded_after_request=loaded,
            previous_gpt_oss_metrics=comparisons[key]['metrics'],
            previous_gpt_oss_seconds=comparisons[key]['provider']['seconds'])
        (out/f'{key}.json').write_bytes(encode_json(row));results.append(row)
        print(key,'valid' if result.analysis else result.provider_error,flush=True)
    for p,sha in plan['sha256'].items():
        if digest(p)!=sha:raise ValueError('Frozen dependency changed during test')
    summary=dict(attempts=len(results),valid=sum(r['result']['analysis'] is not None for r in results),
        seconds=sum(r['provider']['seconds'] for r in results),cloud_calls=0,retries=0,
        adopted=False,clinical_validation=False,rows=[dict(key=r['key'],metrics=r['metrics'],
        previous_gpt_oss_metrics=r['previous_gpt_oss_metrics'],seconds=r['provider']['seconds']) for r in results])
    (out/'summary.json').write_bytes(encode_json(summary));print(encode_json(summary).decode())


if __name__=='__main__':main()
