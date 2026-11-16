"""Hash-checked local decoding for pauses, without instantiating any speech model."""
from dataclasses import dataclass
import hashlib
import re
from time import perf_counter
from pathlib import Path

from .whisper_local import checked_path
from medassistmultimodal.application.analyze_acoustic_pauses import analyze_pause_samples
from medassistmultimodal.domain.audio_features import AudioFeatures
from medassistmultimodal.domain.internal_pauses import PauseAssessment


class AcousticInputError(ValueError):
    pass


class AcousticDecoderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True,slots=True)
class AcousticPauseRun:
    features: AudioFeatures
    assessment: PauseAssessment
    source_sha256: str
    processing_seconds: float
    is_mock: bool


class LocalPauseAnalyzer:
    def __init__(self,root,*,decoder=None):
        self.root=Path(root).absolute();self.decoder=decoder

    def analyze(self,audio_ref,*,expected_sha256):
        started=perf_counter()
        if not isinstance(expected_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',expected_sha256):
            raise AcousticInputError('Expected SHA256 required')
        try:
            path=checked_path(audio_ref,self.root)
            if path.suffix.lower() not in ('.mp3','.wav','.m4a') or not path.is_file():raise ValueError()
            def check_hash():
                try:raw=path.read_bytes()
                except OSError as exc:raise AcousticInputError('Audio unavailable') from exc
                if hashlib.sha256(raw).hexdigest()!=expected_sha256:
                    raise AcousticInputError('Audio hash differs')
            check_hash()
        except (ValueError,OSError) as exc:raise AcousticInputError('Invalid local audio or hash') from exc
        try:
            decode=self.decoder
            if decode is None:
                from faster_whisper.audio import decode_audio
                decode=decode_audio
            samples=decode(str(path),sampling_rate=16000)
        except Exception as exc:
            check_hash()
            raise AcousticDecoderUnavailable('Cannot decode local audio') from exc
        try:
            check_hash();features,assessment=analyze_pause_samples(samples)
        except OSError as exc:raise AcousticInputError('Audio unavailable after decoding') from exc
        except ValueError as exc:raise AcousticInputError('Invalid decoded audio or changed hash') from exc
        return AcousticPauseRun(features,assessment,expected_sha256,perf_counter()-started,self.decoder is not None)
