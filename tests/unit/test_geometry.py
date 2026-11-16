"""Ângulos de referência e propriedades geométricas, sem dados reais."""
from dataclasses import FrozenInstanceError
import math
import unittest

from medassistmultimodal.domain.geometry import GeometryError, angle_at_points, angle_between_vectors
from medassistmultimodal.demo.geometry_fixtures import build_angle_fixtures


class GeometryTests(unittest.TestCase):
    def test_known_synthetic_positions(self):
        for case in build_angle_fixtures():
            with self.subTest(case=case.name):
                self.assertAlmostEqual(angle_at_points(case.first,case.vertex,case.last),case.expected_degrees,places=10)

    def test_fixture_reproducibility_and_immutability(self):
        first,second=build_angle_fixtures(),build_angle_fixtures()
        self.assertEqual(first,second)
        self.assertEqual(len({case.name for case in first}),len(first))
        self.assertTrue(all(case.source=='synthetic:geometry:v1' for case in first))
        with self.assertRaises(FrozenInstanceError):first[0].expected_degrees=10

    def test_translation_and_uniform_scaling_preserve_angles(self):
        for scale in (0.001,2.,-3.):
            for case in build_angle_fixtures():
                def transform(point):return tuple(scale*x+5 for x in point)
                with self.subTest(scale=scale,case=case.name):
                    self.assertAlmostEqual(angle_at_points(transform(case.first),transform(case.vertex),
                                                          transform(case.last)),case.expected_degrees,places=8)

    def test_rotated_and_reflected_vectors(self):
        self.assertAlmostEqual(angle_between_vectors((1.,1.),(-1.,1.)),90.)
        self.assertAlmostEqual(angle_between_vectors((-1.,-1.),(1.,-1.)),90.)
        self.assertAlmostEqual(angle_between_vectors((0.,1.,0.),(0.,0.,-1.)),90.)

    def test_extreme_finite_magnitudes_do_not_overflow_or_underflow(self):
        for magnitude in (1e308,1e-308):
            with self.subTest(magnitude=magnitude):
                self.assertAlmostEqual(angle_between_vectors((magnitude,0.),(0.,magnitude)),90.)
                self.assertAlmostEqual(angle_between_vectors((magnitude,magnitude,magnitude),
                                                             (-magnitude,-magnitude,-magnitude)),180.)

    def test_small_angle_and_nearly_opposite(self):
        expected=math.degrees(math.atan(1e-12))
        self.assertAlmostEqual(angle_between_vectors((1.,0.),(1.,1e-12)),expected,delta=1e-20)
        self.assertAlmostEqual(angle_between_vectors((1.,0.),(-1.,1e-12)),180.-expected,places=10)

    def test_zero_vectors_and_coincident_points_rejected(self):
        for first,second in [((0.,0.),(1.,0.)),((1.,0.,0.),(0.,0.,0.))]:
            with self.subTest(first=first),self.assertRaises(GeometryError):angle_between_vectors(first,second)
        for points in [((0.,0.),(0.,0.),(1.,0.)),((1.,0.),(0.,0.),(0.,0.))]:
            with self.subTest(points=points),self.assertRaises(GeometryError):angle_at_points(*points)

    def test_invalid_dimensions_types_and_nonfinite_values(self):
        for point in (None,'12',(1.,),(1.,2.,3.,4.),(True,1.),('1',2.),
                      (float('nan'),0.),(float('inf'),0.),(10**1000,0.)):
            with self.subTest(point_type=type(point).__name__),self.assertRaises(GeometryError):
                angle_between_vectors(point,(1.,0.))
        with self.assertRaises(GeometryError):angle_between_vectors((1.,0.),(1.,0.,0.))
        with self.assertRaises(GeometryError):angle_at_points((1.,0.),(0.,0.),(1.,0.,0.))

    def test_unrepresentable_point_differences_are_controlled(self):
        with self.assertRaises(GeometryError):
            angle_at_points((1e308,0.),(-1e308,0.),(0.,1.))

    def test_angle_has_no_direction_or_clinical_classification(self):
        clockwise=angle_between_vectors((1.,0.),(0.,-1.))
        counterclockwise=angle_between_vectors((1.,0.),(0.,1.))
        self.assertEqual(clockwise,counterclockwise)
        self.assertIsInstance(clockwise,float)
