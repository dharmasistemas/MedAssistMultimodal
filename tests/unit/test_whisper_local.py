from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from medassistmultimodal.application.audio import Transcript,TranscriptSegment,AudioProviderUnavailableError,AudioNoSpeechError
from medassistmultimodal.domain.audio_features import describe_audio
from medassistmultimodal.providers.whisper_local import LocalWhisperTranscriber


def make(tmp_path,segments=None):
    (tmp_path/'model').mkdir();(tmp_path/'model/model.bin').write_bytes(b'offline fixture')
    (tmp_path/'audio.m4a').write_bytes(b'offline fixture')
    model=Mock()
    model.transcribe.return_value=(iter(segments if segments is not None else [SimpleNamespace(start=0.2,end=0.8,text=' Não senti dor. ')]),SimpleNamespace())
    factory=Mock(return_value=model)
    provider=LocalWhisperTranscriber(root=tmp_path,model_directory='model',model_factory=factory,
        decoder=lambda *a,**kw:np.ones(16000,dtype=np.float32)*0.1)
    return provider,model,factory


def test_contract_segments_and_pinned_no_download_settings(tmp_path):
    p,m,f=make(tmp_path);r=p.transcribe_with_details('audio.m4a')
    assert r.transcript.text=='Não senti dor.' and r.transcript.source=='whisper'
    assert r.transcript.segments[0].start_seconds==0.2
    assert 'sha256=' in r.transcript.evidence_ref and r.features.duration_seconds==1
    assert f.call_args.kwargs==dict(device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
    assert m.transcribe.call_args.kwargs==dict(language='pt',task='transcribe',beam_size=5,
        temperature=0.0,condition_on_previous_text=False,vad_filter=False,word_timestamps=False)


@pytest.mark.parametrize('fault',['decode','load','generator','empty','nan','outside','overlap'])
def test_controlled_failures(tmp_path,fault):
    segments=[] if fault=='empty' else None
    if fault=='nan':segments=[SimpleNamespace(start=float('nan'),end=0.5,text='fala')]
    if fault=='outside':segments=[SimpleNamespace(start=0,end=2,text='fala')]
    if fault=='overlap':segments=[SimpleNamespace(start=0,end=.6,text='a'),SimpleNamespace(start=.5,end=.8,text='b')]
    p,m,f=make(tmp_path,segments)
    if fault=='decode':p.decoder=Mock(side_effect=RuntimeError('bad input'))
    if fault=='load':f.side_effect=RuntimeError('missing DLL')
    if fault=='generator':
        def fail():
            raise RuntimeError('inference failed during iteration')
            yield
        m.transcribe.return_value=(fail(),None)
    with pytest.raises(AudioNoSpeechError if fault=='empty' else AudioProviderUnavailableError):p.transcribe('audio.m4a')


def test_missing_model_does_not_call_factory(tmp_path):
    (tmp_path/'audio.wav').write_bytes(b'fixture')
    f=Mock();p=LocalWhisperTranscriber(root=tmp_path,model_directory='missing',model_factory=f,
        decoder=lambda *a,**kw:np.ones(16000,dtype=np.float32))
    with pytest.raises(AudioProviderUnavailableError):p.transcribe('audio.wav')
    f.assert_not_called()


@pytest.mark.parametrize('path',['_backup/a.wav','../a.wav','.git/a.wav','missing.wav'])
def test_path_rejection(tmp_path,path):
    p,_,_=make(tmp_path)
    with pytest.raises(ValueError):p.transcribe(path)


def test_language_rejected_before_inference(tmp_path):
    p,m,_=make(tmp_path)
    with pytest.raises(ValueError):p.transcribe('audio.m4a',language='en')
    m.transcribe.assert_not_called()


def test_energy_intervals_minimum_and_boundary():
    a=np.r_[np.zeros(3200),np.ones(3200)*.1,np.zeros(1600)].astype(np.float32)
    r=describe_audio(a)
    assert r.duration_seconds==.5 and len(r.low_energy_intervals)==1
    assert r.low_energy_intervals[0].start_seconds==0 and r.low_energy_intervals[0].end_seconds==.2
    assert not describe_audio(np.ones(3200,dtype=np.float32)*.125,low_energy_rms=.125).low_energy_intervals
    assert len(describe_audio(np.zeros(3200,dtype=np.float32)).low_energy_intervals)==1


@pytest.mark.parametrize('samples',[np.array([],dtype=np.float32),np.array([float('nan')]),np.array([1]),np.ones((2,2))])
def test_feature_invalid_input(samples):
    with pytest.raises(ValueError):describe_audio(samples)


def test_existing_mock_constructor_remains_compatible():
    t=Transcript('texto','pt-BR','mock','fixture')
    assert t.segments==()
    with pytest.raises(ValueError):TranscriptSegment(True,1,'x')
