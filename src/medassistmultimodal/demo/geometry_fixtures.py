"""Posições artificiais fixas; expectativas definidas sem executar a geometria."""
from dataclasses import dataclass
from medassistmultimodal.domain.geometry import Point


@dataclass(frozen=True, slots=True)
class AngleFixture:
    name: str
    first: Point
    vertex: Point
    last: Point
    expected_degrees: float
    source: str = 'synthetic:geometry:v1'


def build_angle_fixtures() -> tuple[AngleFixture, ...]:
    return (
        AngleFixture('same_direction_2d',(1.,0.),(0.,0.),(2.,0.),0.),
        AngleFixture('diagonal_2d',(1.,0.),(0.,0.),(1.,1.),45.),
        AngleFixture('right_angle_2d',(1.,0.),(0.,0.),(0.,1.),90.),
        AngleFixture('obtuse_2d',(1.,0.),(0.,0.),(-1.,1.),135.),
        AngleFixture('opposite_direction_2d',(1.,0.),(0.,0.),(-1.,0.),180.),
        AngleFixture('right_angle_3d',(1.,0.,0.),(0.,0.,0.),(0.,0.,1.),90.),
        AngleFixture('elbow_extended_image',(0.,0.),(0.,1.),(0.,2.),180.),
        AngleFixture('elbow_flexed_image',(0.,0.),(0.,1.),(1.,1.),90.),
        AngleFixture('arm_down_image',(0.,2.),(0.,0.),(0.,1.),0.),
        AngleFixture('arm_side_image',(0.,2.),(0.,0.),(1.,0.),90.),
        AngleFixture('arm_up_image',(0.,2.),(0.,0.),(0.,-1.),180.),
        AngleFixture('trunk_upright_image',(0.,-1.),(0.,0.),(0.,-2.),0.),
        AngleFixture('trunk_tilted_image',(0.,-1.),(0.,0.),(1.,-1.),45.),
    )
