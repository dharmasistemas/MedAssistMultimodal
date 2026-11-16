"""Fixed first real development run: human A03/A04/A05, no references or evaluation."""
from dataclasses import asdict
import argparse
import hashlib
import json
import os
from pathlib import Path

from medassistmultimodal.providers.whisper_local import LocalWhisperTranscriber,checked_path
from medassistmultimodal.application.register_vitals import encode_json

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/interim/audio/day13_development_v1_final')
    args=parser.parse_args()
    # Configure MKL before NumPy/native backend initialization. Never allow duplicate runtimes.
    os.environ['MKL_THREADING_LAYER']='SEQUENTIAL'
    os.environ['OMP_NUM_THREADS']='4'
    os.environ['HF_HUB_OFFLINE']='1'
    manifest=json.loads((ROOT/'data/manifests/day13_whisper_assets.json').read_bytes())
    for record in manifest['model']['files']:
        path=ROOT/manifest['model']['local_path']/record['name']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Model hash mismatch')
    corpus=json.loads((ROOT/'data/interim/audio/simulated_v1/collection_status.json').read_bytes())
    chosen=[c for c in corpus['clips'] if c['case_id'] in ('A03','A04','A05')]
    if len(chosen)!=3:raise ValueError('Development selection incomplete')
    # Freeze run configuration before any inference, with no reference text passed to model.
    output=checked_path(args.output,ROOT)
    if not output.is_relative_to(ROOT/'data/interim/audio'):
        raise ValueError('Output must be under data/interim/audio')
    output.mkdir(parents=True,exist_ok=False)
    config={'model_revision':manifest['model']['revision'],'device':'cpu','compute_type':'int8',
        'cpu_threads':4,'language':'pt','beam_size':5,'temperature':0.0,
        'condition_on_previous_text':False,'vad_filter':False,'word_timestamps':False,
        'cases':['A03','A04','A05'],'energy_window_seconds':.02,'low_energy_rms':.01,
        'minimum_low_energy_seconds':.2,'mkl_threading_layer':'SEQUENTIAL','omp_num_threads':4}
    (output/'run_config.json').write_bytes(encode_json(config))
    p=LocalWhisperTranscriber(root=ROOT,model_directory=manifest['model']['local_path'])
    rows=[]
    for c in chosen:
        source=ROOT/c['actual_audio_path']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=c['audio_sha256']:raise ValueError('Source changed')
        if not c['human_verified'] or not c['consent_ref']:raise ValueError('Human reference/permission missing')
        run=p.transcribe_with_details(c['actual_audio_path'])
        artifact={'case_id':c['case_id'],'split':'development','speaker_ref':'S01',
            'model_revision':config['model_revision'],'run':asdict(run),'clinical_validation':False}
        (output/f'{c["case_id"]}.json').write_bytes(encode_json(artifact))
        (output/f'{c["case_id"]}_transcript.txt').write_text(run.transcript.text+'\n',encoding='utf-8')
        rows.append({'case_id':c['case_id'],'duration_seconds':run.features.duration_seconds,
            'processing_seconds':run.processing_seconds,'segments':len(run.transcript.segments)})
        print(c['case_id'],'complete',round(run.processing_seconds,3),'s',flush=True)
    (output/'summary.json').write_bytes(encode_json({'date':'2026-11-05','rows':rows,
        'evaluation_cases_processed':False,'tts_processed':False,'references_passed_to_model':False}))


if __name__=='__main__':main()
