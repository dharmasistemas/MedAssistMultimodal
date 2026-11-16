"""Authorized three-text cloud diagnostic; does not replace the local adapter."""
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from medassistmultimodal.domain.text_context import detect_term_contexts
from medassistmultimodal.domain.text_evaluation import evaluate_text_result
from medassistmultimodal.providers.qwen_text_v2 import SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'gpt-oss:120b-cloud'


def validate_response(raw, text):
    """Same literal/unique evidence criteria as v2; honest cloud provenance."""
    if raw.get('model') not in (MODEL, 'gpt-oss:120b') or raw.get('done') is not True:
        raise ValueError('Unexpected model or incomplete response')
    if raw.get('done_reason') != 'stop':
        raise ValueError('Response did not finish normally')
    content = raw['message']['content']
    if not isinstance(content, str) or len(content) > 16000:
        raise ValueError('Invalid content length')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def reject(value): raise ValueError('Nonfinite JSON value')
    data = json.loads(content, object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(data, dict) or set(data) != {'sentiment', 'sentiment_evidence', 'key_phrases'}:
        raise ValueError('Unexpected schema')
    if data['sentiment'] not in ('positive', 'neutral', 'negative', 'mixed', 'unknown'):
        raise ValueError('Invalid sentiment')
    evidence = []; phrases = []
    for field, kind in (('sentiment_evidence', 'sentiment'), ('key_phrases', 'key_phrase')):
        values = data[field]
        if not isinstance(values, list) or len(values) > 8:
            raise ValueError('Invalid evidence list')
        seen = set()
        for item in values:
            if not isinstance(item, dict) or set(item) != {'quote'}:
                raise ValueError('Invalid evidence schema')
            quote = item['quote']
            if not isinstance(quote, str) or not quote.strip() or len(quote) > 300:
                raise ValueError('Invalid quote')
            start = text.find(quote)
            if start < 0 or text.find(quote, start + 1) >= 0:
                raise ValueError('Quote absent or ambiguous')
            span = (start, start + len(quote))
            if span in seen: raise ValueError('Duplicate evidence')
            seen.add(span)
            evidence.append(dict(kind=kind, start=span[0], end=span[1], quote=quote))
            if kind == 'key_phrase': phrases.append(quote)
    if data['sentiment'] != 'unknown' and not data['sentiment_evidence']:
        raise ValueError('Missing sentiment evidence')
    return dict(sentiment=data['sentiment'], key_phrases=phrases, evidence=evidence,
                source='ollama_cloud', model=raw['model'],
                input_sha256=hashlib.sha256(text.encode()).hexdigest())


def main():
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError('Redirect forbidden')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    def get(path):
        with opener.open('http://127.0.0.1:11434' + path, timeout=10) as stream:
            return json.load(stream)
    tags = get('/api/tags')
    model = next(m for m in tags['models'] if m['name'] == MODEL)
    refs_path = ROOT/'specs/text_analysis_references_v1.json'
    refs = json.loads(refs_path.read_bytes())['cases']
    baseline = ROOT/'data/interim/audio/day14_text_evaluation_cpu_v2'
    texts = {case: json.loads((baseline/f'{case}_manual.json').read_bytes())['input_text']
             for case in ('A03', 'A05', 'A08')}
    out = ROOT/'data/interim/audio/day14_cloud_120b_probe_v1'
    out.mkdir(exist_ok=False)
    config = dict(date='2026-11-06', started_at=datetime.now().astimezone().isoformat(),
                  model=MODEL, local_cloud_manifest_digest=model['digest'],
                  ollama_version=get('/api/version'), order=list(texts), input_kind='manual',
                  cloud_authorized_by_user=True, fictional_text_only=True,
                  temperature=0, num_predict=768, think='low', timeout_seconds=180,
                  retries=0, automatic_model_switch=False, forced_json_schema=False,
                  prompt_sha256=hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                  input_sha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in texts.items()},
                  references_sha256=hashlib.sha256(refs_path.read_bytes()).hexdigest(),
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  authorization='User reports coordinator permits any LLM; authorizes cloud tests on 2026-11-06')
    (out/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows = []
    for case, text in texts.items():
        payload = dict(model=MODEL, stream=False, think='low',
                       options=dict(temperature=0,num_predict=768),
                       messages=[dict(role='system',content=SYSTEM_PROMPT),
                                 dict(role='user',content=json.dumps({'text':text},ensure_ascii=False))])
        row = dict(case_id=case,input_text=text,input_kind='manual',request=payload)
        start = time.perf_counter(); analysis = None; error = None
        try:
            request = Request('http://127.0.0.1:11434/api/chat',
                              data=json.dumps(payload).encode(),
                              headers={'Content-Type':'application/json'},method='POST')
            with opener.open(request,timeout=180) as stream:
                row['http_status'] = stream.status
                raw = json.load(stream)
            # Retain final answer and usage, not internal reasoning traces.
            message = raw.get('message', {})
            row['thinking_present'] = bool(message.get('thinking'))
            message.pop('thinking', None)
            row['raw_response'] = raw
            analysis = validate_response(raw,text)
        except HTTPError as exc:
            row['http_status'] = exc.code; error = f'HTTP{exc.code}'
        except Exception as exc:
            error = type(exc).__name__ + ': ' + str(exc)
        row.update(seconds=time.perf_counter()-start,analysis=analysis,provider_error=error)
        mentions = detect_term_contexts(text)
        diagnostic = SimpleNamespace(analysis=None if analysis is None else SimpleNamespace(**analysis),
                                     provider_error=error,mentions=mentions)
        row['mentions'] = [asdict(m) for m in mentions]
        row['metrics'] = evaluate_text_result(diagnostic,refs[case])
        (out/f'{case}_manual.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        rows.append(row)
        print(case, 'valid' if analysis else error,round(row['seconds'],3),'s',flush=True)
        if row.get('http_status') in (401,402,403,429):
            print('Stopping: authentication/plan/limit response; no retry or purchase.',flush=True)
            break
    summary = dict(attempts=len(rows),valid=sum(r['analysis'] is not None for r in rows),
                   total_seconds=sum(r['seconds'] for r in rows),
                   sentiment_correct=sum(r['metrics']['sentiment_correct'] for r in rows),
                   cases=[dict(case_id=r['case_id'],valid=r['analysis'] is not None,
                               metrics=r['metrics'],seconds=r['seconds']) for r in rows],
                   corpus_known=True,independent_validation=False,production_adapter_changed=False)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__': main()
