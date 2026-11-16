"""Cobertura de intervalos inclusivos; não remove frames nem decide alertas."""
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class FrameAvailability(StrEnum):
    VALID = 'valid'
    ZERO_POSE = 'all_zero_pose'
    INVALID = 'invalid_data'


@dataclass(frozen=True, slots=True)
class SegmentCoverage:
    first_frame: int
    last_frame: int
    expected_frames: int
    in_range_frames: int
    out_of_range_frames: int
    zero_pose_frames: int
    invalid_data_frames: int
    usable_frames: int
    temporal_coverage: float
    structural_coverage: float
    bounds_status: str
    status: str
    out_of_range_runs: tuple[tuple[int,int], ...]
    zero_pose_runs: tuple[tuple[int,int], ...]
    invalid_data_runs: tuple[tuple[int,int], ...]


def _runs(indices):
    result=[]
    for index in indices:
        if result and index==result[-1][1]+1:result[-1]=(result[-1][0],index)
        else:result.append((index,index))
    return tuple(result)


def assess_segment(first_frame: int, last_frame: int,
                   availability: Sequence[FrameAvailability]) -> SegmentCoverage:
    if type(first_frame) is not int or type(last_frame) is not int or not 0<=first_frame<=last_frame:
        raise ValueError('Intervalo inclusivo não negativo esperado')
    if not isinstance(availability,Sequence) or any(not isinstance(x,FrameAvailability) for x in availability):
        raise ValueError('availability deve conter FrameAvailability')
    expected=last_frame-first_frame+1
    start=first_frame;stop=min(last_frame,len(availability)-1)
    inside=max(0,stop-start+1)
    zero=[];invalid=[]
    for index in range(start,stop+1):
        if availability[index] is FrameAvailability.ZERO_POSE:zero.append(index)
        elif availability[index] is FrameAvailability.INVALID:invalid.append(index)
    usable=inside-len(zero)-len(invalid)
    outside=() if last_frame<len(availability) else ((max(first_frame,len(availability)),last_frame),)
    return SegmentCoverage(first_frame,last_frame,expected,inside,expected-inside,len(zero),len(invalid),usable,
        inside/expected,usable/expected,'contained' if inside==expected else 'partial' if inside else 'outside',
        'complete' if usable==expected else 'partial' if usable else 'unavailable',outside,_runs(zero),_runs(invalid))
