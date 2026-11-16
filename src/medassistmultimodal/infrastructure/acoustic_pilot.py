"""Local decoder and fixed acoustic profile, without Whisper model or text inference."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from time import perf_counter

from medassistmultimodal.domain.audio_features import AudioFeatures,describe_audio
from medassistmultimodal.domain.audio_pauses import PauseAssessment,assess_internal_pauses
from medassistmultimodal.providers.whisper_local import checked_path


class AcousticPilotError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)


@dataclass(frozen=True,slots=True)
class AcousticPilotRun:
    source_ref: str
    source_sha256: str
    decoder: str
    is_mock: bool
    features: AudioFeatures
    assessment: PauseAssessment
    processing_seconds: float


def _digest(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def analyze_acoustic_file(root,audio_ref,*,expected_sha256,decoder=None):
    """Validate immutable local input; injected decoder is always explicitly mock."""
    started=perf_counter();root=Path(root).absolute()
    if not isinstance(expected_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_sha256):
        raise AcousticPilotError('invalid_expected_hash')
    try:
        path=checked_path(audio_ref,root)
        if path.suffix.lower() not in ('.mp3','.wav','.m4a') or not path.is_file():raise ValueError()
        if _digest(path)!=expected_sha256:raise AcousticPilotError('source_changed')
    except AcousticPilotError:raise
    except (ValueError,OSError,TypeError):raise AcousticPilotError('input_unavailable_or_unsafe') from None
    injected=decoder is not None
    try:
        if decoder is None:
            from faster_whisper.audio import decode_audio
            decoder=decode_audio
        samples=decoder(str(path),sampling_rate=16000)
    except Exception:raise AcousticPilotError('decoder_unavailable_or_failed') from None
    try:
        import numpy as np
        if (not isinstance(samples,np.ndarray) or samples.ndim!=1 or samples.size==0
            or samples.dtype.kind!='f' or not np.isfinite(samples).all()
            or np.max(np.abs(samples))>1):raise ValueError()
        if not 5*16000<=samples.size<=60*16000:raise AcousticPilotError('unsupported_duration')
        features=describe_audio(samples);assessment=assess_internal_pauses(features)
    except AcousticPilotError:raise
    except (ValueError,TypeError,AttributeError,OverflowError):raise AcousticPilotError('invalid_decoded_audio_or_features') from None
    try:
        if _digest(path)!=expected_sha256:raise AcousticPilotError('source_changed')
    except OSError:raise AcousticPilotError('source_unavailable_after_processing') from None
    return AcousticPilotRun(path.relative_to(root).as_posix(),expected_sha256,
        'injected_offline_fixture' if injected else 'faster_whisper.audio.decode_audio',injected,
        features,assessment,perf_counter()-started)
