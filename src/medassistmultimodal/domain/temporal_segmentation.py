"""Ciclos temporais exploratórios sobre braço–tronco utilizável, sem anotações."""
from dataclasses import dataclass
from enum import StrEnum

from .temporal_quality import QualitySeries,QualityProfile,QualityState,CheckedFrame


@dataclass(frozen=True, slots=True)
class SegmentationProfile:
    version: str = 'day10-cycle-segmentation-v1'
    fps: float = 30.0
    low_degrees: float = 30.0
    high_degrees: float = 60.0
    confirmation_frames: int = 3
    min_duration_frames: int = 15
    max_duration_frames: int = 450

    def __post_init__(self):
        if not isinstance(self.version,str) or not self.version or self.version!=self.version.strip():raise ValueError('Versão inválida')
        if isinstance(self.fps,bool) or not isinstance(self.fps,(int,float)) or self.fps!=30:raise ValueError('Perfil exige 30 FPS')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=180 for v in (self.low_degrees,self.high_degrees)):
            raise ValueError('Faixas inválidas')
        if self.low_degrees>=self.high_degrees:raise ValueError('Faixa baixa deve preceder alta')
        if any(type(v) is not int or v<1 for v in (self.confirmation_frames,self.min_duration_frames,self.max_duration_frames)):
            raise ValueError('Contagens positivas obrigatórias')
        if self.min_duration_frames>self.max_duration_frames:raise ValueError('Duração mínima maior que máxima')

    @property
    def grace_frames(self):return self.confirmation_frames-1


class CycleState(StrEnum):
    WAIT_LOW='wait_low'
    READY='ready'
    ACTIVE='active'


@dataclass(frozen=True, slots=True)
class TemporalCycle:
    first_frame: int
    last_frame: int
    confirmed_at_frame: int
    peak_frame: int
    peak_degrees: float

    @property
    def duration_frames(self):return self.last_frame-self.first_frame+1


@dataclass(frozen=True, slots=True)
class CycleNotice:
    reason: str
    frame_index: int
    candidate_first_frame: int | None
    was_active: bool
    original_quality_reason: str | None = None
    quality_flags: tuple[str,...] = ()


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    evidence_ref: str
    profile: SegmentationProfile
    cycles: tuple[TemporalCycle,...]
    notices: tuple[CycleNotice,...]
    input_frames: int
    unavailable_frames: int
    final_state: CycleState


def segment_repetitions(series: QualitySeries, *, profile: SegmentationProfile = SegmentationProfile()) -> SegmentationResult:
    """Sem I/O, referências anotadas, suavização ou preenchimento de gaps."""
    if not isinstance(series,QualitySeries) or not isinstance(profile,SegmentationProfile):raise ValueError('Contratos tipados obrigatórios')
    if not isinstance(series.profile,QualityProfile) or series.profile.fps!=profile.fps:raise ValueError('FPS incompatível')
    if not isinstance(series.evidence_ref,str) or not series.evidence_ref.strip():raise ValueError('Referência obrigatória')
    if any(not isinstance(f,CheckedFrame) for f in series.frames):raise ValueError('Frame de qualidade obrigatório')
    if any(b.original.frame_index!=a.original.frame_index+1 for a,b in zip(series.frames,series.frames[1:])):
        raise ValueError('Série deve manter índices consecutivos')
    for frame in series.frames:
        angle=frame.right_arm_trunk
        if not isinstance(angle.state,QualityState):raise ValueError('Estado de qualidade inválido')
        if angle.state is QualityState.ACCEPTED:
            value=angle.usable_degrees
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=180 or value!=angle.original.degrees:
                raise ValueError('Medida utilizável contraditória')
        elif angle.usable_degrees is not None:raise ValueError('Medida não aceita não pode ser utilizável')
    state=CycleState.WAIT_LOW;low_count=high_count=0;start=return_first=peak_frame=None;peak=None
    cycles=[];notices=[];unavailable=0
    def reset(low_current=False):
        nonlocal state,low_count,high_count,start,return_first,peak_frame,peak
        state=CycleState.READY if low_current and profile.confirmation_frames==1 else CycleState.WAIT_LOW
        low_count=int(low_current);high_count=0;start=return_first=peak_frame=peak=None
    def notice(reason,index,quality_reason=None,flags=()):
        notices.append(CycleNotice(reason,index,start,state is CycleState.ACTIVE,quality_reason,flags))
    for frame in series.frames:
        index=frame.original.frame_index;angle=frame.right_arm_trunk;value=angle.usable_degrees
        if value is None:
            unavailable+=1
            notice('quality_gap' if start is not None else 'quality_unavailable',index,angle.original.reason,angle.technical_flags)
            reset();continue
        low=value<=profile.low_degrees
        if state is CycleState.WAIT_LOW:
            low_count=low_count+1 if low else 0
            if low_count>=profile.confirmation_frames:state=CycleState.READY;low_count=0
            continue
        if state is CycleState.READY and start is None:
            if low:continue
            start=index;peak=value;peak_frame=index;high_count=0
        if value>peak:peak=value;peak_frame=index
        if state is CycleState.READY:
            if low:
                notice('never_reached_high',index);reset(low_current=True);continue
            high_count=high_count+1 if value>=profile.high_degrees else 0
            if high_count>=profile.confirmation_frames:state=CycleState.ACTIVE;low_count=0
        else:
            if low:
                if low_count==0:return_first=index
                low_count+=1
            else:low_count=0;return_first=None
            if low_count>=profile.confirmation_frames:
                duration=return_first-start+1
                if profile.min_duration_frames<=duration<=profile.max_duration_frames:
                    cycles.append(TemporalCycle(start,return_first,index,peak_frame,float(peak)))
                    reset();state=CycleState.READY
                else:
                    notice('too_short' if duration<profile.min_duration_frames else 'duration_exceeded',index)
                    reset(low_current=True)
                continue
        if start is not None and index>=start+profile.max_duration_frames-1+profile.grace_frames:
            notice('duration_exceeded',index);reset(low_current=low)
    if start is not None:notice('incomplete_eof',series.frames[-1].original.frame_index)
    return SegmentationResult(series.evidence_ref,profile,tuple(cycles),tuple(notices),len(series.frames),unavailable,state)
