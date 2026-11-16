"""Experimental low-energy pauses, not speech/respiration or medical classification."""
from dataclasses import dataclass
import math

from .audio_features import AudioFeatures,LowEnergyInterval


@dataclass(frozen=True,slots=True)
class PauseProfile:
    version: str = 'internal-pauses-v1'
    min_duration_seconds: int = 5
    max_duration_seconds: int = 60
    min_peak: float = .05
    min_rms: float = .01
    min_central_seconds: int = 3
    long_pause_seconds: float = .6
    min_long_pauses: int = 3
    min_fraction_percent: int = 15


@dataclass(frozen=True,slots=True)
class PauseInterval:
    first_sample: int
    last_sample_exclusive: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float


@dataclass(frozen=True,slots=True)
class PauseAssessment:
    profile: PauseProfile
    status: str
    reason: str
    sample_rate_hz: int
    sample_count: int
    analysis_first_sample: int | None
    analysis_last_sample_exclusive: int | None
    central_duration_seconds: float | None
    long_pause_count: int | None
    long_pause_samples: int | None
    long_pause_fraction: float | None
    long_pauses: tuple[PauseInterval,...]
    confidence: None = None
    clinical_validation: bool = False
    medical_condition_inferred: bool = False


def _number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Finite number required')
    return value


def detect_internal_pauses(features:AudioFeatures) -> PauseAssessment:
    """Validate fixed energy profile, exclude edge intervals; compare thresholds in samples."""
    if not isinstance(features,AudioFeatures):raise ValueError('Typed features required')
    if features.version!='energy-descriptors-v1':raise ValueError('Unsupported features')
    rate=features.sample_rate_hz;n=features.sample_count;profile=PauseProfile()
    if type(rate) is not int or rate!=16000 or type(n) is not int or n<=0:
        raise ValueError('16000 Hz and positive integer sample count required')
    if not math.isclose(_number(features.duration_seconds),n/rate,rel_tol=0,abs_tol=1e-9):
        raise ValueError('Inconsistent duration')
    if not profile.min_duration_seconds*rate<=n<=profile.max_duration_seconds*rate:
        raise ValueError('Unsupported duration')
    for value,expected in ((features.energy_window_seconds,.02),(features.low_energy_rms_threshold,.01),
                           (features.minimum_low_energy_seconds,.2)):
        if _number(value)!=expected:raise ValueError('Unsupported energy profile')
    rms=_number(features.rms_normalized);peak=_number(features.peak_abs_normalized)
    if not (0<=rms<=1 and 0<=peak<=1) or rms>peak+1e-12:raise ValueError('Invalid amplitude metadata')
    if not isinstance(features.low_energy_intervals,tuple):raise ValueError('Immutable intervals required')
    intervals=[];previous_end=-1
    for interval in features.low_energy_intervals:
        if not isinstance(interval,LowEnergyInterval):raise ValueError('Typed interval required')
        endpoints=[]
        for seconds in (interval.start_seconds,interval.end_seconds):
            scaled=_number(seconds)*rate;index=round(scaled)
            if not math.isclose(scaled,index,rel_tol=0,abs_tol=1e-6):raise ValueError('Interval not on sample grid')
            endpoints.append(index)
        first,last=endpoints
        if (not 0<=first<last<=n or first<=previous_end or last-first<3200
            or first%320 or (last!=n and last%320)):
            raise ValueError('Invalid/overlapping/unmerged energy intervals')
        intervals.append((first,last));previous_end=last
    def result(status,reason,first=None,last=None,long=()):
        available=first is not None and last is not None and last>first
        count=sum(b-a for a,b in long)
        return PauseAssessment(profile,status,reason,rate,n,first,last,
            (last-first)/rate if available else None,len(long) if available else None,
            count if available else None,count/(last-first) if available else None,
            tuple(PauseInterval(a,b,a/rate,b/rate,(b-a)/rate) for a,b in long))
    if peak<profile.min_peak or rms<profile.min_rms:
        return result('insufficient_evidence','low_signal')
    first=intervals[0][1] if intervals and intervals[0][0]==0 else 0
    last=intervals[-1][0] if intervals and intervals[-1][1]==n else n
    if last-first<profile.min_central_seconds*rate:
        return result('insufficient_evidence','central_interval_too_short')
    long=tuple((a,b) for a,b in intervals if first<a<b<last and b-a>=9600)
    count=sum(b-a for a,b in long)
    signal=len(long)>=profile.min_long_pauses and count*100>=(last-first)*profile.min_fraction_percent
    return result('signal' if signal else 'no_signal',
        'frequent_internal_low_energy_intervals' if signal else 'profile_criteria_not_met',first,last,long)
