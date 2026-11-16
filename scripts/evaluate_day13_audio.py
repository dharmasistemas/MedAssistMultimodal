"""Fixed human evaluation A08/A12 and WER of five local, human-reviewed clips."""
import os
os.environ['MKL_THREADING_LAYER']='SEQUENTIAL'
os.environ['OMP_NUM_THREADS']='4'
os.environ['HF_HUB_OFFLINE']='1'
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.providers.whisper_local import LocalWhisperTranscriber,checked_path
from medassistmultimodal.domain.word_error_rate import word_error_rate

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/interim/audio/day13_evaluation_v1')
    args=parser.parse_args()
    output=checked_path(args.output,ROOT)
    if not output.is_relative_to(ROOT/'data/interim/audio'):raise ValueError('Output outside audio interim')
    previous=json.loads((ROOT/'reports/DAY_13_TASK_03_2026-11-05.json').read_bytes())
    for path,sha in previous['sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError('Previous code changed')
    dev=ROOT/'data/interim/audio/day13_development_v1_final'
    for name,sha in previous['artifacts'].items():
        if hashlib.sha256((dev/name).read_bytes()).hexdigest()!=sha:raise ValueError('Development evidence changed')
    corpus=json.loads((ROOT/'data/interim/audio/simulated_v1/collection_status.json').read_bytes())
    config=json.loads((dev/'run_config.json').read_bytes())
    manifest=json.loads((ROOT/'data/manifests/day13_whisper_assets.json').read_bytes())
    for f in manifest['model']['files']:
        if hashlib.sha256((ROOT/manifest['model']['local_path']/f['name']).read_bytes()).hexdigest()!=f['sha256']:
            raise ValueError('Model hash mismatch')
    output.mkdir(parents=True,exist_ok=False)
    (output/'run_config.json').write_bytes(encode_json({**config,'cases':['A08','A12'],
        'normalization':'nfc-lower-punctuation-as-space-whitespace-v1','alignment_tie_order':['match','substitution','deletion','insertion']}))
    provider=LocalWhisperTranscriber(root=ROOT,model_directory=manifest['model']['local_path'])
    runs={}
    for case in ('A08','A12'):
        c=next(c for c in corpus['clips'] if c['case_id']==case)
        if not c['human_verified'] or not c['consent_ref']:raise ValueError('Missing human verification/authorization')
        if hashlib.sha256((ROOT/c['actual_audio_path']).read_bytes()).hexdigest()!=c['audio_sha256']:raise ValueError('Source hash mismatch')
        r=provider.transcribe_with_details(c['actual_audio_path'])
        runs[case]=asdict(r)
        (output/f'{case}.json').write_bytes(encode_json({'case_id':case,'split':'evaluation','run':runs[case]}))
        (output/f'{case}_transcript.txt').write_text(r.transcript.text+'\n',encoding='utf-8')
        print(case,'transcribed',round(r.processing_seconds,3),'s',flush=True)
    # Reference texts are loaded only after both evaluation inferences complete.
    rows=[]
    for case in ('A03','A04','A05','A08','A12'):
        c=next(c for c in corpus['clips'] if c['case_id']==case)
        reference=(ROOT/c['actual_transcript_ref']).read_bytes()
        if hashlib.sha256(reference).hexdigest()!=c['reference_sha256']:raise ValueError('Reference changed')
        run=runs[case] if case in runs else json.loads((dev/f'{case}.json').read_bytes())['run']
        metrics=word_error_rate(reference.decode('utf-8'),run['transcript']['text'])
        rows.append({'case_id':case,'split':'development' if case in ('A03','A04','A05') else 'evaluation',
            'metrics':asdict(metrics),'duration_seconds':run['features']['duration_seconds'],
            'processing_seconds':run['processing_seconds'],'features':run['features']})
    groups={}
    for split in ('development','evaluation'):
        selected=[r for r in rows if r['split']==split]
        n=sum(r['metrics']['reference_words'] for r in selected)
        counts={k:sum(r['metrics'][k] for r in selected) for k in ('substitutions','deletions','insertions')}
        groups[split]={'files_requested':len(selected),'files_succeeded':len(selected),
            'reference_words':n,**counts,'wer':sum(counts.values())/n if n else None,
            'audio_seconds':sum(r['duration_seconds'] for r in selected),
            'processing_seconds':sum(r['processing_seconds'] for r in selected)}
    result={'date':'2026-11-05','groups':groups,'cases':rows,'same_speaker_both_splits':True,
            'tts_processed':False,'clinical_validation':False,'model_parameters_changed':False,
            'wer_acceptance_threshold_predefined':False}
    (output/'evaluation.json').write_bytes(encode_json(result))
    print(json.dumps(groups,indent=2))


if __name__=='__main__':main()
