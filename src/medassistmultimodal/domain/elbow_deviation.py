"""Fixed experimental Ex1 elbow rule on original world-3D measurements, no IO."""
from dataclasses import dataclass

from .temporal_quality import OriginalFrame


@dataclass(frozen=True, slots=True)
class ElbowDeviation:
    profile: str
    first_frame: int
    last_frame: int
    expected_frames: int
    valid_frames: int
    bent_frames: int
    coverage: float
    bent_fraction: float | None
    status: str
    evidence_frame: int | None
    evidence_seconds: float | None
    minimum_degrees: float | None
    reason: str | None
    min_visibility: float = 0.5
    min_coverage: float = 0.8
    elbow_min_degrees: float = 150.0
    fraction_threshold: float = 0.2
    confidence: None = None
    clinical_validation: bool = False
    overall_correctness: None = None


def detect_elbow_deviation(frames, first, last):
    """Missing indices count against coverage; angles <150, fraction >=.2, coverage >=.8."""
    if type(first) is not int or type(last) is not int or not 0 <= first <= last:
        raise ValueError('Invalid interval')
    originals = tuple(frames)
    if any(not isinstance(f, OriginalFrame) for f in originals):
        raise ValueError('Typed original frames required')
    indices = [f.frame_index for f in originals]
    if indices != sorted(set(indices)) or any(not first <= i <= last for i in indices):
        raise ValueError('Invalid frame indices')
    valid = []
    for f in originals:
        visibility = dict(f.visibility)
        if f.right_elbow.degrees is not None:
            if any(visibility[i] is None or visibility[i] < .5 for i in (12, 14, 16)):
                raise ValueError('Angle contradicts visibility')
            valid.append(f)
    expected = last - first + 1
    coverage = len(valid) / expected
    hits = sum(f.right_elbow.degrees < 150 for f in valid)
    available = bool(valid) and coverage >= .8
    fraction = hits / len(valid) if available else None
    witness = min(valid, key=lambda f: f.right_elbow.degrees) if available else None
    return ElbowDeviation('ex1-world-v1/bent_elbow_proxy', first, last, expected,
        len(valid), hits, coverage, fraction,
        ('deviation' if fraction >= .2 else 'no_deviation') if available else 'not_analyzable',
        witness.frame_index if witness else None, witness.frame_index / 30 if witness else None,
        witness.right_elbow.degrees if witness else None,
        None if available else 'insufficient_quality_coverage')
