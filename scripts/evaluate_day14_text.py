"""One frozen Qwen run on five human reports, manual and ASR kept separate."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from urllib.request import build_opener,ProxyHandler

from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.application.analyze_report_text import analyze_report_text
from medassistmultimodal.providers.qwen_text import QwenTextAnalyzer,MODEL,SYSTEM_PROMPT
from medassistmultimodal.domain.text_evaluation import evaluate_text_result
from medassistmultimodal.providers.whisper_local import checked_path

ROOT=Path(__file__).resolve().parents[1]


def check(condition,message):
    if not condition:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/interim/audio/day14_text_evaluation_v1')
    args=parser.parse_args()
    output=checked_path(args.output,ROOT)
    check(output.is_relative_to(ROOT/'data/interim/audio'),'Output outside audio interim')
    receipt=json.loads((ROOT/'reports/DAY_14_TASKS_01_03_2026-11-06.json').read_bytes())
    for path,sha in receipt['sha256'].items():
        check(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,f'Frozen input/code changed: {path}')
    opener=build_opener(ProxyHandler({}))
    with opener.open('http://127.0.0.1:11434/api/tags',timeout=5) as stream:tags=json.load(stream)
    model=next(m for m in tags['models'] if m['name']==MODEL)
    expected=receipt['ollama_availability']['selected_model']['digest']
    check(model['digest']==expected,'Local model digest changed')
    corpus=json.loads((ROOT/'data/interim/audio/simulated_v1/collection_status.json').read_bytes())
    refs=json.loads((ROOT/'specs/text_analysis_references_v1.json').read_bytes())['cases']
    prepared=[]
    for case in ('A03','A04','A05','A08','A12'):
        c=next(c for c in corpus['clips'] if c['case_id']==case)
        check(c['human_verified'] and c['consent_ref'],'Missing human permission/reference')
        check(hashlib.sha256((ROOT/c['actual_audio_path']).read_bytes()).hexdigest()==c['audio_sha256'],'Audio changed')
        manual=(ROOT/c['actual_transcript_ref']).read_bytes()
        check(hashlib.sha256(manual).hexdigest()==c['reference_sha256'],'Reference changed')
        folder='day13_development_v1_final' if refs[case]['split']=='development' else 'day13_evaluation_v1'
        asrpath=ROOT/'data/interim/audio'/folder/f'{case}.json'
        old=json.loads((ROOT/('reports/DAY_13_TASK_03_2026-11-05.json' if refs[case]['split']=='development' else 'reports/DAY_13_TASK_04_2026-11-05.json')).read_bytes())
        check(hashlib.sha256(asrpath.read_bytes()).hexdigest()==old.get('artifacts',old.get('artifact_sha256',{}))[asrpath.name],'ASR artifact changed')
        asr=json.loads(asrpath.read_bytes())['run']['transcript']['text']
        for kind,text in (('manual',manual.decode('utf-8').strip()),('whisper',asr)):
            prepared.append((case,kind,text))
    output.mkdir(parents=True,exist_ok=False)
    config={'date':'2026-11-06','model':MODEL,'digest':model['digest'],
        'temperature':0,'max_tokens':768,'timeout_seconds':60,'no_retry':True,
        'order':[(c,k) for c,k,t in prepared],'prompt_sha256':hashlib.sha256(SYSTEM_PROMPT.encode('utf-8')).hexdigest(),
        'frozen_hashes':receipt['sha256'],'input_hashes':{c+'_'+k:hashlib.sha256(t.encode('utf-8')).hexdigest() for c,k,t in prepared}}
    (output/'run_config.json').write_bytes(encode_json(config))
    analyzer=QwenTextAnalyzer();original_generate=analyzer.provider.generate
    capture={}
    def recorded(request):
        try:
            response=original_generate(request)
            capture['raw_response']=asdict(response)
            return response
        except Exception as exc:
            capture['transport_error']={'type':type(exc).__name__,'message':str(exc)}
            raise
    analyzer.provider.generate=recorded
    rows=[]
    for case,kind,text in prepared:
        capture={};started=time.perf_counter()
        result=analyze_report_text(text,analyzer)
        row={'case_id':case,'input_kind':kind,'split':refs[case]['split'],'input_text':text,
            'input_sha256':config['input_hashes'][case+'_'+kind],'result':asdict(result),
            'metrics':evaluate_text_result(result,refs[case]),'seconds':time.perf_counter()-started,**capture}
        (output/f'{case}_{kind}.json').write_bytes(encode_json(row));rows.append(row)
        print(case,kind,'valid' if result.analysis else result.provider_error,round(row['seconds'],2),'s',flush=True)
    groups={}
    for split in ('development','evaluation'):
        for kind in ('manual','whisper'):
            selected=[r for r in rows if r['split']==split and r['input_kind']==kind]
            n=len(selected);valid=sum(r['metrics']['provider_valid'] for r in selected)
            values={'attempted':n,'valid':valid,'invalid_or_unavailable':n-valid,
                'sentiment_correct':sum(r['metrics']['sentiment_correct'] for r in selected),
                'sentiment_abstained':sum(r['metrics']['sentiment_abstained'] for r in selected),
                'all_contexts_match':sum(r['metrics']['all_rule_contexts_match'] for r in selected),
                'total_seconds':sum(r['seconds'] for r in selected)}
            values['sentiment_accuracy_all_attempts']=values['sentiment_correct']/n
            values['sentiment_accuracy_valid']=values['sentiment_correct']/valid if valid else None
            for metric in ('key_phrases','rule_context'):
                c={k:sum(r['metrics'][metric][k] for r in selected) for k in ('tp','fp','fn')}
                tp,fp,fn=c.values()
                values[metric]={**c,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
            groups[split+'_'+kind]=values
    summary={'date':'2026-11-06','groups':groups,'same_speaker_both_splits':True,
        'tts_processed':False,'cloud_used':False,'parameters_changed':False,'clinical_validation':False}
    (output/'summary.json').write_bytes(encode_json(summary))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
