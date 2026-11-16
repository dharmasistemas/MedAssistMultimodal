"""Waveform validation and existing energy descriptors; no ASR or LLM."""
from medassistmultimodal.domain.audio_features import describe_audio
from medassistmultimodal.domain.internal_pauses import detect_internal_pauses


def analyze_pause_samples(samples,*,sample_rate_hz=16000):
    import numpy as np
    if type(sample_rate_hz) is not int or sample_rate_hz!=16000:raise ValueError('16000 Hz required')
    if (not isinstance(samples,np.ndarray) or samples.ndim!=1 or samples.dtype.kind!='f'
        or not 80000<=len(samples)<=960000 or not np.isfinite(samples).all()
        or np.any(np.abs(samples)>1)):
        raise ValueError('Finite normalized mono float samples, duration 5–60 seconds required')
    features=describe_audio(samples,sample_rate_hz=sample_rate_hz)
    return features,detect_internal_pauses(features)
