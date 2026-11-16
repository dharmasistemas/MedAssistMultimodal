"""Prepare offline by default. Model requests require explicit execution flags."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import URLError

from medassistmultimodal.application.register_vitals import encode_json, strict_json
from medassistmultimodal.application.text_analysis_v3_prompt_v2 import SYSTEM_PROMPT_V3, analyze_text_v3
from medassistmultimodal.domain.text_analysis_v3 import evaluate_text_v3, validate_text_response_v3, InvalidTextResponse
from medassistmultimodal.providers.ollama_text_v3_prompt_v2 import OllamaTextProviderV3, TextRuntimeV3, check_runtime_input
from medassistmultimodal.providers.whisper_local import checked_path

ROOT=Path(__file__).resolve().parents[1]
REFERENCES='specs/text_analysis_references_v3.json'
APPROVAL='reports/TEXT_V3_REFERENCES_APPROVAL_2026-11-06.json'
CODE_PATHS=(
    'scripts/evaluate_text_v3_prompt_v2.py',
    'src/medassistmultimodal/providers/ollama_text_v3_prompt_v2.py',
    'src/medassistmultimodal/providers/ollama.py',
    'src/medassistmultimodal/application/text_analysis_v3_prompt_v2.py',
    'src/medassistmultimodal/domain/text_analysis_v3.py',
    'src/medassistmultimodal/domain/text_context.py',
    'src/medassistmultimodal/domain/text_evaluation.py',
    'specs/text_analysis_v3.md','specs/text_analysis_v3.schema.json',
)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build_plan(root, config):
    root=Path(root)
    approval=strict_json((root/APPROVAL).read_bytes())
    if digest(root/REFERENCES)!=approval['sha256'][REFERENCES]:raise ValueError('Approved reference changed')
    refs=strict_json((root/REFERENCES).read_bytes())
    if refs['status']!='approved_by_project_user':raise ValueError('Unapproved references')
    keys=[case+'_'+kind for case in ('A03','A04','A05','A08','A12') for kind in ('manual','whisper')]
    if set(refs['cases'])!=set(keys):raise ValueError('Exactly ten approved human entries required')
    hashes={p:digest(root/p) for p in (*CODE_PATHS,REFERENCES,APPROVAL)}
    snapshots_path='reports/DAY_14_TASK_04_CPU_V2_2026-11-06.json'
    hashes[snapshots_path]=digest(root/snapshots_path)
    snapshots=strict_json((root/snapshots_path).read_bytes())['sha256']
    for key in keys:
        ref=refs['cases'][key];check_runtime_input(config,ref['input_text'])
        if ref['review_status']!='approved' or ref['sentiment_review_status']!='approved':
            raise ValueError('Entry review missing')
        if hashlib.sha256(ref['input_text'].encode()).hexdigest()!=ref['input_sha256']:
            raise ValueError('Reference input hash mismatch')
        # Validate literal reference offsets and scoring eligibility before inference.
        if not evaluate_text_v3(None,ref,input_text=ref['input_text'])['sentiment_scorable']:
            raise ValueError('Sentiment reference not scorable')
        path=f'data/interim/audio/day14_text_evaluation_cpu_v2/{key}.json'
        if digest(root/path)!=snapshots[path]:raise ValueError('Original manual/ASR snapshot changed')
        if strict_json((root/path).read_bytes())['input_text']!=ref['input_text']:
            raise ValueError('Approved reference differs from original input')
        hashes[path]=snapshots[path]
    model_record=('data/interim/audio/day14_cloud_120b_probe_v1/config.json'
                  if config.backend=='gpt_oss_cloud' else
                  'data/interim/audio/day14_qwen_post_update_A03_v1/config.json')
    previous=strict_json((root/model_record).read_bytes())
    expected_digest=previous.get('local_cloud_manifest_digest',previous.get('digest'))
    if not isinstance(expected_digest,str) or len(expected_digest)!=64:raise ValueError('Model manifest digest missing')
    hashes[model_record]=digest(root/model_record)
    plan=dict(version='text-v3-prompt-v2-evaluation-plan-v1',prompt_version='text-v3-prompt-v2',prepared_on='2026-11-07',target_day='day16',
        runtime=asdict(config),model=config.model,source=config.source,
        expected_model_manifest_digest=expected_digest,
        prompt_sha256=hashlib.sha256(SYSTEM_PROMPT_V3.encode()).hexdigest(),
        references=REFERENCES,order=keys,
        input_hashes={key:refs['cases'][key]['input_sha256'] for key in keys},
        frozen_hashes=hashes,output=f'data/interim/audio/day16_text_v3_prompt_v2_{config.backend}_v1',
        attempts_planned=10,retries=0,automatic_model_switch=False,
        cloud_fictional_text_only=True,tts_included=False,corpus_known=True,
        independent_validation=False,all_sentiment_references_neutral=True,
        requests_executed_during_preparation=0)
    plan['plan_sha256']=hashlib.sha256(encode_json(plan)).hexdigest()
    return plan


def verify_plan(plan,root):
    bare=dict(plan);sha=bare.pop('plan_sha256')
    if hashlib.sha256(encode_json(bare)).hexdigest()!=sha:raise ValueError('Plan hash mismatch')
    expected=build_plan(root,TextRuntimeV3(**plan['runtime']))
    if expected!=plan:raise ValueError('Frozen plan/source/reference mismatch')


def aggregate(rows):
    groups={}
    for kind in ('manual','whisper'):
        subset=[row for row in rows if row['input_kind']==kind]
        n=len(subset);valid=sum(row['metrics']['provider_valid'] for row in subset)
        correct=sum(row['metrics']['sentiment_correct'] is True for row in subset)
        values=dict(attempts=n,valid=valid,invalid_or_unavailable=n-valid,sentiment_correct=correct,
                    sentiment_accuracy_all_attempts=correct/n if n else None,
                    sentiment_accuracy_valid=correct/valid if valid else None,
                    sentiment_unknown=sum(row['metrics']['sentiment_abstained'] for row in subset))
        for name in ('term_occurrences','unique_terms'):
            tp,fp,fn=(sum(row['metrics'][name][key] for row in subset) for key in ('tp','fp','fn'))
            values[name]=dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,
                             recall=tp/(tp+fn) if tp+fn else None,
                             f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
        groups[kind]=values
    return groups


def metadata(path):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise URLError('Redirect forbidden')
    opener=build_opener(ProxyHandler({}),NoRedirect())
    with opener.open('http://127.0.0.1:11434'+path,timeout=10) as stream:return json.load(stream)


def validation_telemetry(result,telemetry,text,config):
    telemetry=dict(telemetry)
    if result.provider_error=='InvalidTextResponse' and isinstance(telemetry.get('content'),str):
        try:
            validate_text_response_v3(telemetry['content'],text,source=config.source,model=config.model)
        except InvalidTextResponse as exc:
            # Validator messages are fixed codes/descriptions, not provider exception text.
            detail=str(exc);lower=detail.lower()
            telemetry['error_category']=('schema' if 'schema' in lower or 'json' in lower
                else 'evidence' if 'quote' in lower or 'term' in lower else 'schema')
            telemetry['validation_detail']=detail
    return telemetry


def provider_totals(rows):
    seconds=[r['provider']['seconds'] for r in rows if r['provider'].get('seconds') is not None]
    result=dict(seconds=sum(seconds) if seconds else None,calls_with_seconds=len(seconds),usage={})
    for key in ('prompt_eval_count','prompt_eval_cached_count','eval_count'):
        values=[(r['provider'].get('metrics') or {}).get(key) for r in rows]
        observed=[v for v in values if v is not None]
        result['usage'][key]=dict(total_available=sum(observed) if observed else None,
                                 calls_with_metric=len(observed),attempts=len(rows))
    return result


def execute_plan(plan,root,*,allow_cloud=False,provider_factory=OllamaTextProviderV3,read_metadata=metadata):
    verify_plan(plan,root)
    config=TextRuntimeV3(**plan['runtime'])
    if config.source=='ollama_cloud' and allow_cloud is not True:
        raise ValueError('Cloud execution requires explicit --allow-cloud and user approval')
    tags=read_metadata('/api/tags')
    model=next((m for m in tags['models'] if m['name']==config.model),None)
    if model is None or model['digest']!=plan['expected_model_manifest_digest']:
        raise ValueError('Selected model manifest absent/changed; no pull or fallback')
    output=checked_path(plan['output'],root)
    if not output.is_relative_to(Path(root)/'data/interim/audio'):raise ValueError('Unsafe output')
    output.mkdir(parents=True,exist_ok=False)
    (output/'run_config.json').write_bytes(encode_json(dict(plan=plan,
        started_at_utc=datetime.now(timezone.utc).isoformat(),ollama_version=read_metadata('/api/version'),
        cloud_execution_authorized=allow_cloud)))
    refs=strict_json((Path(root)/plan['references']).read_bytes())['cases']
    provider=provider_factory(config=config,allow_requests=True)
    rows=[]
    for key in plan['order']:
        ref=refs[key];text=ref['input_text']
        result=analyze_text_v3(text,provider,source=config.source,model=config.model)
        row=dict(case_id=ref['case_id'],input_kind=ref['input_kind'],input_sha256=ref['input_sha256'],
                 result=asdict(result),metrics=evaluate_text_v3(result.analysis,ref,input_text=text,
                 provider_error=result.provider_error),
                 provider=validation_telemetry(result,provider.last_call,text,config))
        (output/f'{key}.json').write_bytes(encode_json(row));rows.append(row)
        print(key,'valid' if result.analysis else result.provider_error,flush=True)
        if provider.last_call.get('http_status') in (401,402,403,429):break
    summary=dict(groups=aggregate(rows),attempts=len(rows),not_attempted=10-len(rows),
                 provider_totals=provider_totals(rows),
                 corpus_known=True,independent_validation=False,all_sentiment_references_neutral=True,
                 cloud_used=config.source=='ollama_cloud',clinical_validation=False)
    (output/'summary.json').write_bytes(encode_json(summary))
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--allow-cloud',action='store_true')
    parser.add_argument('--backend',choices=('gpt_oss_cloud','qwen_cpu'))
    parser.add_argument('--plan',default='configs/day16_text_evaluation_v3_prompt_v2.json')
    args=parser.parse_args(argv)
    path=checked_path(args.plan,ROOT)
    if not path.is_relative_to(ROOT/'configs') or path.suffix!='.json':raise ValueError('Plan must be JSON under configs')
    if args.execute:
        plan=strict_json(path.read_bytes())
        if args.backend is not None and args.backend!=plan['runtime']['backend']:
            raise ValueError('Requested backend differs from frozen plan')
        print(encode_json(execute_plan(plan,ROOT,allow_cloud=args.allow_cloud)).decode())
    else:
        if args.allow_cloud:raise ValueError('--allow-cloud is an execution flag, not needed to prepare')
        plan=build_plan(ROOT,TextRuntimeV3(backend=args.backend or 'gpt_oss_cloud'))
        with path.open('xb') as stream:stream.write(encode_json(plan))
        print('Prepared:',path.relative_to(ROOT),'| requests:0 | planned entries:10')


if __name__=='__main__':main()
