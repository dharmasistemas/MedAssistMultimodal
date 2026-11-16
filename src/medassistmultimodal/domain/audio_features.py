"""Local technical energy descriptors; never a clinical or emotion classifier."""
from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class LowEnergyInterval:
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True, slots=True)
class AudioFeatures:
    version: str
    sample_rate_hz: int
    sample_count: int
    duration_seconds: float
    rms_normalized: float
    peak_abs_normalized: float
    energy_window_seconds: float
    low_energy_rms_threshold: float
    minimum_low_energy_seconds: float
    low_energy_intervals: tuple[LowEnergyInterval, ...]


def describe_audio(samples, *, sample_rate_hz=16000, window_seconds=0.02,
                   low_energy_rms=0.01, minimum_low_energy_seconds=0.2):
    import numpy as np
    if type(sample_rate_hz) is not int or sample_rate_hz<=0:
        raise ValueError('Positive integer sample rate required')
    for value in (window_seconds,low_energy_rms,minimum_low_energy_seconds):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite feature parameters required')
    if not isinstance(samples,np.ndarray) or samples.ndim!=1 or samples.size==0 or samples.dtype.kind!='f' or not np.isfinite(samples).all():
        raise ValueError('Nonempty finite mono floating samples required')
    width=round(window_seconds*sample_rate_hz)
    if width<1:raise ValueError('Energy window smaller than one sample')
    intervals=[];start=None
    for first in range(0,len(samples),width):
        last=min(first+width,len(samples))
        rms=float(np.sqrt(np.mean(samples[first:last].astype(np.float64)**2)))
        if rms < low_energy_rms:
            if start is None:start=first
        elif start is not None:
            if (first-start)/sample_rate_hz>=minimum_low_energy_seconds:
                intervals.append(LowEnergyInterval(start/sample_rate_hz,first/sample_rate_hz))
            start=None
    if start is not None and (len(samples)-start)/sample_rate_hz>=minimum_low_energy_seconds:
        intervals.append(LowEnergyInterval(start/sample_rate_hz,len(samples)/sample_rate_hz))
    return AudioFeatures('energy-descriptors-v1',sample_rate_hz,len(samples),len(samples)/sample_rate_hz,
        float(np.sqrt(np.mean(samples.astype(np.float64)**2))),float(np.max(np.abs(samples))),
        width/sample_rate_hz,low_energy_rms,minimum_low_energy_seconds,tuple(intervals))
