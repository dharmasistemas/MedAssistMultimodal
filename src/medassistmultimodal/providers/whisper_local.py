"""Lazy, local-only faster-whisper adapter; no download or reference transcript input."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import time

from medassistmultimodal.application.audio import (
    Transcript,TranscriptSegment,AudioProviderUnavailableError,AudioNoSpeechError)
from medassistmultimodal.domain.audio_features import AudioFeatures,describe_audio


@dataclass(frozen=True, slots=True)
class WhisperRun:
    transcript: Transcript
    features: AudioFeatures
    source_sha256: str
    processing_seconds: float


def checked_path(value,root):
    path=Path(value);root=Path(root)
    if any(p.casefold() in ('_backup','.git','..') for p in path.parts):
        raise ValueError('Private/traversal path forbidden')
    if not path.is_absolute():path=root/path
    if not path.is_relative_to(root):raise ValueError('Path outside configured local root')
    for part in reversed((path,*path.parents)):
        if part.is_symlink() or part.is_junction():raise ValueError('Link/junction forbidden')
    return path


class LocalWhisperTranscriber:
    def __init__(self, *, root: Path, model_directory: str,
                 model_factory=None,decoder=None):
        self.root=Path(root).absolute()
        self.model_directory=checked_path(model_directory,self.root)
        self.model_factory=model_factory;self.decoder=decoder;self._model=None

    def _load(self):
        if self._model is None:
            checked_path(str(self.model_directory/'model.bin'),self.root)
            if not self.model_directory.is_dir() or not (self.model_directory/'model.bin').is_file():
                raise AudioProviderUnavailableError('Local model unavailable; no automatic download')
            try:
                factory=self.model_factory
                if factory is None:
                    from faster_whisper import WhisperModel
                    factory=WhisperModel
                self._model=factory(str(self.model_directory),device='cpu',compute_type='int8',
                                    cpu_threads=4,local_files_only=True)
            except Exception as exc:
                raise AudioProviderUnavailableError('Cannot load local Whisper model') from exc
        return self._model

    def transcribe(self,audio_ref: str,*,language='pt-BR') -> Transcript:
        return self.transcribe_with_details(audio_ref,language=language).transcript

    def transcribe_with_details(self,audio_ref: str,*,language='pt-BR') -> WhisperRun:
        if language!='pt-BR':raise ValueError('This experimental profile supports pt-BR only')
        path=checked_path(audio_ref,self.root)
        if path.suffix.lower() not in ('.wav','.mp3','.m4a') or not path.is_file():
            raise ValueError('Existing local WAV/MP3/M4A required')
        start=time.perf_counter();source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            decode=self.decoder
            if decode is None:
                from faster_whisper.audio import decode_audio
                decode=decode_audio
            samples=decode(str(path),sampling_rate=16000)
            features=describe_audio(samples)
        except Exception as exc:
            raise AudioProviderUnavailableError('Cannot decode audio locally') from exc
        model=self._load()
        try:
            generated,info=model.transcribe(samples,language='pt',task='transcribe',
                beam_size=5,temperature=0.0,condition_on_previous_text=False,
                vad_filter=False,word_timestamps=False)
            segments=[]
            for s in generated:
                if not isinstance(s.text,str):raise ValueError('Invalid text from provider')
                text=s.text.strip()
                if not text:continue
                segment=TranscriptSegment(s.start,s.end,text)
                # Segment boundaries are model estimates; reject intervals outside decoded signal.
                if segment.end_seconds > features.duration_seconds + 0.02:
                    raise ValueError('Segment outside audio duration')
                segments.append(segment)
        except Exception as exc:
            raise AudioProviderUnavailableError('Whisper inference/output unavailable') from exc
        if not segments:raise AudioNoSpeechError('No speech text produced by Whisper')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hash:
            raise AudioProviderUnavailableError('Source changed during transcription')
        try:
            transcript=Transcript(' '.join(s.text for s in segments),'pt-BR','whisper',
                f'{path.relative_to(self.root).as_posix()}#sha256={source_hash}',tuple(segments))
        except ValueError as exc:
            raise AudioProviderUnavailableError('Invalid Whisper segment ordering') from exc
        return WhisperRun(transcript,features,source_hash,time.perf_counter()-start)
