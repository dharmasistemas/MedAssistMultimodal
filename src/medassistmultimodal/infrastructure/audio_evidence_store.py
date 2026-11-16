"""Exclusive immutable file storage; never deletes orphaned evidence."""
import os
from pathlib import Path

from medassistmultimodal.application.register_audio import verify_prepared_audio
from medassistmultimodal.providers.whisper_local import checked_path


class AudioEvidenceStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()

    def path(self, reference):
        if not isinstance(reference, str) or not reference.startswith('data/interim/audio/') or '#' in reference:
            raise ValueError('Relative audio evidence path required')
        path = checked_path(reference, self.root)
        if path.suffix != '.json': raise ValueError('JSON evidence required')
        return path

    def read(self, reference):
        return self.path(reference).read_bytes()

    def ensure(self, prepared, *, committed):
        verify_prepared_audio(prepared)
        path = self.path(prepared.evidence_ref)
        if path.exists():
            if path.read_bytes() != prepared.evidence:
                raise ValueError('Existing evidence differs; preserved without overwrite')
            return
        if committed:
            raise ValueError('Committed evidence missing; explicit recovery required')
        path.parent.mkdir(parents=True, exist_ok=True)
        path = self.path(prepared.evidence_ref)  # Recheck links after creating parents.
        try:
            with path.open('xb') as stream:
                stream.write(prepared.evidence); stream.flush(); os.fsync(stream.fileno())
        except FileExistsError:
            if self.read(prepared.evidence_ref) != prepared.evidence:
                raise ValueError('Concurrent evidence conflict; preserved')
