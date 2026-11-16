"""Intervalos inventados, sem dados reais nem pipeline de vídeo."""
from pathlib import Path
import tempfile
import unittest
import numpy as np

from medassistmultimodal.domain.temporal_alignment import FrameAvailability as F,assess_segment
from medassistmultimodal.infrastructure.rehab26_alignment import inspect_frame_availability
from medassistmultimodal.infrastructure.rehab26_landmarks import LandmarkSequence,Representation


class TemporalAlignmentTests(unittest.TestCase):
    def test_full_single_frame_and_inclusive_last(self):
        full=assess_segment(1,3,(F.VALID,)*4)
        self.assertEqual(full.expected_frames,3);self.assertEqual(full.usable_frames,3)
        self.assertEqual(full.status,'complete');self.assertEqual(full.temporal_coverage,1.)
        one=assess_segment(3,3,(F.VALID,)*4)
        self.assertEqual(one.expected_frames,1);self.assertEqual(one.status,'complete')

    def test_trailing_frames_missing_are_not_silently_truncated(self):
        result=assess_segment(2,5,(F.VALID,)*4)
        self.assertEqual((result.expected_frames,result.in_range_frames,result.out_of_range_frames),(4,2,2))
        self.assertEqual(result.out_of_range_runs,((4,5),));self.assertEqual(result.bounds_status,'partial')
        self.assertEqual(result.temporal_coverage,0.5);self.assertEqual(result.structural_coverage,0.5)

    def test_fully_outside_and_empty_sequence(self):
        for states in ((),(F.VALID,)*3):
            with self.subTest(length=len(states)):
                value=assess_segment(5,7,states)
                self.assertEqual(value.status,'unavailable');self.assertEqual(value.usable_frames,0)
                self.assertEqual(value.out_of_range_runs,((5,7),))

    def test_zero_and_invalid_runs_remain_at_original_indices(self):
        states=(F.VALID,F.ZERO_POSE,F.ZERO_POSE,F.INVALID,F.VALID,F.ZERO_POSE)
        value=assess_segment(0,5,states)
        self.assertEqual(value.zero_pose_runs,((1,2),(5,5)))
        self.assertEqual(value.invalid_data_runs,((3,3),))
        self.assertEqual(value.usable_frames,2);self.assertEqual(value.temporal_coverage,1.)
        self.assertAlmostEqual(value.structural_coverage,2/6)
        self.assertEqual(value.status,'partial')
        self.assertEqual(states[3],F.INVALID)

    def test_all_zero_is_not_complete_despite_full_temporal_coverage(self):
        value=assess_segment(0,2,(F.ZERO_POSE,)*3)
        self.assertEqual(value.bounds_status,'contained');self.assertEqual(value.status,'unavailable')
        self.assertEqual(value.temporal_coverage,1.);self.assertEqual(value.structural_coverage,0.)

    def test_combined_internal_and_trailing_missing(self):
        value=assess_segment(0,4,(F.VALID,F.ZERO_POSE,F.INVALID))
        self.assertEqual(value.expected_frames,value.usable_frames+value.zero_pose_frames+value.invalid_data_frames+value.out_of_range_frames)
        self.assertEqual(value.out_of_range_runs,((3,4),))

    def test_invalid_interval_and_state_types(self):
        for first,last in [(-1,3),(4,2),(True,3),(0,1.5)]:
            with self.subTest(first=first,last=last),self.assertRaises(ValueError):assess_segment(first,last,(F.VALID,))
        for states in (None,('valid',),[None]):
            with self.subTest(states=states),self.assertRaises(ValueError):assess_segment(0,0,states)

    def test_synthetic_npy_adapter_preserves_rows_without_quality_threshold(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.npy'
            data=np.ones((4,33,4),dtype=np.float64)
            data[1]=0.;data[2,0,0]=np.nan;data[3,:,3]=0.01
            np.save(path,data,allow_pickle=False)
            with LandmarkSequence(path,representation=Representation.TWO_D) as sequence:
                self.assertEqual(inspect_frame_availability(sequence),(F.VALID,F.ZERO_POSE,F.INVALID,F.VALID))
                self.assertEqual(sequence.frame(0).reason,'coordinate_units_unconfirmed')
