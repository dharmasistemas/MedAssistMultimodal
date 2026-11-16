"""Loader NPY v1, read-only e sem inferência silenciosa de unidade 2D."""
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import math
from pathlib import Path
import re

import numpy as np

from medassistmultimodal.domain.rehabilitation import CoordinateSpace, Landmark


class LandmarkLoadError(ValueError):
    pass


class Representation(StrEnum):
    TWO_D = '2d'
    THREE_D = '3d'


class ImageUnits(StrEnum):
    UNKNOWN = 'unknown'
    PIXELS = 'pixels'
    NORMALIZED = 'normalized'


@dataclass(frozen=True, slots=True)
class RawFrame:
    frame_index: int
    representation: Representation
    values: tuple[tuple[float, float, float, float], ...]
    all_zero_pose: bool


@dataclass(frozen=True, slots=True)
class PoseFrame:
    frame_index: int
    status: str
    reason: str | None
    landmarks: tuple[tuple[int, Landmark], ...]
    invalid_indices: tuple[int, ...]
    coordinate_space: CoordinateSpace | None
    image_units: ImageUnits
    image_size: tuple[int, int] | None
    unit_evidence_ref: str | None


class LandmarkSequence:
    """Context manager: cópias por frame; o array mapeado nunca é exposto."""
    def __init__(self, path: Path, *, representation: Representation,
                 expected_sha256: str | None = None, image_units: ImageUnits = ImageUnits.UNKNOWN,
                 image_size: tuple[int, int] | None = None, unit_evidence_ref: str | None = None):
        self._data = None
        if not isinstance(representation, Representation) or not isinstance(image_units, ImageUnits):
            raise LandmarkLoadError('Representação/unidade deve usar enum explícito')
        if representation is Representation.THREE_D and (image_units is not ImageUnits.UNKNOWN or image_size is not None):
            raise LandmarkLoadError('Configuração de imagem incompatível com 3D')
        if image_size is not None and (not isinstance(image_size,tuple) or len(image_size)!=2 or
            any(type(value) is not int or value<=0 for value in image_size)):
            raise LandmarkLoadError('image_size deve ser (largura,altura) de inteiros positivos')
        if image_units is not ImageUnits.UNKNOWN and (not isinstance(unit_evidence_ref,str) or
            not unit_evidence_ref.strip() or unit_evidence_ref!=unit_evidence_ref.strip()):
            raise LandmarkLoadError('Unidade 2D explícita exige unit_evidence_ref')
        if expected_sha256 is not None and (not isinstance(expected_sha256,str) or
            re.fullmatch('[0-9a-f]{64}',expected_sha256) is None):
            raise LandmarkLoadError('SHA-256 esperado deve ser hexadecimal canônico')
        path=Path(path)
        if '..' in path.parts or any(part.casefold() in {'_backup','.git'} for part in path.parts):
            raise LandmarkLoadError('Caminho não permitido')
        path=path.absolute()
        for part in reversed((path,*path.parents)):
            if part.is_symlink() or part.is_junction():raise LandmarkLoadError('Links/junctions não permitidos')
        if path.suffix.lower()!='.npy':raise LandmarkLoadError('Esperado arquivo NPY')
        try:
            size=path.stat().st_size
            if not 0<size<=64*1024**2:raise LandmarkLoadError('Arquivo fora do limite de 64 MiB')
            if expected_sha256 is not None:
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(1048576),b''):digest.update(chunk)
                if digest.hexdigest()!=expected_sha256:raise LandmarkLoadError('SHA-256 divergente')
            data=np.load(path,allow_pickle=False,mmap_mode='r')
        except LandmarkLoadError:raise
        except (OSError,ValueError,EOFError):raise LandmarkLoadError('NPY indisponível ou inválido') from None
        self._data=data
        try:
            if not isinstance(data,np.memmap):raise LandmarkLoadError('NPY mapeável esperado')
            if data.ndim!=3 or data.shape[0]==0 or data.shape[1:]!=(33,4):
                raise LandmarkLoadError('Shape esperado: (frames,33,4), não vazio')
            if data.dtype!=np.dtype('float64') or not data.flags.c_contiguous:
                raise LandmarkLoadError('V1 exige float64 nativo e ordem C')
            if data.offset+data.nbytes!=size:raise LandmarkLoadError('Tamanho NPY inconsistente')
            self.shape=tuple(data.shape)
            self.representation=representation
            self.image_units=image_units
            self.image_size=image_size
            self.unit_evidence_ref=unit_evidence_ref
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        data=self._data
        self._data=None
        if isinstance(data,np.memmap):data._mmap.close()
        elif data is not None and hasattr(data,'close'):data.close()

    def __enter__(self):
        if self._data is None:raise LandmarkLoadError('Sequência fechada')
        return self

    def __exit__(self,*args):self.close()

    def __len__(self):return self.shape[0]

    def raw_frame(self,index: int) -> RawFrame:
        if self._data is None:raise LandmarkLoadError('Sequência fechada')
        if type(index) is not int or not 0<=index<len(self):
            raise LandmarkLoadError('Índice de frame fora da sequência; sem índices negativos')
        values=tuple(tuple(float(v) for v in point) for point in self._data[index])
        return RawFrame(index,self.representation,values,all(v==0 for point in values for v in point))

    def frame(self,index: int) -> PoseFrame:
        raw=self.raw_frame(index)
        space=CoordinateSpace.WORLD_3D if self.representation is Representation.THREE_D else CoordinateSpace.IMAGE_2D
        def result(status,reason,points=(),invalid=(),coordinate_space=space):
            return PoseFrame(index,status,reason,tuple(points),tuple(invalid),coordinate_space,
                             self.image_units,self.image_size,self.unit_evidence_ref)
        if raw.all_zero_pose:return result('not_analyzable','all_zero_pose',coordinate_space=None)
        if self.representation is Representation.TWO_D:
            if self.image_units is ImageUnits.UNKNOWN:
                return result('not_analyzable','coordinate_units_unconfirmed',coordinate_space=None)
            if self.image_units is ImageUnits.NORMALIZED and self.image_size is None:
                return result('not_analyzable','missing_image_dimensions',coordinate_space=None)
        points=[];invalid=[]
        for number,(x,y,z,visibility) in enumerate(raw.values):
            coordinates=(x,y,z) if self.representation is Representation.THREE_D else (x,y)
            if self.representation is Representation.TWO_D and self.image_units is ImageUnits.NORMALIZED:
                try:coordinates=(x*self.image_size[0],y*self.image_size[1])
                except OverflowError:invalid.append(number);continue
            if not all(math.isfinite(v) for v in coordinates) or not math.isfinite(visibility) or not 0<=visibility<=1:
                invalid.append(number);continue
            points.append((number,Landmark(coordinates,visibility)))
        if invalid:
            return result('partial' if points else 'not_analyzable','invalid_landmarks',points,invalid)
        return result('ok',None,points)
