"""Fixed, non-diagnostic internal low-energy pause profile; no IO or models."""
from dataclasses import dataclass
import math
from typing import Literal

from .audio_features import AudioFeatures,LowEnergyInterval


@dataclass(frozen=True,slots=True)
class PauseProfile:
    version: str = 'internal-pauses-v1'
    sample_rate_hz: int = 16000
    window_seconds: float = .02
    low_energy_rms: float = .01
    minimum_interval_seconds: float = .2
    long_pause_seconds: float = .6
    minimum_long_pauses: int = 3
    minimum_fraction_percent: int = 15
    minimum_duration_seconds: int = 5
    maximum_duration_seconds: int = 60
    minimum_central_seconds: int = 3
    minimum_peak: float = .05
    minimum_global_rms: float = .01


@dataclass(frozen=True,slots=True)
class PauseInterval:
    first_sample: int
    end_sample: int  # Exclusive.
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True,slots=True)
class PauseAssessment:
    profile: PauseProfile
    status: Literal['signal','no_signal','insufficient_evidence']
    reason: str
    sample_count: int
    central_first_sample: int
    central_end_sample: int
    central_duration_seconds: float
    long_pauses: tuple[PauseInterval,...]
    long_pause_count: int | None
    long_pause_samples: int | None
    long_pause_fraction: float | None
    quality_flags: tuple[str,...]
    clinical_validation: bool = False
    confidence: None = None


def _finite(value):
    return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)


def assess_internal_pauses(features:AudioFeatures) -> PauseAssessment:
    """Use original timestamps and integer samples, excluding only boundary intervals."""
    profile=PauseProfile();rate=profile.sample_rate_hz
    if not isinstance(features,AudioFeatures) or features.version!='energy-descriptors-v1':
        raise ValueError('unsupported_features')
    if type(features.sample_rate_hz) is not int or features.sample_rate_hz!=rate:
        raise ValueError('unsupported_sample_rate')
    count=features.sample_count
    if type(count) is not int or count<=0:raise ValueError('invalid_sample_count')
    if not _finite(features.duration_seconds) or not math.isclose(features.duration_seconds,count/rate,rel_tol=0,abs_tol=1e-9):
        raise ValueError('inconsistent_duration')
    if not profile.minimum_duration_seconds*rate<=count<=profile.maximum_duration_seconds*rate:
        raise ValueError('unsupported_duration')
    for value,expected in ((features.energy_window_seconds,profile.window_seconds),
        (features.low_energy_rms_threshold,profile.low_energy_rms),
        (features.minimum_low_energy_seconds,profile.minimum_interval_seconds)):
        if not _finite(value) or value!=expected:raise ValueError('unsupported_descriptor_profile')
    rms,peak=features.rms_normalized,features.peak_abs_normalized
    if not all(_finite(v) and 0<=v<=1 for v in (rms,peak)) or rms>peak+1e-12:
        raise ValueError('invalid_amplitude_metadata')
    if not isinstance(features.low_energy_intervals,tuple):raise ValueError('typed_intervals_required')
    intervals=[];previous_end=-1;window=round(profile.window_seconds*rate)
    for interval in features.low_energy_intervals:
        if not isinstance(interval,LowEnergyInterval):raise ValueError('typed_intervals_required')
        points=[]
        for time in (interval.start_seconds,interval.end_seconds):
            if not _finite(time) or not 0<=time<=features.duration_seconds:raise ValueError('invalid_interval_time')
            sample=round(time*rate)
            if not math.isclose(time*rate,sample,rel_tol=0,abs_tol=1e-7):raise ValueError('unaligned_sample_time')
            points.append(sample)
        first,end=points
        if first%window or (end%window and end!=count):raise ValueError('unaligned_energy_window')
        if end-first<round(profile.minimum_interval_seconds*rate) or first<=previous_end:
            raise ValueError('invalid_interval_order_or_length')
        intervals.append((first,end));previous_end=end
    first=intervals[0][1] if intervals and intervals[0][0]==0 else 0
    end=intervals[-1][0] if intervals and intervals[-1][1]==count else count
    if first>end:first=end=0  # Entire clip low-energy; there is no central span.
    span=end-first;flags=('full_scale_peak_not_proof_of_clipping',) if peak==1 else ()
    def result(status,reason,pauses=(),total=None,fraction=None):
        return PauseAssessment(profile,status,reason,count,first,end,span/rate,tuple(pauses),
            len(pauses) if total is not None else None,total,fraction,flags)
    if peak<profile.minimum_peak or rms<profile.minimum_global_rms:
        return result('insufficient_evidence','low_signal_level')
    if span<profile.minimum_central_seconds*rate:
        return result('insufficient_evidence','central_span_too_short')
    pauses=tuple(PauseInterval(a,b,a/rate,b/rate) for a,b in intervals
        if a>0 and b<count and b-a>=round(profile.long_pause_seconds*rate))
    total=sum(p.end_sample-p.first_sample for p in pauses)
    # Exact 15% boundary without binary-float comparison.
    signal=len(pauses)>=profile.minimum_long_pauses and total*100>=profile.minimum_fraction_percent*span
    return result('signal' if signal else 'no_signal',
        'frequent_internal_low_energy_pauses' if signal else 'below_profile_criteria',pauses,total,total/span)
