from dataclasses import replace
import hashlib
from unittest.mock import Mock

import numpy as np
import pytest

from medassistmultimodal.domain.audio_features import AudioFeatures,LowEnergyInterval
from medassistmultimodal.domain.internal_pauses import detect_internal_pauses
from medassistmultimodal.application.analyze_acoustic_pauses import analyze_pause_samples
from medassistmultimodal.providers.acoustic_local import LocalPauseAnalyzer,AcousticInputError,AcousticDecoderUnavailable


LONG=((1.,1.6),(3.,3.6),(5.,5.6))


def features(*,seconds=12,intervals=LONG,rms=.1,peak=.2):
    return AudioFeatures('energy-descriptors-v1',16000,round(seconds*16000),seconds,rms,peak,
        .02,.01,.2,tuple(LowEnergyInterval(a,b) for a,b in intervals))


@pytest.mark.parametrize('seconds,intervals,status,count',[
    (12,LONG,'signal',3), # 3*0.6/12 = 15%, exactly inclusive.
    (12.02,LONG,'no_signal',3),
    (12,((1,2),(3,4)),'no_signal',2),
    (12,((1,1.58),(3,3.58),(5,5.58)),'no_signal',0),
    (12,(),'no_signal',0),
    (12,((0,1),(4,4.6),(6,6.6),(8,8.6),(11,12)),'signal',3),
])
def test_boundaries_and_edge_exclusion(seconds,intervals,status,count):
    result=detect_internal_pauses(features(seconds=seconds,intervals=intervals))
    assert result.status==status and result.long_pause_count==count
    assert result.confidence is None and result.clinical_validation is False
    assert result.medical_condition_inferred is False
    if seconds==12 and intervals==LONG:
        assert result.long_pause_fraction==.15 and result.long_pause_samples==28800
        assert result.long_pauses[0].first_sample==16000
        assert result.long_pauses[0].last_sample_exclusive==25600


def test_edges_do_not_change_original_timestamps():
    result=detect_internal_pauses(features(intervals=((0,1),*LONG[1:],(7,7.6),(11,12))))
    assert result.analysis_first_sample==16000 and result.analysis_last_sample_exclusive==176000
    assert result.central_duration_seconds==10
    assert result.long_pauses[0].start_seconds==3


@pytest.mark.parametrize('rms,peak',[(0,0),(.009,.2),(.01,.049)])
def test_low_signal_is_insufficient_not_negative(rms,peak):
    r=detect_internal_pauses(features(rms=rms,peak=peak))
    assert r.status=='insufficient_evidence' and r.reason=='low_signal'
    assert r.long_pause_fraction is None and r.long_pause_count is None


def test_quality_threshold_equalities_and_central_span():
    assert detect_internal_pauses(features(rms=.01,peak=.05)).status=='signal'
    good=features(seconds=8,intervals=((0,2),(5,8)))
    assert detect_internal_pauses(good).central_duration_seconds==3
    bad=features(seconds=8,intervals=((0,2.02),(5,8)))
    assert detect_internal_pauses(bad).reason=='central_interval_too_short'


@pytest.mark.parametrize('seconds',[5,60])
def test_supported_duration_equalities(seconds):
    assert detect_internal_pauses(features(seconds=seconds,intervals=())).status=='no_signal'


@pytest.mark.parametrize('field,value',[
    ('sample_rate_hz',True),('sample_rate_hz',44100),('sample_count',True),
    ('duration_seconds',11.99),('duration_seconds',float('nan')),
    ('energy_window_seconds',.04),('low_energy_rms_threshold',.02),('minimum_low_energy_seconds',.1),
    ('rms_normalized',True),('rms_normalized',-.1),('rms_normalized',.3),
    ('peak_abs_normalized',1.01),('version','other'),('low_energy_intervals',[]),
])
def test_inconsistent_features_are_rejected(field,value):
    with pytest.raises(ValueError):detect_internal_pauses(replace(features(),**{field:value}))


@pytest.mark.parametrize('intervals',[
    ((1,1.18),),((1,1.6),(1.4,2)),((3,3.6),(1,1.6)),
    ((1,1.6),(1.6,2.2)),((-1,1),),((11,13),),((1.001,1.601),),((1,float('inf')),),
])
def test_invalid_or_unmerged_intervals_rejected(intervals):
    with pytest.raises(ValueError):detect_internal_pauses(features(intervals=intervals))


def samples(intervals=LONG,seconds=12,level=.2):
    result=np.full(round(seconds*16000),level,dtype=np.float64)
    for a,b in intervals:result[round(a*16000):round(b*16000)]=0
    return result


def test_waveform_pipeline_positive_and_no_normalization_or_mutation():
    wave=samples();original=wave.copy();f,r=analyze_pause_samples(wave)
    assert np.array_equal(wave,original)
    assert f.version=='energy-descriptors-v1' and r.status=='signal' and r.long_pause_fraction==.15
    _,low=analyze_pause_samples(wave*.1)
    assert low.status=='insufficient_evidence'


@pytest.mark.parametrize('wave',[
    np.zeros(80000),np.full(80000,.001),np.full(80000,.02),
])
def test_silence_or_low_volume_does_not_mean_normal(wave):
    _,r=analyze_pause_samples(wave)
    assert r.status=='insufficient_evidence'


@pytest.mark.parametrize('wave',[
    np.array([],dtype=float),np.zeros((80000,2)),np.zeros(80000,dtype=np.int16),
    np.full(80000,float('nan')),np.full(80000,float('inf')),np.full(80000,1.01),
    np.zeros(79999),np.zeros(960001),
])
def test_invalid_waveform_rejected(wave):
    with pytest.raises(ValueError):analyze_pause_samples(wave)


def test_noise_can_mask_pauses_without_medical_inference():
    wave=samples()
    for a,b in LONG:wave[round(a*16000):round(b*16000)]=.02
    _,r=analyze_pause_samples(wave)
    assert r.status=='no_signal' and r.medical_condition_inferred is False
    # Valid numerical saturation is not diagnosed or assigned a new ad-hoc threshold.
    _,r=analyze_pause_samples(np.ones(80000))
    assert r.status=='no_signal' and r.medical_condition_inferred is False


def test_continuous_float_waveform_rounding_is_valid():
    _,r=analyze_pause_samples(samples(intervals=(),level=.1))
    assert r.status=='no_signal'


def test_minimum_descriptor_interval_inclusive_but_not_a_long_pause():
    wave=samples(intervals=((1.,1.2),))
    f,r=analyze_pause_samples(wave)
    assert len(f.low_energy_intervals)==1
    assert r.long_pause_count==0 and r.status=='no_signal'


def test_media_unavailable_after_decoder_failure_is_input_error(tmp_path):
    path=tmp_path/'fixture.mp3';path.write_bytes(b'original');sha=hashlib.sha256(b'original').hexdigest()
    def moved(*args,**kwargs):
        path.rename(tmp_path/'preserved.mp3')
        raise RuntimeError('fixture decode failure')
    with pytest.raises(AcousticInputError,match='unavailable'):
        LocalPauseAnalyzer(tmp_path,decoder=moved).analyze(path.name,expected_sha256=sha)


def test_decoder_injected_mock_hash_and_sampling_rate(tmp_path):
    path=tmp_path/'fixture.mp3';path.write_bytes(b'not-real-mp3')
    sha=hashlib.sha256(path.read_bytes()).hexdigest();decoder=Mock(return_value=samples())
    run=LocalPauseAnalyzer(tmp_path,decoder=decoder).analyze(path.name,expected_sha256=sha)
    decoder.assert_called_once_with(str(path),sampling_rate=16000)
    assert run.is_mock is True and run.source_sha256==sha and run.assessment.status=='signal'


@pytest.mark.parametrize('failure',['missing','hash','outside','suffix','bad_hash'])
def test_invalid_input_does_not_decode(tmp_path,failure):
    path=tmp_path/'fixture.mp3';path.write_bytes(b'original');sha=hashlib.sha256(b'original').hexdigest()
    reference={'missing':'missing.mp3','outside':'../fixture.mp3','suffix':'fixture.txt'}.get(failure,path.name)
    if failure=='hash':sha='0'*64
    if failure=='bad_hash':sha='bad'
    decoder=Mock()
    with pytest.raises(AcousticInputError):LocalPauseAnalyzer(tmp_path,decoder=decoder).analyze(reference,expected_sha256=sha)
    decoder.assert_not_called()


def test_decoder_failure_and_changed_media_are_distinct(tmp_path):
    path=tmp_path/'fixture.mp3';path.write_bytes(b'original');sha=hashlib.sha256(b'original').hexdigest()
    service=LocalPauseAnalyzer(tmp_path,decoder=Mock(side_effect=RuntimeError('private raw error')))
    with pytest.raises(AcousticDecoderUnavailable,match='Cannot decode'):service.analyze(path.name,expected_sha256=sha)
    def changed(*args,**kwargs):path.write_bytes(b'changed');return samples()
    with pytest.raises(AcousticInputError):LocalPauseAnalyzer(tmp_path,decoder=changed).analyze(path.name,expected_sha256=sha)


def test_decoder_invalid_samples_rejected(tmp_path):
    path=tmp_path/'fixture.mp3';path.write_bytes(b'original');sha=hashlib.sha256(b'original').hexdigest()
    with pytest.raises(AcousticInputError):
        LocalPauseAnalyzer(tmp_path,decoder=lambda *a,**k:np.full(80000,2.)).analyze(path.name,expected_sha256=sha)
