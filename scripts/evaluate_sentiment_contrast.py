"""Prepare six approved fictional texts offline; execution requires explicit cloud opt-in."""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import URLError

from medassistmultimodal.application.register_vitals import encode_json,strict_json
from medassistmultimodal.application.text_analysis_v3_prompt_v2 import SYSTEM_PROMPT_V3,analyze_text_v3
from medassistmultimodal.domain.text_analysis_v3 import evaluate_text_v3
from medassistmultimodal.providers.ollama_text_v3_prompt_v2 import OllamaTextProviderV3,TextRuntimeV3,check_runtime_input
from medassistmultimodal.providers.whisper_local import checked_path

ROOT=Path(__file__).resolve().parents[1]
REFERENCES='specs/sentiment_contrast_references_v1.json'
APPROVAL='reports/SENTIMENT_CONTRAST_APPROVAL_2026-11-12.json'
MODEL_RECORD='data/interim/audio/day14_cloud_120b_probe_v1/config.json'
OUTPUT='data/interim/audio/sentiment_contrast_gpt_oss_v1'
PLAN='configs/sentiment_contrast_evaluation_v1.json'
ORDER=tuple(f'S{i:02}' for i in range(1,7))
CLASSES=('positive','negative','mixed','neutral','unknown')
CODE_PATHS=('scripts/evaluate_sentiment_contrast.py',
    'src/medassistmultimodal/application/text_analysis_v3_prompt_v2.py',
    'src/medassistmultimodal/domain/text_analysis_v3.py',
    'src/medassistmultimodal/domain/text_context.py',
    'src/medassistmultimodal/domain/text_evaluation.py',
    'src/medassistmultimodal/providers/ollama_text_v3_prompt_v2.py',
    'src/medassistmultimodal/providers/ollama.py',
    'specs/text_analysis_v3.md','specs/text_analysis_v3.schema.json')


def digest(root,name):return hashlib.sha256(checked_path(name,root).read_bytes()).hexdigest()


def build_plan(root):
    refs=strict_json(checked_path(REFERENCES,root).read_bytes())
    approval=strict_json(checked_path(APPROVAL,root).read_bytes())
    if digest(root,REFERENCES)!=approval['sha256'][REFERENCES]:raise ValueError('Approved references changed')
    if refs['status']!='approved_by_project_user' or set(refs['cases'])!=set(ORDER) or refs['fictional'] is not True:
        raise ValueError('Six approved fictional inputs required')
    config=TextRuntimeV3()  # Same 1536-token, 180-second profile as the earlier prompt-v2 comparison.
    hashes={n:digest(root,n) for n in (*CODE_PATHS,REFERENCES,APPROVAL,MODEL_RECORD)}
    for key in ORDER:
        ref=refs['cases'][key];text=ref['input_text'];check_runtime_input(config,text)
        if checked_path(ref['input_file'],root).read_text(encoding='utf-8')!=text:raise ValueError('Input file differs')
        if digest(root,ref['input_file'])!=ref['input_sha256']:raise ValueError('Input hash differs')
        if not evaluate_text_v3(None,ref,input_text=text)['sentiment_scorable']:raise ValueError('Unapproved sentiment')
        hashes[ref['input_file']]=digest(root,ref['input_file'])
    manifest=strict_json(checked_path(MODEL_RECORD,root).read_bytes())['local_cloud_manifest_digest']
    if not isinstance(manifest,str) or len(manifest)!=64 or any(c not in '0123456789abcdef' for c in manifest):
        raise ValueError('Model digest required')
    plan=dict(version='sentiment-contrast-evaluation-plan-v1',prepared_on='2026-11-12',
        runtime=asdict(config),model=config.model,source=config.source,temperature=0,think='low',
        prompt_version='text-v3-prompt-v2',prompt_sha256=hashlib.sha256(SYSTEM_PROMPT_V3.encode()).hexdigest(),
        expected_model_manifest_digest=manifest,references=REFERENCES,approval=APPROVAL,order=list(ORDER),
        frozen_hashes=hashes,input_hashes={k:refs['cases'][k]['input_sha256'] for k in ORDER},
        class_counts=refs['class_counts'],attempts_planned=6,retries=0,automatic_model_switch=False,
        output=OUTPUT,cloud_fictional_text_only=True,inputs_are_transcriptions=False,
        clinical_validation=False,independent_validation=False,unknown_reference_included=False,
        preparation_model_requests=0)
    plan['plan_sha256']=hashlib.sha256(encode_json(plan)).hexdigest()
    return plan


def verify_plan(plan,root):
    bare=dict(plan);expected=bare.pop('plan_sha256')
    if hashlib.sha256(encode_json(bare)).hexdigest()!=expected:raise ValueError('Plan hash differs')
    if build_plan(root)!=plan:raise ValueError('Frozen plan/dependency differs')


def metadata(path):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise URLError('Redirect forbidden')
    opener=build_opener(ProxyHandler({}),NoRedirect())
    with opener.open('http://127.0.0.1:11434'+path,timeout=10) as stream:return json.load(stream)


def aggregate(rows):
    divide=lambda a,b:a/b if b else None
    valid=sum(r['metrics']['provider_valid'] for r in rows)
    correct=sum(r['metrics']['sentiment_correct'] is True for r in rows)
    confusion={k:{v:0 for v in (*CLASSES,'provider_failure')} for k in CLASSES}
    for row in rows:
        predicted=row['metrics']['sentiment_predicted'] if row['metrics']['provider_valid'] else 'provider_failure'
        confusion[row['reference_sentiment']][predicted]+=1
    terms={}
    for kind in ('term_occurrences','unique_terms'):
        tp,fp,fn=(sum(r['metrics'][kind][k] for r in rows) for k in ('tp','fp','fn'))
        terms[kind]=dict(tp=tp,fp=fp,fn=fn,precision=divide(tp,tp+fp),recall=divide(tp,tp+fn),f1=divide(2*tp,2*tp+fp+fn))
    per_class={}
    for label in CLASSES:
        subset=[r for r in rows if r['reference_sentiment']==label]
        per_class[label]=dict(attempts=len(subset),correct=sum(r['metrics']['sentiment_correct'] is True for r in subset),
            valid=sum(r['metrics']['provider_valid'] for r in subset))
    times=[r['provider'].get('seconds') for r in rows if r['provider'].get('seconds') is not None]
    usage={}
    for name in ('prompt_eval_count','prompt_eval_cached_count','eval_count'):
        values=[r['provider'].get('metrics',{}).get(name) for r in rows if isinstance(r['provider'].get('metrics'),dict)]
        available=[v for v in values if v is not None]
        usage[name]=dict(total_available=sum(available) if available else None,calls_with_metric=len(available))
    return dict(attempts=len(rows),not_attempted=6-len(rows),valid=valid,correct=correct,
        accuracy_all_attempts=divide(correct,len(rows)),accuracy_valid=divide(correct,valid),
        confusion=confusion,per_class=per_class,**terms,seconds=sum(times) if times else None,usage=usage,
        semantic_evidence_review='pending_human_review',clinical_validation=False,independent_validation=False)


def write(path,document):
    with path.open('xb') as stream:stream.write(encode_json(document))


def execute_plan(plan,root,*,allow_cloud=False,provider_factory=OllamaTextProviderV3,read_metadata=metadata):
    verify_plan(plan,root)
    if allow_cloud is not True:raise ValueError('Explicit --execute --allow-cloud and user approval required')
    output=checked_path(plan['output'],root)
    if output.exists():raise ValueError('Exclusive output already exists; no inference retry')
    tags=read_metadata('/api/tags')
    match=next((m for m in tags['models'] if m['name']==plan['model']),None)
    if match is None or match['digest']!=plan['expected_model_manifest_digest']:raise ValueError('Model manifest changed; no pull/fallback')
    output.mkdir(parents=True,exist_ok=False)
    injected=provider_factory is not OllamaTextProviderV3
    write(output/'run_config.json',dict(plan=plan,started_at_utc=datetime.now(timezone.utc).isoformat(),
        ollama_version=read_metadata('/api/version'),provider_injected=injected))
    refs=strict_json(checked_path(plan['references'],root).read_bytes())['cases']
    config=TextRuntimeV3(**plan['runtime']);provider=provider_factory(config=config,allow_requests=True);rows=[]
    for key in plan['order']:
        ref=refs[key];text=ref['input_text']
        result=analyze_text_v3(text,provider,source='mock' if injected else config.source,model=config.model)
        row=dict(case_id=key,input_text=text,input_sha256=ref['input_sha256'],reference_sentiment=ref['sentiment'],
            result=asdict(result),metrics=evaluate_text_v3(result.analysis,ref,input_text=text,provider_error=result.provider_error),
            provider=provider.last_call,execution_kind='injected_offline_test' if injected else 'ollama_cloud',
            semantic_evidence_review='pending_human_review')
        write(output/f'{key}.json',row);rows.append(row)
        print(key,'valid' if result.analysis else result.provider_error,flush=True)
        if provider.last_call.get('http_status') in (401,402,403,429):break
    verify_plan(plan,root)
    summary=aggregate(rows);summary.update(provider_injected=injected,cloud_used=not injected)
    write(output/'summary.json',summary)
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--allow-cloud',action='store_true');parser.add_argument('--plan',default=PLAN)
    args=parser.parse_args(argv);path=checked_path(args.plan,ROOT)
    if not path.is_relative_to(ROOT/'configs') or path.suffix!='.json':raise ValueError('Config JSON path required')
    if args.execute:
        summary=execute_plan(strict_json(path.read_bytes()),ROOT,allow_cloud=args.allow_cloud)
        print(encode_json(summary).decode())
    else:
        if args.allow_cloud:raise ValueError('--allow-cloud is not a preparation flag')
        plan=build_plan(ROOT);write(path,plan);print('Prepared six inputs; model requests: 0')


if __name__=='__main__':main()
