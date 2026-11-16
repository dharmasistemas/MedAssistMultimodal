"""Deterministic experimental vital rules. No IO, reference labels or providers."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from collections.abc import Mapping

UNITS = {'heart_rate': 'bpm', 'spo2': '%', 'systolic': 'mmHg', 'diastolic': 'mmHg'}


@dataclass(frozen=True, slots=True)
class VitalValue:
    value: int | float | None
    quality: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class VitalSample:
    sample_index: int
    timestamp: datetime
    channels: tuple[VitalValue, ...]


@dataclass(frozen=True, slots=True)
class VitalOccurrence:
    rule_id: str
    channel: str
    direction: str
    threshold: float
    unit: str
    first_index: int
    last_index: int
    confirmed_index: int
    first_timestamp: str
    last_timestamp: str
    confirmed_timestamp: str
    values: tuple[int | float, ...]
    duration_seconds: int
    confirmation_latency_seconds: int
    termination: str


@dataclass(frozen=True, slots=True)
class QualityInterval:
    channel: str
    first_index: int
    last_index: int
    quality: str
    reason: str


@dataclass(frozen=True, slots=True)
class ChannelCoverage:
    channel: str
    valid_samples: int
    total_samples: int
    fraction: float


@dataclass(frozen=True, slots=True)
class VitalsResult:
    series_id: str
    source: str
    input_sha256: str
    processor: str
    profile_version: str
    persistence: int
    bounds: tuple[tuple[float | None, float | None], ...]
    occurrences: tuple[VitalOccurrence, ...]
    quality_intervals: tuple[QualityInterval, ...]
    coverage: tuple[ChannelCoverage, ...]
    clinical_validation: bool = False


@dataclass(frozen=True, slots=True)
class VitalsProfile:
    version: str = 'synthetic-vitals-rules-v1'
    persistence: int = 3
    # Channel order is fixed and explicit; None means no bound in that direction.
    bounds: tuple[tuple[float | None, float | None], ...] = ((50, 110), (94, None), (90, 140), (60, 90))

    def __post_init__(self):
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError('profile version required')
        if type(self.persistence) is not int or self.persistence < 1:
            raise ValueError('persistence must be a positive integer')
        if not isinstance(self.bounds, tuple) or len(self.bounds) != 4:
            raise ValueError('four immutable channel bounds required')
        for pair in self.bounds:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError('immutable lower/upper pairs required')
            low, high = pair
            if all(v is None for v in pair) or any(v is not None and not _number(v) for v in pair):
                raise ValueError('finite bounds required')
            if low is not None and high is not None and low >= high:
                raise ValueError('lower must precede upper')


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _time(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be text')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError('timestamp must explicitly use UTC')
    return parsed.astimezone(timezone.utc)


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def validate_vital_series(payload: Mapping) -> tuple[VitalSample, ...]:
    """Reject envelope errors; normalize invalid measurements without imputing values."""
    if not isinstance(payload, Mapping):
        raise ValueError('series must be an object')
    required = {'schema_version': 'synthetic-vitals-v1', 'subject_kind': 'synthetic_patient',
                'source_kind': 'synthetic', 'time_basis': 'fictional_nominal_utc'}
    if any(payload.get(k) != v for k, v in required.items()):
        raise ValueError('unsupported schema, identity or time basis')
    if not isinstance(payload.get('patient_id'), str) or re.fullmatch(r'PAT-[0-9]{3}', payload['patient_id']) is None:
        raise ValueError('synthetic patient required')
    if payload.get('dataset_id') is not None or payload.get('participant_ref') is not None:
        raise ValueError('dataset identity forbidden')
    if any(not _text(payload.get(k)) for k in ('series_id', 'scenario_id', 'source', 'generator_version')):
        raise ValueError('series/source identifiers required')
    if type(payload.get('seed')) is not int or type(payload.get('interval_seconds')) is not int or payload['interval_seconds'] != 1:
        raise ValueError('integer seed and one-second grid required')
    start = _time(payload.get('started_at'))
    samples = payload.get('samples')
    if not isinstance(samples, list) or not samples:
        raise ValueError('nonempty samples list required')
    validated = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping) or type(sample.get('sample_index')) is not int or sample['sample_index'] != index:
            raise ValueError('contiguous sample indices required')
        timestamp = _time(sample.get('timestamp'))
        if timestamp != start + timedelta(seconds=index):
            raise ValueError('timestamp inconsistent with grid')
        channels = []
        for channel, unit in UNITS.items():
            entry = sample.get(channel)
            if not isinstance(entry, Mapping) or entry.get('unit') != unit:
                raise ValueError('channel and explicit unit required')
            if 'value' not in entry:
                raise ValueError('explicit value field required')
            value, state, reason = entry.get('value'), entry.get('quality'), entry.get('reason')
            if state not in ('valid', 'missing', 'invalid'):
                raise ValueError('invalid quality state')
            if state == 'missing':
                if value is not None or not _text(reason):
                    raise ValueError('missing requires null and reason')
            else:
                if not _number(value):
                    raise ValueError('numeric finite non-bool channel required')
                if state == 'invalid' and not _text(reason):
                    raise ValueError('invalid requires reason')
                if state == 'valid':
                    if reason is not None:
                        raise ValueError('valid channel cannot have rejection reason')
                    if channel == 'spo2' and not 0 <= value <= 100:
                        state, reason = 'invalid', 'outside_percentage'
                    elif channel != 'spo2' and value <= 0:
                        state, reason = 'invalid', 'non_positive'
            channels.append(VitalValue(value, state, reason))
        systolic, diastolic = channels[2:]
        if systolic.quality == diastolic.quality == 'valid':
            if systolic.value <= diastolic.value:
                channels[2:] = [VitalValue(v.value, 'invalid', 'invalid_pressure_pair') for v in channels[2:]]
        else:
            for pos in (2, 3):
                if channels[pos].quality == 'valid':
                    channels[pos] = VitalValue(channels[pos].value, 'invalid', 'pressure_pair_unavailable')
        validated.append(VitalSample(index, timestamp, tuple(channels)))
    return tuple(validated)


def analyze_vitals(payload: Mapping, *, input_sha256: str, profile: VitalsProfile = VitalsProfile()) -> VitalsResult:
    """Batch analysis. The caller supplies the hash of the original input bytes."""
    if not isinstance(input_sha256, str) or re.fullmatch('[0-9a-f]{64}', input_sha256) is None:
        raise ValueError('input SHA-256 required')
    if not isinstance(profile, VitalsProfile):
        raise ValueError('VitalsProfile required')
    samples = validate_vital_series(payload)
    occurrences, quality, coverage = [], [], []
    for pos, (channel, unit) in enumerate(UNITS.items()):
        valid = sum(s.channels[pos].quality == 'valid' for s in samples)
        coverage.append(ChannelCoverage(channel, valid, len(samples), valid / len(samples)))
        i = 0
        while i < len(samples):
            value = samples[i].channels[pos]
            if value.quality == 'valid':
                i += 1
                continue
            end = i
            while end + 1 < len(samples) and (samples[end + 1].channels[pos].quality,
                    samples[end + 1].channels[pos].reason) == (value.quality, value.reason):
                end += 1
            quality.append(QualityInterval(channel, i, end, value.quality, value.reason))
            i = end + 1
        for direction, bound in zip(('low', 'high'), profile.bounds[pos]):
            if bound is None:
                continue
            def violates(sample):
                v = sample.channels[pos]
                return v.quality == 'valid' and (v.value < bound if direction == 'low' else v.value > bound)
            i = 0
            while i < len(samples):
                if not violates(samples[i]):
                    i += 1
                    continue
                end = i
                while end + 1 < len(samples) and violates(samples[end + 1]):
                    end += 1
                if end - i + 1 >= profile.persistence:
                    confirmed = i + profile.persistence - 1
                    if end == len(samples) - 1:
                        termination = 'end_of_series'
                    elif samples[end + 1].channels[pos].quality != 'valid':
                        termination = 'quality_gap'
                    else:
                        following = samples[end + 1].channels[pos].value
                        low, high = profile.bounds[pos]
                        opposite = (high is not None and following > high) if direction == 'low' else (low is not None and following < low)
                        termination = 'direction_change' if opposite else 'return_to_range'
                    occurrences.append(VitalOccurrence(f'{channel}_{direction}', channel, direction, bound,
                        unit, i, end, confirmed, samples[i].timestamp.isoformat(),
                        samples[end].timestamp.isoformat(), samples[confirmed].timestamp.isoformat(),
                        tuple(s.channels[pos].value for s in samples[i:end + 1]), end - i + 1,
                        confirmed - i, termination))
                i = end + 1
    return VitalsResult(payload['series_id'], payload['source'], input_sha256, 'vitals-rules-v1',
                        profile.version, profile.persistence, profile.bounds,
                        tuple(occurrences), tuple(quality), tuple(coverage))
