from dataclasses import replace,FrozenInstanceError
import hashlib
from unittest.mock import Mock

import numpy as np
import pytest

from medassistmultimodal.domain.audio_features import AudioFeatures,LowEnergyInterval,describe_audio
from medassistmultimodal.domain.audio_pauses import assess_internal_pauses
from medassistmultimodal.infrastructure.acoustic_pilot import analyze_acoustic_file,AcousticPilotError


def features(duration=12,intervals=((1,1.6),(3,3.6),(5,5.6)),*,rms=.1,peak=.2):
    return AudioFeatures('energy-descriptors-v1',16000,round(duration*16000),duration,rms,peak,
        .02,.01,.2,tuple(LowEnergyInterval(a,b) for a,b in intervals))


def test_exact_three_pauses_and_fifteen_percent_are_inclusive():
    r=assess_internal_pauses(features())
    assert r.status=='signal' and r.long_pause_count==3
    assert r.long_pause_samples==28800 and r.long_pause_fraction==.15
    assert r.central_duration_seconds==12 and r.long_pauses[0].start_seconds==1
    assert r.confidence is None and r.clinical_validation is False
    with pytest.raises(FrozenInstanceError):r.status='no_signal'


@pytest.mark.parametrize('f',[
    features(duration=12.02),
    features(intervals=((1,1.58),(3,3.6),(5,5.6))),
    features(duration=5,intervals=((1,2),(3,4))),
    features(intervals=()),
])
def test_fraction_count_duration_and_no_pause_negatives(f):
    assert assess_internal_pauses(f).status=='no_signal'


def test_boundary_pauses_do_not_inflate_count_or_denominator():
    r=assess_internal_pauses(features(duration=14,intervals=((0,1),(2,2.6),(4,4.6),(6,6.6),(13,14))))
    assert r.status=='signal' and r.long_pause_count==3 and r.long_pause_fraction==.15
    assert (r.central_first_sample,r.central_end_sample)==(16000,208000)
    assert r.long_pauses[0].first_sample==32000  # Original coordinates are preserved.


def test_exact_three_second_central_span_and_insufficiency():
    assert assess_internal_pauses(features(5,((0,1),(4,5)))).status=='no_signal'
    r=assess_internal_pauses(features(5,((0,1.02),(4,5))))
    assert r.status=='insufficient_evidence' and r.reason=='central_span_too_short'
    assert r.long_pause_count is None and r.long_pause_fraction is None


@pytest.mark.parametrize('rms,peak',[(0,0),(.009,.1),(.01,.049)])
def test_silence_and_low_signal_are_not_normal_results(rms,peak):
    r=assess_internal_pauses(features(rms=rms,peak=peak))
    assert r.status=='insufficient_evidence' and r.reason=='low_signal_level'
    assert r.long_pause_samples is None


def test_low_signal_equalities_and_entire_clip_silence():
    assert assess_internal_pauses(features(rms=.01,peak=.05)).status=='signal'
    r=assess_internal_pauses(features(5,((0,5),),rms=0,peak=0))
    assert r.status=='insufficient_evidence' and r.central_duration_seconds==0


@pytest.mark.parametrize('field,value',[
    ('version','other'),('sample_rate_hz',8000),('sample_rate_hz',True),('sample_count',True),
    ('sample_count',0),('duration_seconds',11),('duration_seconds',float('nan')),
    ('energy_window_seconds',.04),('low_energy_rms_threshold',.02),('minimum_low_energy_seconds',.1),
    ('rms_normalized',float('inf')),('rms_normalized',True),('rms_normalized',.3),
    ('peak_abs_normalized',1.1),('peak_abs_normalized',-.1),('low_energy_intervals',[]),
])
def test_bad_metadata_rejected(field,value):
    with pytest.raises(ValueError):assess_internal_pauses(replace(features(),**{field:value}))


@pytest.mark.parametrize('duration',[4.98,60.02])
def test_unsupported_duration_rejected(duration):
    with pytest.raises(ValueError,match='unsupported_duration'):assess_internal_pauses(features(duration,()))


@pytest.mark.parametrize('duration',[5,60])
def test_duration_boundaries_supported(duration):
    assert assess_internal_pauses(features(duration,())).status=='no_signal'


@pytest.mark.parametrize('intervals',[
    ((1,1.19),),((1.001,1.601),),((1.00001,1.60001),),((1,1.6),(1.5,2.1)),
    ((1,1.6),(1.6,2.2)),((3,3.6),(1,1.6)),((-1,1),),((1,13),),((1,1),),
    ((1,float('nan')),),((True,2),),
])
def test_invalid_overlapping_split_or_unaligned_intervals(intervals):
    with pytest.raises(ValueError):assess_internal_pauses(features(intervals=intervals))


def test_twenty_ms_descriptor_and_short_intervals_stay_out_of_long_count():
    samples=np.full(12*16000,.1,dtype=np.float32)
    for a,b in ((1,1.6),(3,3.6),(5,5.6),(7,7.2)):samples[round(a*16000):round(b*16000)]=0
    r=assess_internal_pauses(describe_audio(samples))
    assert r.status=='signal' and r.long_pause_count==3 and r.long_pause_samples==28800


def test_energy_threshold_is_strict_and_noise_can_mask_a_pause():
    # Both signals have no low-energy intervals; energy alone is not a speech classifier.
    for samples in (np.full(80000,.01,dtype=np.float64),np.random.default_rng(7).uniform(-.2,.2,80000)):
        f=describe_audio(samples)
        assert not f.low_energy_intervals
        assert assess_internal_pauses(f).status!='signal'


def test_full_scale_peak_is_flag_not_a_clipping_diagnosis():
    r=assess_internal_pauses(describe_audio(np.ones(80000,dtype=np.float32)))
    assert r.status=='no_signal' and r.quality_flags==('full_scale_peak_not_proof_of_clipping',)


@pytest.fixture
def source(tmp_path):
    path=tmp_path/'fixture.mp3';path.write_bytes(b'only an injected decoder can read this fixture')
    return path,hashlib.sha256(path.read_bytes()).hexdigest()


def test_local_adapter_uses_fixture_without_models_or_normalization(tmp_path,source):
    path,sha=source;decoder=Mock(return_value=np.full(80000,.1,dtype=np.float32))
    before=path.read_bytes();r=analyze_acoustic_file(tmp_path,path.name,expected_sha256=sha,decoder=decoder)
    assert r.is_mock is True and r.decoder=='injected_offline_fixture'
    assert r.source_sha256==sha and r.assessment.status=='no_signal'
    assert r.features.peak_abs_normalized==pytest.approx(.1) and path.read_bytes()==before
    decoder.assert_called_once_with(str(path),sampling_rate=16000)


@pytest.mark.parametrize('reference,expected',[
    ('../fixture.mp3','a'*64),('_backup/file.mp3','a'*64),('missing.mp3','a'*64),
    ('fixture.mp3','a'*64),('fixture.mp3','invalid'),('fixture.txt','a'*64),
])
def test_bad_source_never_calls_decoder(tmp_path,source,reference,expected):
    decoder=Mock()
    with pytest.raises(AcousticPilotError):analyze_acoustic_file(tmp_path,reference,expected_sha256=expected,decoder=decoder)
    decoder.assert_not_called()


def test_decoder_failure_is_safe_and_not_no_signal(tmp_path,source):
    path,sha=source;decoder=Mock(side_effect=RuntimeError('PRIVATE_ERROR_SHOULD_NOT_LEAK'))
    with pytest.raises(AcousticPilotError,match='^decoder_unavailable_or_failed$'):
        analyze_acoustic_file(tmp_path,path.name,expected_sha256=sha,decoder=decoder)


def test_change_during_processing_detected(tmp_path,source):
    path,sha=source
    def decode(*args,**kwargs):path.write_bytes(b'changed');return np.full(80000,.1,dtype=np.float32)
    with pytest.raises(AcousticPilotError,match='source_changed'):
        analyze_acoustic_file(tmp_path,path.name,expected_sha256=sha,decoder=decode)


@pytest.mark.parametrize('samples',[
    np.array([],dtype=np.float32),np.zeros((10,2),dtype=np.float32),np.zeros(80000,dtype=np.int16),
    np.full(80000,float('nan')),np.full(80000,1.1),np.zeros(79000,dtype=np.float32),
])
def test_invalid_decoder_output_rejected(tmp_path,source,samples):
    path,sha=source
    with pytest.raises(AcousticPilotError):
        analyze_acoustic_file(tmp_path,path.name,expected_sha256=sha,decoder=lambda *a,**k:samples)
