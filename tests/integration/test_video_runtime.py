"""Opt-in explícito: dependências/assets locais; nunca baixa ou acessa providers."""
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.skipif(os.environ.get('MEDASSISTMULTIMODAL_VIDEO_TESTS') != '1',
                                reason='Validação RGB real exige opt-in e assets locais')


def test_real_codec_roundtrip(tmp_path):
    import cv2
    import numpy as np
    from medassistmultimodal.infrastructure.video_pose import VideoReader
    path=tmp_path/'synthetic.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),30.,(32,32))
    assert writer.isOpened()
    try:
        writer.write(np.zeros((32,32,3),dtype=np.uint8))
        writer.write(np.full((32,32,3),255,dtype=np.uint8))
    finally:writer.release()
    with VideoReader(path) as reader:
        frames=list(reader.frames(0,1))
        assert reader.info.fps==30. and reader.info.declared_frames==2
        assert len(frames)==2 and frames[0].rgb.shape==(32,32,3)


def test_real_corrupt_video(tmp_path):
    from medassistmultimodal.infrastructure.video_pose import VideoReader,VideoProcessingError
    path=tmp_path/'invalid.mp4';path.write_bytes(b'not a video')
    with pytest.raises(VideoProcessingError):VideoReader(path)


def test_real_model_absent_pose():
    import numpy as np
    from medassistmultimodal.infrastructure.video_pose import MediaPipePose,VideoFrame
    root=Path(__file__).resolve().parents[2]
    with MediaPipePose(root/'data/raw/models/pose_landmarker_full.task') as detector:
        result=detector.detect(VideoFrame(0,0.,0,np.zeros((256,256,3),dtype=np.uint8)))
    assert result.reason=='no_pose' and not result.landmarks
