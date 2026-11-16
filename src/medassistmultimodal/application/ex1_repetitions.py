"""Análise experimental de intervalos conhecidos; não detecta repetições nem alertas."""
from collections import Counter
from dataclasses import asdict, dataclass
import math
from typing import Protocol

from medassistmultimodal.domain.rehabilitation import CoordinateSpace, measure_rehabilitation


@dataclass(frozen=True)
class Ex1Config:
    version: str = 'ex1-world-v1'
    min_visibility: float = 0.5
    min_coverage: float = 0.8
    elbow_min_degrees: float = 150.0
    arm_peak_min_degrees: float = 80.0
    bent_fraction: float = 0.2
    fps: float = 30.0
    camera: int = 1

    def __post_init__(self):
        for name in ('min_visibility', 'min_coverage', 'bent_fraction'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
                raise ValueError(name)
        for name in ('elbow_min_degrees', 'arm_peak_min_degrees'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 180:
                raise ValueError(name)
        if isinstance(self.fps, bool) or not isinstance(self.fps, (int, float)) or not math.isfinite(self.fps) or self.fps <= 0:
            raise ValueError('fps')
        if type(self.camera) is not int or self.camera != 1 or not isinstance(self.version, str) or not self.version.strip():
            raise ValueError('Perfil v1 exige camera 1 e versão')


class PoseSequence(Protocol):
    def __len__(self) -> int: ...
    def frame(self, index: int): ...


def analyze_repetition(sequence: PoseSequence, first: int, last: int, *,
                       evidence_ref: str, config: Ex1Config, camera: int = 1) -> dict:
    """Extremos inclusivos; ausência não vira zero nem é interpolada."""
    if type(first) is not int or type(last) is not int or first < 0 or last < first:
        raise ValueError('Intervalo inválido')
    if not isinstance(config, Ex1Config) or not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise ValueError('Configuração/evidência obrigatória')
    samples = []; reasons = Counter()
    supported = type(camera) is int and camera == config.camera
    for index in range(first, min(last + 1, len(sequence))):
        frame = sequence.frame(index)
        if not supported:
            reasons['unsupported_camera'] += 1
            continue
        if frame.coordinate_space is not CoordinateSpace.WORLD_3D:
            reasons[frame.reason or 'world_3d_required'] += 1
            continue
        measures = measure_rehabilitation(dict(frame.landmarks), space=CoordinateSpace.WORLD_3D,
                                          min_visibility=config.min_visibility)
        values = {m.name: m.value_degrees for m in measures[:2]}
        for m in measures[:2]:
            if m.reason: reasons[m.reason] += 1
        samples.append({'frame': index, 'seconds': index / config.fps, **values})
    expected = last - first + 1
    missing = expected - max(0, min(last + 1, len(sequence)) - first)
    if missing: reasons['out_of_range'] += missing
    rules = []
    for name, metric in [('bent_elbow_proxy', 'right_elbow'), ('low_elevation_proxy', 'right_arm_trunk')]:
        valid = [s for s in samples if s[metric] is not None]
        coverage = len(valid) / expected
        available = supported and coverage >= config.min_coverage and bool(valid)
        if name == 'bent_elbow_proxy':
            hits = [s for s in valid if s[metric] < config.elbow_min_degrees]
            value = len(hits) / len(valid) if valid else None
            deviation = value is not None and value >= config.bent_fraction
            witness = min(valid, key=lambda s: s[metric]) if valid else None
        else:
            witness = max(valid, key=lambda s: s[metric]) if valid else None
            value = witness[metric] if witness else None
            deviation = value is not None and value < config.arm_peak_min_degrees
        rules.append({'name': name, 'status': ('deviation' if deviation else 'no_deviation') if available else 'not_analyzable',
                      'coverage': coverage, 'value': value if available else None,
                      'evidence_frame': witness['frame'] if available else None,
                      'evidence_seconds': witness['seconds'] if available else None,
                      'reason': None if available else ('unsupported_camera' if not supported else 'insufficient_quality_coverage')})
    return {'first_frame': first, 'last_frame': last, 'expected_frames': expected,
            'first_seconds': first / config.fps, 'last_seconds': last / config.fps,
            'evidence_ref': evidence_ref, 'config': asdict(config), 'rules': rules,
            'quality_reasons': dict(reasons), 'samples': samples,
            'trunk_status': 'not_analyzable_missing_vertical_reference',
            'confidence': None, 'review_status': 'pending_review', 'clinical_validation': False,
            'overall_correctness': None}
