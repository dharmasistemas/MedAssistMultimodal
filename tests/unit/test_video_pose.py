from types import SimpleNamespace as NS
import numpy as np
import pytest

from medassistmultimodal.infrastructure.video_pose import (VideoReader, VideoProcessingError,
    world_pose, IntervalPoseSequence, MediaPipePose, VideoFrame)
from medassistmultimodal.application.ex1_repetitions import Ex1Config, analyze_repetition


class Capture:
    def __init__(self, fps=30., fail=None): self.fps=fps; self.index=0; self.released=False; self.fail=fail
    def isOpened(self): return True
    def get(self, key): return [self.fps,2.,1.,5.][key]
    def read(self):
        i=self.index;self.index+=1
        return (False,None) if i==self.fail else (True,np.zeros((1,2,3),dtype=np.uint8))
    def release(self): self.released=True


def cv(capture):
    return NS(VideoCapture=lambda p:capture,CAP_PROP_FPS=0,CAP_PROP_FRAME_WIDTH=1,
              CAP_PROP_FRAME_HEIGHT=2,CAP_PROP_FRAME_COUNT=3,COLOR_BGR2RGB=99,
              cvtColor=lambda im,code:im[:,:,::-1].copy())


def test_reader_indices_timestamps_and_release(tmp_path):
    path=tmp_path/'clip.mp4';path.write_bytes(b'fixture')
    capture=Capture()
    with VideoReader(path,cv=cv(capture)) as reader:
        frames=list(reader.frames(2,4))
        assert [f.index for f in frames]==[2,3,4]
        assert [f.detector_timestamp_ms for f in frames]==[67,100,133]
        assert frames[1].nominal_seconds==.1
        with pytest.raises(VideoProcessingError): list(reader.frames(0,1))
    assert capture.released


@pytest.mark.parametrize('fps',[0.,float('nan'),float('inf'),241.])
def test_bad_metadata_closes_resource(tmp_path,fps):
    p=tmp_path/'clip.mp4';p.touch();capture=Capture(fps=fps)
    with pytest.raises(VideoProcessingError): VideoReader(p,cv=cv(capture))
    assert capture.released


def test_corrupt_video_not_silent_truncation(tmp_path):
    p=tmp_path/'clip.mp4';p.touch();capture=Capture(fail=2)
    with VideoReader(p,cv=cv(capture)) as reader:
        with pytest.raises(VideoProcessingError): list(reader.frames(0,4))
    assert capture.released


def result(points=None):
    if points is None: points=[NS(x=0.,y=0.,z=0.,visibility=1.) for _ in range(33)]
    return NS(pose_world_landmarks=[points])


def test_absent_ambiguous_and_invalid_pose():
    assert world_pose(NS(pose_world_landmarks=[]),4).reason=='no_pose'
    assert world_pose(NS(pose_world_landmarks=[[],[]]),4).reason=='multiple_poses'
    assert world_pose(result([]),4).reason=='invalid_landmark_count'
    r=result();r.pose_world_landmarks[0][14].x=float('nan')
    p=world_pose(r,4)
    assert p.status=='partial' and p.invalid_indices==(14,)
    assert 14 not in dict(p.landmarks)


def test_pipeline_connects_rules_and_preserves_global_index():
    p=result();points=p.pose_world_landmarks[0]
    for i,xyz in {12:(0,0,0),14:(1,0,0),16:(2,0,0),24:(0,1,0)}.items():
        points[i]=NS(x=float(xyz[0]),y=float(xyz[1]),z=float(xyz[2]),visibility=1.)
    poses={30:world_pose(p,30),31:world_pose(NS(pose_world_landmarks=[]),31)}
    seq=IntervalPoseSequence(poses,first=30,last=31)
    r=analyze_repetition(seq,30,31,evidence_ref='synthetic/video',config=Ex1Config(min_coverage=.5))
    assert r['rules'][0]['coverage']==.5
    assert r['rules'][0]['evidence_frame']==30
    assert r['rules'][0]['status']=='no_deviation'
    with pytest.raises(VideoProcessingError): IntervalPoseSequence({30:poses[30]},first=30,last=31)


def test_private_missing_path_rejected(tmp_path):
    with pytest.raises(VideoProcessingError): VideoReader(tmp_path/'missing.mp4',cv=cv(Capture()))
    with pytest.raises(VideoProcessingError): VideoReader(tmp_path/'_backup'/'clip.mp4',cv=cv(Capture()))


def test_bounds_and_color_conversion(tmp_path):
    p=tmp_path/'clip.mp4';p.touch();capture=Capture()
    image=np.array([[[1,2,3],[4,5,6]]],dtype=np.uint8)
    capture.read=lambda:(True,image)
    with VideoReader(p,cv=cv(capture)) as reader:
        with pytest.raises(VideoProcessingError):list(reader.frames(True,1))
        with pytest.raises(VideoProcessingError):list(reader.frames(0,5))
        frame=next(reader.frames(0,0))
        assert frame.rgb[0,0].tolist()==[3,2,1]


def test_detector_timestamp_guard_and_no_pose():
    detector=MediaPipePose.__new__(MediaPipePose)
    detector.last_timestamp=-1
    detector.mp=NS(ImageFormat=NS(SRGB=1),Image=lambda **kwargs:kwargs)
    detector.detector=NS(detect_for_video=lambda im,t:NS(pose_world_landmarks=[]))
    frame=VideoFrame(0,0.,0,object())
    assert detector.detect(frame).reason=='no_pose'
    with pytest.raises(VideoProcessingError):detector.detect(frame)
