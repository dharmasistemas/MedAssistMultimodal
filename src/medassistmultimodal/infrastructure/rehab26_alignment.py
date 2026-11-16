"""Adaptador de presença estrutural; sem limiar de visibilidade ou conversão 2D."""
import math
from medassistmultimodal.domain.temporal_alignment import FrameAvailability
from .rehab26_landmarks import LandmarkSequence


def inspect_frame_availability(sequence: LandmarkSequence) -> tuple[FrameAvailability,...]:
    result=[]
    for index in range(len(sequence)):
        frame=sequence.raw_frame(index)
        if frame.all_zero_pose:state=FrameAvailability.ZERO_POSE
        elif any(not all(math.isfinite(v) for v in values) or not 0<=values[3]<=1 for values in frame.values):
            state=FrameAvailability.INVALID
        else:state=FrameAvailability.VALID
        result.append(state)
    return tuple(result)
