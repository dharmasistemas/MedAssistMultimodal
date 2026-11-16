"""Medidas/qualidade com coordenadas inventadas; sem nomes, mídia ou Azure."""
from dataclasses import replace
from io import StringIO
from contextlib import redirect_stdout
import json
import math
import unittest

from medassistmultimodal.domain.rehabilitation import Landmark,CoordinateSpace,measure_rehabilitation
from medassistmultimodal.demo.rehabilitation import synthetic_pose,build_demo_results,main


class RehabilitationTests(unittest.TestCase):
    def measure(self,pose=None,**kwargs):
        return measure_rehabilitation(synthetic_pose() if pose is None else pose,
            space=kwargs.pop('space',CoordinateSpace.IMAGE_2D),min_visibility=kwargs.pop('min_visibility',0.5),**kwargs)

    def test_known_elbow_arm_and_upright_trunk(self):
        values=self.measure()
        for result,expected in zip(values,(90.,90.,0.)):
            self.assertEqual(result.status,'ok')
            self.assertAlmostEqual(result.value_degrees,expected)
            self.assertIsNone(result.reason)
        self.assertEqual(values[2].reference,'image_up')

    def test_extended_elbow_and_arm_down_up(self):
        pose=synthetic_pose();pose[14]=Landmark((1.,1.),1.);pose[16]=Landmark((1.,2.),1.)
        values=self.measure(pose)
        self.assertAlmostEqual(values[0].value_degrees,180.)
        self.assertAlmostEqual(values[1].value_degrees,0.)
        pose[14]=Landmark((1.,-1.),1.);pose[16]=Landmark((1.,-2.),1.)
        self.assertAlmostEqual(self.measure(pose)[1].value_degrees,180.)

    def test_midpoints_and_tilted_trunk(self):
        pose=synthetic_pose()
        pose[11]=Landmark((1.,0.),1.);pose[12]=Landmark((3.,0.),1.)
        self.assertAlmostEqual(self.measure(pose)[2].value_degrees,45.)

    def test_low_visibility_is_local_to_required_points(self):
        pose=synthetic_pose();pose[14]=replace(pose[14],visibility=0.49)
        values=self.measure(pose)
        self.assertEqual([v.reason for v in values],['low_visibility','low_visibility',None])
        self.assertIsNone(values[0].value_degrees)
        self.assertEqual(values[2].status,'ok')

    def test_visibility_threshold_inclusive_and_missing_or_invalid(self):
        pose=synthetic_pose();pose[16]=replace(pose[16],visibility=0.5)
        self.assertEqual(self.measure(pose)[0].status,'ok')
        for visibility,reason in [(None,'missing_visibility'),(-1.,'invalid_visibility'),
                                  (1.01,'invalid_visibility'),(float('nan'),'invalid_visibility'),
                                  (True,'invalid_visibility')]:
            pose[16]=replace(pose[16],visibility=visibility)
            with self.subTest(visibility=visibility):self.assertEqual(self.measure(pose)[0].reason,reason)

    def test_missing_points_and_invalid_coordinates(self):
        pose=synthetic_pose();del pose[16]
        values=self.measure(pose)
        self.assertEqual([v.reason for v in values],['missing_landmark',None,None])
        pose[16]=Landmark((float('inf'),0.),1.)
        self.assertEqual(self.measure(pose)[0].reason,'invalid_coordinates')
        pose[16]=object()
        self.assertEqual(self.measure(pose)[0].reason,'invalid_landmark')
        self.assertTrue(all(v.reason=='missing_landmark' for v in self.measure({})))

    def test_degenerate_geometry_is_not_zero(self):
        pose=synthetic_pose();pose[16]=pose[14]
        value=self.measure(pose)[0]
        self.assertEqual(value.reason,'degenerate_geometry')
        self.assertIsNone(value.value_degrees)
        pose=synthetic_pose();pose[23]=pose[11];pose[24]=pose[12]
        self.assertEqual(self.measure(pose)[2].reason,'degenerate_geometry')

    def test_3d_requires_explicit_reference_only_for_trunk(self):
        pose={i:Landmark((*p.coordinates,0.),p.visibility) for i,p in synthetic_pose().items()}
        values=self.measure(pose,space=CoordinateSpace.WORLD_3D)
        self.assertEqual([v.reason for v in values],[None,None,'missing_vertical_reference'])
        values=self.measure(pose,space=CoordinateSpace.WORLD_3D,vertical_up=(0.,-1.,0.))
        self.assertAlmostEqual(values[2].value_degrees,0.)
        self.assertEqual(values[2].reference,'provided_up')

    def test_bad_reference_and_mixed_dimensions(self):
        for up in ((0.,0.),(0.,-1.,0.),(float('nan'),0.)):
            with self.subTest(up=up):self.assertEqual(self.measure(vertical_up=up)[2].reason,'invalid_vertical_reference')
        pose=synthetic_pose();pose[16]=Landmark((1.,0.,0.),1.)
        self.assertEqual(self.measure(pose)[0].reason,'dimension_mismatch')
        self.assertEqual(self.measure(pose)[1].status,'ok')

    def test_invalid_configuration_is_not_data_abstention(self):
        for value in (-1.,1.1,None,True,float('inf')):
            with self.subTest(value=value),self.assertRaises(ValueError):self.measure(min_visibility=value)
        with self.assertRaises(ValueError):self.measure(space='image_2d')
        with self.assertRaises(ValueError):measure_rehabilitation(None,space=CoordinateSpace.IMAGE_2D,min_visibility=0.5)

    def test_uniform_scale_translation_and_input_not_mutated(self):
        pose=synthetic_pose();original=dict(pose)
        transformed={i:Landmark(tuple(3*x+10 for x in p.coordinates),p.visibility) for i,p in pose.items()}
        for first,second in zip(self.measure(pose),self.measure(transformed)):
            self.assertAlmostEqual(first.value_degrees,second.value_degrees)
        self.assertEqual(pose,original)

    def test_demo_is_reproducible_and_json_safe(self):
        self.assertEqual(build_demo_results(),build_demo_results())
        out=StringIO()
        with redirect_stdout(out):self.assertEqual(main(),0)
        payload=json.loads(out.getvalue())
        self.assertFalse(payload['clinical_validation'])
        self.assertEqual(len(payload['cases']),3)
        self.assertIsNone(payload['cases'][1]['measurements'][0]['value_degrees'])
