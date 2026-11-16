"""Geometria euclidiana experimental, sem dependência de mídia ou limiares clínicos."""
from collections.abc import Sequence
import math

Point = tuple[float, float] | tuple[float, float, float]


class GeometryError(ValueError):
    """Entrada sem geometria válida; não converter em ângulo zero."""


def _coordinates(value: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(value, (tuple, list)) or len(value) not in (2, 3):
        raise GeometryError('Esperadas duas ou três coordenadas')
    result=[]
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            raise GeometryError('Coordenadas devem ser numéricas e finitas')
        try: number=float(coordinate)
        except (OverflowError, ValueError):
            raise GeometryError('Coordenada não representável') from None
        if not math.isfinite(number):
            raise GeometryError('Coordenadas devem ser finitas')
        result.append(number)
    return tuple(result)


def _unit(vector: tuple[float, ...]) -> tuple[float, ...]:
    scale=max(abs(coordinate) for coordinate in vector)
    if scale==0:
        raise GeometryError('Vetor nulo: direção indefinida')
    scaled=tuple(coordinate/scale for coordinate in vector)
    length=math.hypot(*scaled)
    return tuple(coordinate/length for coordinate in scaled)


def angle_between_vectors(first: Point, second: Point) -> float:
    """Ângulo não orientado em graus [0,180], sem informação sobre plano ou lado."""
    a,b=_coordinates(first),_coordinates(second)
    if len(a)!=len(b):raise GeometryError('Dimensões incompatíveis')
    a,b=_unit(a),_unit(b)
    # Fórmula de meio ângulo evita perda de precisão de acos perto de 0/180.
    difference=math.hypot(*(x-y for x,y in zip(a,b)))
    addition=math.hypot(*(x+y for x,y in zip(a,b)))
    return math.degrees(2*math.atan2(difference,addition))


def angle_at_points(first: Point, vertex: Point, last: Point) -> float:
    """Ângulo first-vertex-last; vertex é o vértice, em coordenadas homogêneas."""
    a,b,c=_coordinates(first),_coordinates(vertex),_coordinates(last)
    if not len(a)==len(b)==len(c):raise GeometryError('Dimensões incompatíveis')
    ab=tuple(x-y for x,y in zip(a,b))
    cb=tuple(x-y for x,y in zip(c,b))
    if not all(math.isfinite(x) for x in (*ab,*cb)):
        raise GeometryError('Diferença de coordenadas não representável')
    return angle_between_vectors(ab,cb)
