"""Authorized seven-clip TTS Whisper expansion; no LLM or audio uploads."""
import os
os.environ['MKL_THREADING_LAYER'] = 'SEQUENTIAL'
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['HF_HUB_OFFLINE'] = '1'

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path

from medassistmultimodal.providers.whisper_local import LocalWhisperTranscriber, checked_path
from medassistmultimodal.domain.word_error_rate import word_error_rate

ROOT = Path(__file__).resolve().parents[1]
CASES = ('A01', 'A02', 'A06', 'A07', 'A09', 'A10', 'A11')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    corpus_path = ROOT/'data/interim/audio/simulated_v1/collection_status.json'
    corpus = json.loads(corpus_path.read_bytes())
    permission_path = ROOT/'data/interim/audio/simulated_v1/permissions/dark_planner_support_2026-11-06.json'
    permission = json.loads(permission_path.read_bytes())
    if set(permission['case_ids']) != set(CASES): raise ValueError('Permission selection mismatch')
    manifest_path = ROOT/'data/manifests/day13_whisper_assets.json'
    manifest = json.loads(manifest_path.read_bytes())
    for item in manifest['model']['files']:
        path = checked_path(str(ROOT/manifest['model']['local_path']/item['name']), ROOT)
        if sha(path) != item['sha256']: raise ValueError('Model hash mismatch')
    chosen = [next(c for c in corpus['clips'] if c['case_id'] == case) for case in CASES]
    for c in chosen:
        if not c['human_verified'] or c.get('tts_permission_status') != 'permission_reported_by_support_for_requested_use':
            raise ValueError('Missing reviewed reference/support permission')
        if sha(checked_path(c['actual_audio_path'],ROOT)) != c['audio_sha256']:
            raise ValueError('Audio changed')
        if sha(checked_path(c['actual_transcript_ref'],ROOT)) != c['reference_sha256']:
            raise ValueError('Reference changed')
    out = checked_path('data/interim/audio/day14_tts_whisper_v1',ROOT)
    out.mkdir(exist_ok=False)
    config = json.loads((ROOT/'data/interim/audio/day13_development_v1_final/run_config.json').read_bytes())
    config.update(date='2026-11-06', started_at=datetime.now().astimezone().isoformat(),
                  cases=list(CASES), purpose='known_corpus_tts_expansion_not_independent_test',
                  retries=0, audio_uploaded=False, llm_used=False,
                  reference_text_passed_to_model=False,
                  input_hashes={c['case_id']:c['audio_sha256'] for c in chosen},
                  reference_hashes={c['case_id']:c['reference_sha256'] for c in chosen},
                  permission_sha256=sha(permission_path),model_manifest_sha256=sha(manifest_path),
                  runner_sha256=sha(Path(__file__)),
                  code_sha256={p:sha(ROOT/p) for p in (
                      'src/medassistmultimodal/providers/whisper_local.py',
                      'src/medassistmultimodal/domain/audio_features.py',
                      'src/medassistmultimodal/domain/word_error_rate.py')})
    save(out/'run_config.json',config)
    provider = LocalWhisperTranscriber(root=ROOT,model_directory=manifest['model']['local_path'])
    rows=[]
    for c in chosen:
        row=dict(case_id=c['case_id'],speaker_ref=c['speaker_ref'],origin='synthetic_tts',
                 input_sha256=c['audio_sha256'],run=None,error=None)
        try:
            run=provider.transcribe_with_details(c['actual_audio_path'])
            row['run']=asdict(run)
            (out/f'{c["case_id"]}_transcript.txt').write_text(run.transcript.text+'\n',encoding='utf-8')
        except Exception as exc:
            row['error']=dict(type=type(exc).__name__,message=str(exc))
        save(out/f'{c["case_id"]}.json',row);rows.append(row)
        print(c['case_id'],'transcribed' if row['run'] else row['error'],
              round(row['run']['processing_seconds'],3) if row['run'] else '',flush=True)
    # Score after all inferences, without supplying reference text to Whisper.
    for row,c in zip(rows,chosen):
        if sha(checked_path(c['actual_audio_path'],ROOT)) != c['audio_sha256']:
            raise ValueError('Audio changed during run')
        reference=checked_path(c['actual_transcript_ref'],ROOT)
        if sha(reference) != c['reference_sha256']: raise ValueError('Reference changed during run')
        row['metrics']=None if row['run'] is None else asdict(word_error_rate(
            reference.read_text(encoding='utf-8'), row['run']['transcript']['text']))
        save(out/f'{c["case_id"]}.json',row)
    valid=[r for r in rows if r['run']]
    n=sum(r['metrics']['reference_words'] for r in valid)
    counts={k:sum(r['metrics'][k] for r in valid) for k in ('substitutions','deletions','insertions')}
    result=dict(date='2026-11-06',requested=len(rows),succeeded=len(valid),failed=len(rows)-len(valid),
                cases=rows,reference_words=n,**counts,wer=sum(counts.values())/n if n else None,
                wer_scope='successful_tts_clips_only',
                audio_seconds=sum(r['run']['features']['duration_seconds'] for r in valid),
                processing_seconds=sum(r['run']['processing_seconds'] for r in valid),
                independent_validation=False,clinical_validation=False,llm_used=False)
    save(out/'evaluation.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2),flush=True)


if __name__ == '__main__': main()
