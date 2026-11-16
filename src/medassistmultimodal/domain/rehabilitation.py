"""Medidas geométricas experimentais por frame, sem classificação clínica."""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import math

from .geometry import Point, GeometryError, _coordinates, angle_at_points, angle_between_vectors


class CoordinateSpace(StrEnum):
    IMAGE_2D = 'image_2d'
    WORLD_3D = 'world_3d'


@dataclass(frozen=True, slots=True)
class Landmark:
    coordinates: Point
    visibility: float | None


@dataclass(frozen=True, slots=True)
class Measurement:
    name: str
    value_degrees: float | None
    status: str
    reason: str | None
    required_indices: tuple[int, ...]
    coordinate_space: CoordinateSpace
    min_visibility: float
    reference: str


def _visibility(value) -> float | None:
    if isinstance(value,bool) or not isinstance(value,(int,float)): return None
    try: number=float(value)
    except (OverflowError,ValueError): return None
    return number if math.isfinite(number) and 0<=number<=1 else None


def measure_rehabilitation(landmarks: Mapping[int,Landmark], *, space: CoordinateSpace,
                           min_visibility: float, vertical_up: Point | None = None) -> tuple[Measurement,...]:
    """Entradas já convertidas para uma base/unidade homogênea; não processa mídia."""
    if not isinstance(space,CoordinateSpace): raise ValueError('space deve ser CoordinateSpace')
    threshold=_visibility(min_visibility)
    if threshold is None: raise ValueError('min_visibility deve ser número finito em [0,1]')
    if not isinstance(landmarks,Mapping): raise ValueError('landmarks deve ser mapeamento por índice')
    dimensions=2 if space is CoordinateSpace.IMAGE_2D else 3
    reference='image_up' if space is CoordinateSpace.IMAGE_2D and vertical_up is None else 'provided_up'
    def measure(name,indices,operation,ref='landmark_vectors'):
        def result(value=None,reason=None):
            return Measurement(name,value,'ok' if reason is None else 'not_analyzable',reason,
                               indices,space,threshold,ref)
        points=[]
        for index in indices:
            landmark=landmarks.get(index)
            if landmark is None:return result(reason='missing_landmark')
            if not isinstance(landmark,Landmark):return result(reason='invalid_landmark')
            try: point=_coordinates(landmark.coordinates)
            except GeometryError:return result(reason='invalid_coordinates')
            if len(point)!=dimensions:return result(reason='dimension_mismatch')
            if landmark.visibility is None:return result(reason='missing_visibility')
            visible=_visibility(landmark.visibility)
            if visible is None:return result(reason='invalid_visibility')
            if visible<threshold:return result(reason='low_visibility')
            points.append(point)
        try: return result(operation(points))
        except _ReferenceError as error:return result(reason=str(error))
        except GeometryError:return result(reason='degenerate_geometry')
    def trunk(points):
        if vertical_up is None and space is CoordinateSpace.WORLD_3D:
            raise _ReferenceError('missing_vertical_reference')
        up=(0.,-1.) if vertical_up is None else vertical_up
        try:
            up=_coordinates(up)
            if len(up)!=dimensions:raise GeometryError('dimensão')
            angle_between_vectors(up,up)  # Exige referência finita e não nula.
        except GeometryError:raise _ReferenceError('invalid_vertical_reference') from None
        left_shoulder,right_shoulder,left_hip,right_hip=points
        # Metade antes da soma evita overflow no ponto médio de coordenadas finitas.
        shoulders=tuple(a/2+b/2 for a,b in zip(left_shoulder,right_shoulder))
        hips=tuple(a/2+b/2 for a,b in zip(left_hip,right_hip))
        direction=tuple(a-b for a,b in zip(shoulders,hips))
        return angle_between_vectors(direction,up)
    return (
        measure('right_elbow',(12,14,16),lambda p:angle_at_points(*p)),
        measure('right_arm_trunk',(24,12,14),lambda p:angle_at_points(*p)),
        measure('trunk_inclination',(11,12,23,24),trunk,reference),
    )


class _ReferenceError(ValueError):
    pass
