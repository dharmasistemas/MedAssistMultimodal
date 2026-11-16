"""Loader com NPY inventados, sem depender dos arquivos reais ou da rede."""
from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
import tempfile
import unittest

import numpy as np

from medassistmultimodal.infrastructure.rehab26_landmarks import (
    LandmarkSequence,LandmarkLoadError,Representation,ImageUnits,
)
from medassistmultimodal.domain.rehabilitation import CoordinateSpace,measure_rehabilitation


def array():
    data=np.ones((3,33,4),dtype=np.float64)
    data[1]=0.
    for i,point in {11:(-1.,0.,0.),12:(1.,0.,0.),14:(2.,0.,0.),16:(2.,1.,0.),23:(-1.,2.,0.),24:(1.,2.,0.)}.items():
        data[0,i,:3]=point
    return data


class LandmarkSequenceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'fixture.npy'
        np.save(self.path,array(),allow_pickle=False)

    def open(self,**kwargs):
        return LandmarkSequence(self.path,representation=kwargs.pop('representation',Representation.THREE_D),**kwargs)

    def test_shape_safe_raw_copy_and_explicit_close(self):
        digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.open(expected_sha256=digest) as sequence:
            self.assertEqual(sequence.shape,(3,33,4));self.assertEqual(len(sequence),3)
            raw=sequence.raw_frame(0)
            self.assertEqual(raw.frame_index,0);self.assertEqual(len(raw.values),33)
            with self.assertRaises(FrozenInstanceError):raw.frame_index=1
        self.assertEqual(raw.values[12],(1.,0.,0.,1.))
        sequence.close()
        with self.assertRaises(LandmarkLoadError):sequence.raw_frame(0)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),digest)
        # O arquivo pode ser substituído após close no Windows, sem mmap pendente.
        self.path.write_bytes(self.path.read_bytes())

    def test_zero_pose_preserves_indices_and_is_not_valid_at_zero_threshold(self):
        with self.open() as sequence:
            self.assertEqual([sequence.raw_frame(i).frame_index for i in range(len(sequence))],[0,1,2])
            missing=sequence.frame(1)
            self.assertEqual(missing.reason,'all_zero_pose');self.assertEqual(missing.landmarks,())
            self.assertEqual(sequence.frame(2).frame_index,2)

    def test_unknown_2d_does_not_silently_convert(self):
        with self.open(representation=Representation.TWO_D) as sequence:
            self.assertEqual(sequence.frame(0).reason,'coordinate_units_unconfirmed')
            self.assertIsNone(sequence.frame(0).coordinate_space)
            self.assertEqual(sequence.raw_frame(0).values[12][0],1.)

    def test_pixel_and_normalized_2d_profiles(self):
        with self.open(representation=Representation.TWO_D,image_units=ImageUnits.PIXELS,
                       unit_evidence_ref='synthetic:pixels') as sequence:
            frame=sequence.frame(0)
            self.assertEqual(frame.coordinate_space,CoordinateSpace.IMAGE_2D)
            self.assertEqual(dict(frame.landmarks)[12].coordinates,(1.,0.))
        with self.open(representation=Representation.TWO_D,image_units=ImageUnits.NORMALIZED,
                       unit_evidence_ref='synthetic:normalized',image_size=(200,100)) as sequence:
            points=dict(sequence.frame(0).landmarks)
            self.assertEqual(points[12].coordinates,(200.,0.))
            self.assertEqual(points[11].coordinates,(-200.,0.))  # Não recorta coordenada fora da imagem.

    def test_normalized_requires_dimensions_and_evidence(self):
        with self.assertRaises(LandmarkLoadError):self.open(representation=Representation.TWO_D,image_units=ImageUnits.PIXELS)
        with self.open(representation=Representation.TWO_D,image_units=ImageUnits.NORMALIZED,
                       unit_evidence_ref='synthetic:normalized') as sequence:
            self.assertEqual(sequence.frame(0).reason,'missing_image_dimensions')

    def test_world_conversion_works_with_existing_geometry_without_inventing_up(self):
        with self.open() as sequence:
            frame=sequence.frame(0)
            self.assertEqual(frame.status,'ok')
            result=measure_rehabilitation(dict(frame.landmarks),space=frame.coordinate_space,min_visibility=0.5)
            self.assertAlmostEqual(result[0].value_degrees,90.)
            self.assertAlmostEqual(result[1].value_degrees,90.)
            self.assertEqual(result[2].reason,'missing_vertical_reference')

    def test_nonfinite_and_invalid_visibility_are_local_not_deleted_frames(self):
        data=array();data[0,16,0]=np.nan;data[2,12,3]=1.1
        np.save(self.path,data,allow_pickle=False)
        with self.open() as sequence:
            first,last=sequence.frame(0),sequence.frame(2)
            self.assertEqual(first.status,'partial');self.assertEqual(first.invalid_indices,(16,))
            self.assertEqual(last.invalid_indices,(12,));self.assertEqual(len(sequence),3)
            self.assertEqual(first.reason,'invalid_landmarks')
            self.assertNotIn(16,dict(first.landmarks))

    def test_visibility_is_preserved_not_thresholded_by_loader(self):
        data=array();data[0,14,3]=0.2;np.save(self.path,data,allow_pickle=False)
        with self.open() as sequence:
            frame=sequence.frame(0)
            self.assertEqual(frame.status,'ok')
            self.assertEqual(dict(frame.landmarks)[14].visibility,0.2)
            values=measure_rehabilitation(dict(frame.landmarks),space=frame.coordinate_space,min_visibility=0.5)
            self.assertEqual(values[0].reason,'low_visibility')

    def test_index_and_configuration_rejected(self):
        with self.open() as sequence:
            for index in (-1,3,True,1.0):
                with self.subTest(index=index),self.assertRaises(LandmarkLoadError):sequence.raw_frame(index)
        for kwargs in ({'representation':'3d'},{'expected_sha256':'bad'},
                       {'expected_sha256':'0'*64},{'image_size':(100,100)}):
            with self.subTest(kwargs=kwargs),self.assertRaises(LandmarkLoadError):self.open(**kwargs)
        for size in ((0,1),(1,True),(1,),[100,100]):
            with self.subTest(size=size),self.assertRaises(LandmarkLoadError):
                self.open(representation=Representation.TWO_D,image_size=size)

    def test_invalid_arrays_pickle_and_truncated_files_rejected(self):
        cases=[np.ones((3,32,4),dtype=np.float64),np.ones((0,33,4),dtype=np.float64),
               np.ones((3,33,4),dtype=np.float32),np.ones((33,4),dtype=np.float64),
               np.asfortranarray(np.ones((3,33,4),dtype=np.float64)),
               np.full((1,33,4),object(),dtype=object)]
        for data in cases:
            np.save(self.path,data,allow_pickle=True)
            with self.subTest(shape=data.shape,dtype=str(data.dtype)),self.assertRaises(LandmarkLoadError):self.open()
        self.path.write_bytes(b'not an npy')
        with self.assertRaises(LandmarkLoadError):self.open()
        np.save(self.path,array());self.path.write_bytes(self.path.read_bytes()[:-8])
        with self.assertRaises(LandmarkLoadError):self.open()

    def test_missing_private_or_traversal_paths_rejected(self):
        for path in (self.path.parent/'absent.npy',Path('_backup/forbidden.npy'),Path('.git/forbidden.npy'),Path('a/../b.npy')):
            with self.subTest(kind=path.name),self.assertRaises(LandmarkLoadError):
                LandmarkSequence(path,representation=Representation.THREE_D)

    def test_all_invalid_points_remain_one_non_analyzable_frame(self):
        data=array();data[0,:,3]=np.inf;np.save(self.path,data,allow_pickle=False)
        with self.open() as sequence:
            frame=sequence.frame(0)
            self.assertEqual(frame.status,'not_analyzable');self.assertEqual(len(frame.invalid_indices),33)
            self.assertEqual(frame.landmarks,());self.assertEqual(frame.frame_index,0)
