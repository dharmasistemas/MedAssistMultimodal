"""Catalog-bound local listening, independent of ASR and LLM providers."""
import ctypes
import hashlib
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_vitals import strict_json
from medassistmultimodal.infrastructure.desktop_workspace import CORPUS
from medassistmultimodal.infrastructure.desktop_acoustics import acoustic_source
from medassistmultimodal.providers.whisper_local import checked_path


class PlaybackError(RuntimeError):
    pass


@dataclass
class PreparedListeningAudio:
    directory: object
    path: Path

    def close(self):
        self.directory.cleanup()


def prepare_listening_audio(path):
    """Decode on the UI worker, without loading any speech model. Own temp files only."""
    directory = tempfile.TemporaryDirectory(prefix='medassistmultimodal-listen-')
    output = Path(directory.name)/'listening.wav'
    try:
        import av
        with av.open(str(path)) as container, wave.open(str(output), 'wb') as target:
            target.setnchannels(1); target.setsampwidth(2); target.setframerate(44100)
            resampler = av.AudioResampler(format='s16', layout='mono', rate=44100)
            samples = 0
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    samples += converted.samples
                    if samples > 44100*120:
                        raise PlaybackError('Áudio fora do limite de escuta (120 s).')
                    target.writeframes(converted.to_ndarray().tobytes())
            for converted in resampler.resample(None):
                samples += converted.samples
                if samples > 44100*120:
                    raise PlaybackError('Áudio fora do limite de escuta (120 s).')
                target.writeframes(converted.to_ndarray().tobytes())
            if not samples:
                raise PlaybackError('Áudio sem amostras para reprodução.')
        return PreparedListeningAudio(directory,output)
    except Exception as exc:
        directory.cleanup()
        raise PlaybackError('Não foi possível preparar a escuta local.') from exc


def playback_source(root, case, *, pilot=False):
    """Only registered, permitted, unchanged local media; never arbitrary UI paths."""
    try:
        if pilot:
            item = acoustic_source(root, case)
            reference, digest = item['audio_ref'], item['sha256']
        else:
            corpus = strict_json(checked_path(CORPUS, root).read_bytes())
            matches = [c for c in corpus['clips'] if c['case_id'] == case]
            if len(matches) != 1:
                raise ValueError()
            item = matches[0]
            if item.get('human_verified') is not True or not (item.get('consent_ref') or item.get('tts_permission_ref')):
                raise ValueError()
            reference, digest = item['actual_audio_path'], item['audio_sha256']
        path = checked_path(reference, root)
        if path.suffix.lower() not in ('.mp3', '.wav', '.m4a') or not path.is_file():
            raise ValueError()
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError()
        return path
    except (HistoryError, ValueError, KeyError, TypeError, OSError) as exc:
        raise PlaybackError('Mídia ausente, alterada ou sem permissão no catálogo.') from exc


class WindowsAudioPlayer:
    """Small native MCI adapter. No DLL loading or playback until explicitly opened."""

    def __init__(self, send=None):
        self._send = send
        self.alias = 'mam' + uuid4().hex
        self.opened = False
        self.duration_ms = 0

    def _command(self, command):
        try:
            if self._send is None:
                if os.name != 'nt':
                    raise PlaybackError('Reprodução disponível somente no Windows.')
                native = ctypes.WinDLL('winmm').mciSendStringW
                native.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
                native.restype = ctypes.c_uint

                def send(text):
                    result = ctypes.create_unicode_buffer(256)
                    code = native(text, result, len(result), None)
                    if code:
                        raise PlaybackError('Reprodução local indisponível neste formato/dispositivo.')
                    return result.value
                self._send = send
            return self._send(command)
        except (OSError, ValueError, TypeError) as exc:
            raise PlaybackError('Reprodução local indisponível.') from exc

    def open(self, path):
        self.close()
        path = Path(path)
        if not path.is_absolute() or not path.is_file() or path.suffix.lower() not in ('.mp3', '.wav', '.m4a') or any(c in str(path) for c in ('"', '\n', '\r')):
            raise PlaybackError('Mídia local inválida.')
        try:
            kind = 'waveaudio' if path.suffix.lower() == '.wav' else 'mpegvideo'
            self._command(f'open "{path}" type {kind} alias {self.alias}')
            self.opened = True
            self._command(f'set {self.alias} time format milliseconds')
            self.duration_ms = int(self._command(f'status {self.alias} length'))
            if self.duration_ms <= 0:
                raise PlaybackError('Duração indisponível.')
        except (PlaybackError, ValueError) as exc:
            self.close()
            raise PlaybackError('Não foi possível abrir o áudio no reprodutor local.') from exc

    def play(self):
        if not self.opened:
            raise PlaybackError('Selecione um áudio antes de reproduzir.')
        position, mode = self.status()
        if mode == 'stopped' and position >= self.duration_ms - 20:
            self._command(f'seek {self.alias} to start')
        self._command(f'play {self.alias}')

    def pause(self):
        if self.opened:
            self._command(f'pause {self.alias}')

    def stop(self):
        if self.opened:
            self._command(f'stop {self.alias}')
            self._command(f'seek {self.alias} to start')

    def status(self):
        if not self.opened:
            return 0, 'closed'
        try:
            position = int(self._command(f'status {self.alias} position'))
            return max(0, min(position, self.duration_ms)), self._command(f'status {self.alias} mode')
        except ValueError as exc:
            raise PlaybackError('Posição de reprodução indisponível.') from exc

    def close(self):
        if self.opened:
            self._command(f'close {self.alias}')
            self.opened = False
        self.duration_ms = 0
