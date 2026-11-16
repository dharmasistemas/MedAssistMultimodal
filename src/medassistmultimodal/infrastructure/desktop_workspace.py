"""Explicit work copies, local ASR and audited reviews; historical DBs stay read-only."""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.process_audio import ProcessAudio, AudioProcessingRequest, ProviderIdentity
from medassistmultimodal.application.register_audio import prepare_audio_registration
from medassistmultimodal.application.register_vitals import strict_json, encode_json
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.session import utc_datetime
from medassistmultimodal.providers.whisper_local import LocalWhisperTranscriber, checked_path
from .audio_evidence_store import AudioEvidenceStore
from .desktop_history import SQLiteHistoryReader
from .sqlite_audio_registration import register_audio_sqlite, query_audio_session
from .sqlite_event_review import review_event_sqlite
from .sqlite_patient_repository import SQLitePatientRepository

WORKSPACES = 'data/interim/audio/desktop_workspaces_v1'
CORPUS = 'data/interim/audio/simulated_v1/collection_status.json'


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    run_id: str
    session_id: str
    status: str
    persisted: bool


class DesktopWorkspace:
    def __init__(self, root, *, transcriber_factory=None):
        self.root = Path(root).absolute()
        self.reader = SQLiteHistoryReader(self.root)
        self.transcriber_factory = transcriber_factory
        self.prepared = {}  # Exact bytes survive persistence failure during this app session.

    def writable_path(self, database):
        try:
            path = checked_path(database, self.root)
            base = self.root/WORKSPACES
            relative = path.relative_to(base)
            if len(relative.parts)!=2 or relative.name!='audio.sqlite3': raise ValueError()
            workspace_id = str(UUID(relative.parts[0]))
            marker = strict_json(checked_path(str(path.parent/'workspace.json'), self.root).read_bytes())
            if marker != dict(version='desktop-workspace-v1', workspace_id=workspace_id): raise ValueError()
            if not path.is_file(): raise ValueError()
            return path
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise HistoryError('workspace_required') from exc

    def is_workspace(self, database):
        try: self.writable_path(database); return True
        except HistoryError: return False

    def create_copy(self, source, patient_id):
        # Validate the selected source without migrating or initializing it.
        self.reader.sessions(source, patient_id)
        workspace_id = str(uuid4())
        directory = checked_path(f'{WORKSPACES}/{workspace_id}', self.root)
        directory.mkdir(parents=True, exist_ok=False)
        destination = checked_path(str(directory/'audio.sqlite3'), self.root)
        with self.reader._connection(source) as origin, closing(sqlite3.connect(destination)) as target:
            origin.backup(target)
        (directory/'workspace.json').write_bytes(encode_json(dict(version='desktop-workspace-v1', workspace_id=workspace_id)))
        return destination.relative_to(self.root).as_posix()

    def clips(self):
        try:
            corpus = strict_json(checked_path(CORPUS, self.root).read_bytes())
            return tuple(c['case_id'] for c in corpus['clips'] if c.get('human_verified') is True
                         and (c.get('consent_ref') or c.get('tts_permission_ref')))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise HistoryError('corpus_unavailable') from exc

    def _transcriber(self):
        if self.transcriber_factory:
            return self.transcriber_factory(), ProviderIdentity('fixture', 'offline', '1', 'mock', True)
        manifest = strict_json(checked_path('data/manifests/day13_whisper_assets.json', self.root).read_bytes())
        for item in manifest['model']['files']:
            path = checked_path(str(Path(manifest['model']['local_path'])/item['name']), self.root)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                raise HistoryError('model_unavailable')
        return (LocalWhisperTranscriber(root=self.root, model_directory=manifest['model']['local_path']),
                ProviderIdentity('faster-whisper', 'small-ct2', manifest['runtime']['version'], 'whisper', False))

    def process(self, database, patient_id, case_id, session_at, progress=lambda stage: None):
        path = self.writable_path(database)
        session_at = utc_datetime(session_at, 'session_at')
        progress('validating')
        corpus = strict_json(checked_path(CORPUS, self.root).read_bytes())
        matches = [c for c in corpus['clips'] if c['case_id']==case_id]
        if len(matches)!=1: raise HistoryError('corpus_unavailable')
        clip = matches[0]
        permission = clip.get('consent_ref') or clip.get('tts_permission_ref')
        if clip.get('human_verified') is not True or not permission:
            raise HistoryError('permission_required')
        source = checked_path(clip['actual_audio_path'], self.root)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=clip['audio_sha256']:
            raise HistoryError('audio_changed')
        # Connection is opened and used only on the worker thread.
        with closing(sqlite3.connect(path, timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            patients = SQLitePatientRepository(connection)
            if patients.get_by_id(patient_id) is None: raise HistoryError('invalid_patient')
            progress('loading_model')
            transcriber, identity = self._transcriber()
            request = AudioProcessingRequest(run_id=uuid4(), session_id=uuid4(), patient_id=patient_id,
                session_timestamp=session_at, processing_timestamp=datetime.now(timezone.utc),
                audio_ref=clip['actual_audio_path'], expected_sha256=clip['audio_sha256'], origin_ref=CORPUS,
                permission_ref=permission, origin_kind=clip['origin_reported'], permission_declared=True)
            processor = ProcessAudio(root=self.root, patient_exists=lambda p: patients.get_by_id(p) is not None,
                transcriber=transcriber, asr_identity=identity)
            progress('processing')
            result = processor.execute(request)  # LLM disabled; no cloud adapter is created.
            if result.status=='rejected': raise HistoryError('audio_rejected')
            reference = (path.parent/f'{request.run_id}.json').relative_to(self.root).as_posix()
            prepared = prepare_audio_registration(result, evidence_ref=reference)
            self.prepared[str(request.run_id)] = (str(path), prepared)
            progress('saving')
            try:
                register_audio_sqlite(prepared, connection=connection, store=AudioEvidenceStore(self.root))
            except (ValueError, OSError, sqlite3.Error):
                return ProcessOutcome(str(request.run_id), str(request.session_id), result.status, False)
            return ProcessOutcome(str(request.run_id), str(request.session_id), result.status, True)

    def retry_persistence(self, database, run_id):
        path = self.writable_path(database)
        original, prepared = self.prepared[run_id]
        if str(path)!=original: raise HistoryError('workspace_required')
        with closing(sqlite3.connect(path, timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            register_audio_sqlite(prepared, connection=connection, store=AudioEvidenceStore(self.root))
        return ProcessOutcome(run_id, str(prepared.session.session_id),
                              strict_json(prepared.evidence)['summary']['status'], True)

    def review(self, database, session_id, request: EventReviewRequest, expected_evidence_ref):
        path = self.writable_path(database)
        # Recheck displayed evidence immediately before the status/audit operation.
        detail = self.reader.detail(str(path), session_id).document
        row = next((r for r in detail['events'] if r['event']['event_id']==str(request.event_id)), None)
        if row is None or row['event']['evidence_ref']!=expected_evidence_ref:
            raise HistoryError('evidence_invalid')
        with closing(sqlite3.connect(path, timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            try: return review_event_sqlite(request, connection=connection)
            except ValueError as exc: raise HistoryError('review_conflict') from exc
