"""Leitura sequencial RGB e MediaPipe Tasks; imports pesados somente no uso real."""
from dataclasses import dataclass
import math
from pathlib import Path

from medassistmultimodal.domain.rehabilitation import CoordinateSpace, Landmark
from .rehab26_landmarks import ImageUnits, PoseFrame


class VideoProcessingError(ValueError):
    pass


def safe_local_file(path: Path) -> Path:
    path = Path(path)
    if '..' in path.parts or any(p.casefold() in {'_backup', '.git'} for p in path.parts):
        raise VideoProcessingError('Caminho não permitido')
    path = path.absolute()
    for parent in reversed((path, *path.parents)):
        if parent.is_symlink() or parent.is_junction():
            raise VideoProcessingError('Links não permitidos')
    if not path.is_file(): raise VideoProcessingError('Arquivo local indisponível')
    return path


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    declared_frames: int


@dataclass(frozen=True)
class VideoFrame:
    index: int
    nominal_seconds: float
    detector_timestamp_ms: int
    rgb: object


class VideoReader:
    """Somente arquivo local CFR; sem câmera, URL, seek ou correção silenciosa de FPS."""
    def __init__(self, path: Path, *, cv=None):
        path = safe_local_file(path)
        if cv is None:
            try: import cv2 as cv
            except ImportError: raise VideoProcessingError('OpenCV não instalado') from None
        self.cv = cv
        self.capture = cv.VideoCapture(str(path))
        try:
            if not self.capture.isOpened(): raise VideoProcessingError('Vídeo não pôde ser aberto')
            fps = float(self.capture.get(cv.CAP_PROP_FPS))
            dimensions = [float(self.capture.get(p)) for p in
                          (cv.CAP_PROP_FRAME_WIDTH, cv.CAP_PROP_FRAME_HEIGHT, cv.CAP_PROP_FRAME_COUNT)]
            if not math.isfinite(fps) or not 0 < fps <= 240:
                raise VideoProcessingError('FPS inválido; perfil CFR até 240 FPS')
            if any(not math.isfinite(v) or v <= 0 or not v.is_integer() for v in dimensions):
                raise VideoProcessingError('Dimensões/contagem declarada inválidas')
            self.info = VideoInfo(int(dimensions[0]), int(dimensions[1]), fps, int(dimensions[2]))
        except BaseException:
            self.capture.release()
            raise
        self.closed = False
        self.started = False

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self):
        if not self.closed:
            self.capture.release()
            self.closed = True

    def frames(self, first: int, last: int):
        if self.closed or self.started: raise VideoProcessingError('Leitura única; leitor fechado ou já usado')
        if type(first) is not int or type(last) is not int or not 0 <= first <= last < self.info.declared_frames:
            raise VideoProcessingError('Intervalo fora da contagem declarada')
        self.started = True
        for index in range(last + 1):
            ok, image = self.capture.read()
            if not ok: raise VideoProcessingError(f'Falha de decodificação no frame {index}; não truncar')
            if image is None or getattr(image, 'shape', None) != (self.info.height, self.info.width, 3):
                raise VideoProcessingError('Frame com dimensões/canais inesperados')
            if index >= first:
                yield VideoFrame(index, index / self.info.fps, round(index * 1000 / self.info.fps),
                                 self.cv.cvtColor(image, self.cv.COLOR_BGR2RGB))


def world_pose(result, index: int) -> PoseFrame:
    """Ausência não gera pose zero; seleção ambígua é recusada."""
    poses = result.pose_world_landmarks
    def output(status, reason, points=(), invalid=()):
        return PoseFrame(index, status, reason, tuple(points), tuple(invalid),
                         CoordinateSpace.WORLD_3D if points else None,
                         ImageUnits.UNKNOWN, None, 'mediapipe_tasks_world_meters')
    if not poses: return output('not_analyzable', 'no_pose')
    if len(poses) != 1: return output('not_analyzable', 'multiple_poses')
    if len(poses[0]) != 33: return output('not_analyzable', 'invalid_landmark_count')
    points = []; invalid = []
    for number, point in enumerate(poses[0]):
        values = (point.x, point.y, point.z, point.visibility)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values) or not 0 <= values[3] <= 1:
            invalid.append(number)
        else: points.append((number, Landmark(tuple(values[:3]), values[3])))
    return output('partial' if invalid and points else ('ok' if points else 'not_analyzable'),
                  'invalid_landmarks' if invalid else None, points, invalid)


class MediaPipePose:
    def __init__(self, model_path: Path):
        model_path = safe_local_file(model_path)
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
        except ImportError: raise VideoProcessingError('MediaPipe não instalado') from None
        self.mp = mp
        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path), delegate=python.BaseOptions.Delegate.CPU),
            running_mode=vision.RunningMode.VIDEO, num_poses=1,
            min_pose_detection_confidence=0.5, min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5, output_segmentation_masks=False)
        self.detector = vision.PoseLandmarker.create_from_options(options)
        self.last_timestamp = -1

    def __enter__(self): return self
    def __exit__(self, *args): self.detector.close()
    def detect(self, frame: VideoFrame) -> PoseFrame:
        if frame.detector_timestamp_ms <= self.last_timestamp:
            raise VideoProcessingError('Timestamp deve ser estritamente crescente')
        result = self.detector.detect_for_video(
            self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=frame.rgb), frame.detector_timestamp_ms)
        self.last_timestamp = frame.detector_timestamp_ms
        return world_pose(result, frame.index)


class IntervalPoseSequence:
    """Adapta intervalo extraído sem renumerar índices globais do vídeo."""
    def __init__(self, poses: dict[int, PoseFrame], *, first: int, last: int):
        if type(first) is not int or type(last) is not int or first < 0 or last < first:
            raise VideoProcessingError('Intervalo inválido')
        if set(poses) != set(range(first, last + 1)) or any(p.frame_index != i for i,p in poses.items()):
            raise VideoProcessingError('Intervalo incompleto ou índices inconsistentes')
        self.poses = dict(poses)
        self.last = last
    def __len__(self): return self.last + 1
    def frame(self, index):
        if type(index) is not int or index not in self.poses: raise VideoProcessingError('Frame não extraído')
        return self.poses[index]
