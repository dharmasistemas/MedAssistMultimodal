from dataclasses import replace
from types import SimpleNamespace
import math
import pytest

from medassistmultimodal.application.ex1_repetitions import Ex1Config, analyze_repetition
from medassistmultimodal.domain.rehabilitation import CoordinateSpace, Landmark


def pose(bent=False, low=False, visibility=1.):
    points = {12: (0.,0.,0.), 24: (0.,1.,0.), 14: ((0.,1.,0.) if low else (1.,0.,0.)),
              16: ((1.,1.,0.) if bent else ((0.,2.,0.) if low else (2.,0.,0.)))}
    return SimpleNamespace(coordinate_space=CoordinateSpace.WORLD_3D, reason=None,
        landmarks=tuple((i, Landmark(p, visibility)) for i,p in points.items()))


class Sequence:
    def __init__(self, frames): self.frames=frames
    def __len__(self): return len(self.frames)
    def frame(self,i): return self.frames[i]


def analyze(frames, first=0, last=None, **kwargs):
    return analyze_repetition(Sequence(frames), first, len(frames)-1 if last is None else last,
                             evidence_ref='synthetic/ex1', config=kwargs.pop('config',Ex1Config()), **kwargs)


def test_positive_negative_and_evidence():
    good=analyze([pose()]); bad=analyze([pose(bent=True)]); low=analyze([pose(low=True)])
    assert [r['status'] for r in good['rules']]==['no_deviation','no_deviation']
    assert bad['rules'][0]['status']=='deviation'
    assert low['rules'][1]['status']=='deviation'
    assert good['rules'][0]['evidence_frame']==0
    assert good['confidence'] is None and good['overall_correctness'] is None


def test_coverage_boundary_and_no_interpolation():
    frames=[pose()]*4+[pose(visibility=.49)]
    result=analyze(frames)
    assert result['rules'][0]['coverage']==.8
    assert result['rules'][0]['status']=='no_deviation'
    assert analyze(frames, last=5)['rules'][0]['status']=='not_analyzable'
    assert result['samples'][-1]['right_elbow'] is None


def test_threshold_boundaries():
    result=analyze([pose()],config=Ex1Config(elbow_min_degrees=180.,arm_peak_min_degrees=90.))
    assert all(r['status']=='no_deviation' for r in result['rules'])
    frames=[pose(bent=True)]+[pose()]*4
    assert analyze(frames)['rules'][0]['status']=='deviation'  # Fração inclusiva .2.


def test_missing_source_and_outside_interval():
    result=analyze([],first=3,last=4)
    assert result['quality_reasons']=={'out_of_range':2}
    assert all(r['status']=='not_analyzable' for r in result['rules'])


def test_source_failure_is_not_success_or_empty_result():
    class Unavailable(Sequence):
        def frame(self, i): raise OSError('fonte indisponível')
    with pytest.raises(OSError):
        analyze_repetition(Unavailable([pose()]),0,0,evidence_ref='synthetic',config=Ex1Config())


def test_unknown_units_zero_pose_and_view():
    absent=SimpleNamespace(coordinate_space=None,reason='all_zero_pose',landmarks=())
    assert analyze([absent])['quality_reasons']=={'all_zero_pose':1}
    unknown=SimpleNamespace(coordinate_space=None,reason='coordinate_units_unconfirmed',landmarks=())
    assert analyze([unknown])['rules'][0]['status']=='not_analyzable'
    assert analyze([pose()],camera=2)['rules'][0]['reason']=='unsupported_camera'


def test_nominal_timecode_and_inclusive_bounds():
    result=analyze([pose()]*32,first=30,last=31)
    assert result['expected_frames']==2 and result['first_seconds']==1.
    assert [s['frame'] for s in result['samples']]==[30,31]


@pytest.mark.parametrize('field,value',[('min_visibility',True),('min_coverage',0),('bent_fraction',math.nan),
    ('fps',math.inf),('fps',False),('elbow_min_degrees',181),('camera',True),('camera',2)])
def test_invalid_configuration(field,value):
    with pytest.raises(ValueError): replace(Ex1Config(),**{field:value})


@pytest.mark.parametrize('first,last',[(True,1),(-1,1),(2,1)])
def test_invalid_intervals(first,last):
    with pytest.raises(ValueError): analyze([pose()],first,last)
