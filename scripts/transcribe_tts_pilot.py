"""Authorized local Whisper processing of seven previously unprocessed TTS files."""
import os
os.environ['MKL_THREADING_LAYER'] = 'SEQUENTIAL'
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['HF_HUB_OFFLINE'] = '1'

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path

from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.providers.whisper_local import LocalWhisperTranscriber, checked_path
from medassistmultimodal.domain.word_error_rate import word_error_rate

ROOT = Path(__file__).resolve().parents[1]
CASES = ('A01', 'A02', 'A06', 'A07', 'A09', 'A10', 'A11')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT/'data/manifests/day13_whisper_assets.json'
    manifest = json.loads(manifest_path.read_bytes())
    for record in manifest['model']['files']:
        path = checked_path(str(ROOT/manifest['model']['local_path']/record['name']), ROOT)
        if sha(path) != record['sha256']: raise ValueError('Model changed')
    corpus_path = ROOT/'data/interim/audio/simulated_v1/collection_status.json'
    corpus = json.loads(corpus_path.read_bytes())
    selected = [next(c for c in corpus['clips'] if c['case_id'] == case) for case in CASES]
    permission_path = ROOT/'data/interim/audio/simulated_v1/permissions/dark_planner_support_2026-11-06.json'
    permission = json.loads(permission_path.read_bytes())
    for c in selected:
        if c['case_id'] not in permission['case_ids'] or not c['human_verified']:
            raise ValueError('Missing permission or human reference review')
        if c.get('tts_permission_status') != 'permission_reported_by_support_for_requested_use':
            raise ValueError('TTS permission not recorded')
        if sha(checked_path(c['actual_audio_path'], ROOT)) != c['audio_sha256']:
            raise ValueError('Audio changed')
        if sha(checked_path(c['actual_transcript_ref'], ROOT)) != c['reference_sha256']:
            raise ValueError('Reference changed')
    out = checked_path('data/interim/audio/tts_whisper_2026-11-06_v1', ROOT)
    out.mkdir(exist_ok=False)
    old_config = json.loads((ROOT/'data/interim/audio/day13_development_v1_final/run_config.json').read_bytes())
    config = dict(old_config, cases=list(CASES), date='2026-11-06',
                  started_at=datetime.now().astimezone().isoformat(),
                  group='complementary_known_tts_not_independent_evaluation',
                  references_passed_to_model=False, cloud_used=False, retries=0,
                  permission_sha256=sha(permission_path), model_manifest_sha256=sha(manifest_path),
                  runner_sha256=sha(Path(__file__)),
                  adapter_sha256=sha(ROOT/'src/medassistmultimodal/providers/whisper_local.py'),
                  sources={c['case_id']:dict(audio_sha256=c['audio_sha256'],reference_sha256=c['reference_sha256']) for c in selected})
    (out/'run_config.json').write_bytes(encode_json(config))
    provider = LocalWhisperTranscriber(root=ROOT,model_directory=manifest['model']['local_path'])
    rows = []
    for c in selected:
        row = dict(case_id=c['case_id'],speaker_ref=c['speaker_ref'],origin='synthetic_tts',
                   group=config['group'],permission_ref=c['tts_permission_ref'])
        try:
            run = provider.transcribe_with_details(c['actual_audio_path'])
            row.update(run=asdict(run),status='transcribed',error=None)
            (out/f'{c["case_id"]}_transcript.txt').write_text(run.transcript.text+'\n',encoding='utf-8')
            print(c['case_id'],'transcribed',round(run.processing_seconds,3),'s',flush=True)
        except Exception as exc:
            row.update(run=None,status='failed',error=type(exc).__name__+': '+str(exc))
            print(c['case_id'],'failed',row['error'],flush=True)
        rows.append(row)
        (out/f'{c["case_id"]}.json').write_bytes(encode_json(row))
    # Reference text enters the metric only after all model calls complete.
    for c,row in zip(selected,rows):
        ref_path = checked_path(c['actual_transcript_ref'], ROOT)
        if sha(ref_path) != c['reference_sha256']: raise ValueError('Reference changed during run')
        if sha(checked_path(c['actual_audio_path'], ROOT)) != c['audio_sha256']:
            raise ValueError('Original changed during run')
        row['reference_text'] = ref_path.read_text(encoding='utf-8').strip()
        row['metrics'] = None if row['run'] is None else asdict(word_error_rate(
            row['reference_text'], row['run']['transcript']['text']))
        (out/f'{c["case_id"]}.json').write_bytes(encode_json(row))
    succeeded = [r for r in rows if r['run'] is not None]
    words = sum(r['metrics']['reference_words'] for r in succeeded)
    counts = {k:sum(r['metrics'][k] for r in succeeded) for k in ('substitutions','deletions','insertions')}
    summary = dict(date='2026-11-06',requested=7,succeeded=len(succeeded),failed=7-len(succeeded),
                   reference_words=words,**counts,wer=sum(counts.values())/words if words else None,
                   audio_seconds=sum(r['run']['features']['duration_seconds'] for r in succeeded),
                   processing_seconds=sum(r['run']['processing_seconds'] for r in succeeded),
                   speaker_origins=['TTS-F01','TTS-M01'],clinical_validation=False,
                   model_parameters_changed=False,independent_test=False,
                   case_metrics={r['case_id']:r['metrics'] for r in rows})
    (out/'summary.json').write_bytes(encode_json(summary))
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__': main()
