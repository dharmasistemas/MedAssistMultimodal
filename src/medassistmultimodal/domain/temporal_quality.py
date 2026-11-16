"""Qualidade angular exploratória v1; não classifica exercícios ou decide alertas."""
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

MEASURES = ('right_elbow', 'right_arm_trunk')
REQUIRED = {'right_elbow': (12,14,16), 'right_arm_trunk': (24,12,14)}


def _number(value, low, high, label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not low <= value <= high:
        raise ValueError(label)
    return float(value)


def _text(value, label):
    if not isinstance(value,str) or not value or value != value.strip():raise ValueError(label)
    return value


@dataclass(frozen=True, slots=True)
class QualityProfile:
    version: str = 'day10-angular-quality-v1'
    fps: float = 30.0
    min_visibility: float = 0.5
    max_change_degrees: float = 30.0

    def __post_init__(self):
        _text(self.version,'Versão obrigatória')
        if isinstance(self.fps,bool) or not isinstance(self.fps,(int,float)) or self.fps != 30:
            raise ValueError('Este perfil exige 30 FPS')
        _number(self.min_visibility,0,1,'Visibilidade inválida')
        if _number(self.max_change_degrees,0,180,'Limite angular inválido') <= 0:
            raise ValueError('Limite angular deve ser positivo')


@dataclass(frozen=True, slots=True)
class OriginalAngle:
    degrees: float | None
    reason: str | None = None

    def __post_init__(self):
        if self.degrees is None:
            _text(self.reason,'Ângulo ausente exige motivo original')
        else:
            _number(self.degrees,0,180,'Ângulo deve ser finito em [0,180]')
            if self.reason is not None:raise ValueError('Ângulo válido não deve ter motivo de ausência')


@dataclass(frozen=True, slots=True)
class OriginalFrame:
    frame_index: int
    right_elbow: OriginalAngle
    right_arm_trunk: OriginalAngle
    visibility: tuple[tuple[int,float | None], ...]

    def __post_init__(self):
        if type(self.frame_index) is not int or self.frame_index < 0:raise ValueError('Índice inválido')
        if not all(isinstance(getattr(self,n),OriginalAngle) for n in MEASURES):raise ValueError('Medidas tipadas obrigatórias')
        if not isinstance(self.visibility,tuple):raise ValueError('Visibilidade deve ser tupla imutável')
        indices=[]
        for item in self.visibility:
            if not isinstance(item,tuple) or len(item)!=2 or type(item[0]) is not int:
                raise ValueError('Par índice/visibilidade inválido')
            indices.append(item[0])
            if item[1] is not None:_number(item[1],0,1,'Visibilidade inválida')
        if sorted(indices)!=[12,14,16,24]:raise ValueError('Exigir pontos 12/14/16/24, sem duplicatas')


class QualityState(StrEnum):
    ACCEPTED = 'accepted'
    SUSPECT = 'suspect'
    UNAVAILABLE = 'unavailable'


@dataclass(frozen=True, slots=True)
class AngularJump:
    measure: str
    first_frame: int
    second_frame: int
    delta_degrees: float


@dataclass(frozen=True, slots=True)
class CheckedAngle:
    original: OriginalAngle
    usable_degrees: float | None
    state: QualityState
    technical_flags: tuple[str, ...]
    jump_pairs: tuple[AngularJump, ...]


@dataclass(frozen=True, slots=True)
class CheckedFrame:
    original: OriginalFrame
    nominal_seconds: float
    right_elbow: CheckedAngle
    right_arm_trunk: CheckedAngle


@dataclass(frozen=True, slots=True)
class QualitySeries:
    evidence_ref: str
    profile: QualityProfile
    frames: tuple[CheckedFrame, ...]
    jumps: tuple[AngularJump, ...]


def assess_angular_quality(frames: Iterable[OriginalFrame], *, evidence_ref: str,
                           profile: QualityProfile = QualityProfile()) -> QualitySeries:
    """Batch: comparar originais primeiro, aplicar máscara depois; nenhum I/O."""
    _text(evidence_ref,'Referência de evidência obrigatória')
    if not isinstance(profile,QualityProfile):raise ValueError('Perfil tipado obrigatório')
    originals=tuple(frames)
    if any(not isinstance(f,OriginalFrame) for f in originals):raise ValueError('Frames tipados obrigatórios')
    if any(b.frame_index != a.frame_index+1 for a,b in zip(originals,originals[1:])):
        raise ValueError('Índices devem ser consecutivos; representar ausência explicitamente')
    # Não aceitar que o chamador rotule como válida uma medida com visibilidade insuficiente.
    for frame in originals:
        visibility=dict(frame.visibility)
        for name in MEASURES:
            if getattr(frame,name).degrees is not None and any(visibility[i] is None or visibility[i] < profile.min_visibility for i in REQUIRED[name]):
                raise ValueError('Medida originalmente válida contradiz o filtro de visibilidade')
    associations={};jumps=[]
    for a,b in zip(originals,originals[1:]):
        for name in MEASURES:
            av=getattr(a,name).degrees;bv=getattr(b,name).degrees
            if av is None or bv is None:continue
            delta=abs(bv-av)
            if delta > profile.max_change_degrees:
                jump=AngularJump(name,a.frame_index,b.frame_index,float(delta));jumps.append(jump)
                for index in (a.frame_index,b.frame_index):associations.setdefault((index,name),[]).append(jump)
    checked=[]
    for frame in originals:
        values={}
        for name in MEASURES:
            original=getattr(frame,name);pairs=tuple(associations.get((frame.frame_index,name),()))
            state=(QualityState.UNAVAILABLE if original.degrees is None else
                   (QualityState.SUSPECT if pairs else QualityState.ACCEPTED))
            values[name]=CheckedAngle(original,original.degrees if state is QualityState.ACCEPTED else None,
                state,('angular_discontinuity',) if pairs else (),pairs)
        checked.append(CheckedFrame(frame,frame.frame_index/profile.fps,**values))
    return QualitySeries(evidence_ref,profile,tuple(checked),tuple(jumps))
