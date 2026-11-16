"""Register known fictional scenarios and review verified events only in explicit work copies."""
from contextlib import closing
from dataclasses import dataclass,asdict
import hashlib
import re
import sqlite3
from uuid import uuid4
from datetime import datetime,timezone

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.application.register_vitals import prepare_vitals,register_prepared_vitals,strict_json
from medassistmultimodal.application.register_prescriptions import prepare_prescriptions,register_prepared_prescriptions
from medassistmultimodal.application.register_prescription_expectation import prepare_prescription_expectation
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.demo.prescription_expectations import expectation_cases
from medassistmultimodal.application.register_acoustics import prepare_acoustics,register_prepared_acoustics
from medassistmultimodal.providers.acoustic_local import LocalPauseAnalyzer,AcousticInputError,AcousticDecoderUnavailable
from .desktop_acoustics import acoustic_source
from medassistmultimodal.providers.whisper_local import checked_path
from .desktop_workspace import DesktopWorkspace
from .desktop_vitals import MultimodalHistoryReader
from .sqlite_patient_repository import SQLitePatientRepository
from .sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from .sqlite_event_review import review_event_sqlite


@dataclass(frozen=True,slots=True)
class StructuredOutcome:
    run_id: str
    session_id: str
    modality: str
    scenario: str
    persisted: bool
    error_code: str | None = None


class StructuredWorkspace(DesktopWorkspace):
    supports_structured = True

    def __init__(self,root,*,pause_analyzer_factory=None,**kwargs):
        super().__init__(root,**kwargs)
        self.pause_analyzer_factory=pause_analyzer_factory
        self.reader=MultimodalHistoryReader(self.root)
        self.structured_prepared={}

    def scenarios(self,modality):
        if modality=='acoustics':return ('AP01','AP02','AP03')
        if modality=='vitals':return tuple(f'V{i:02d}' for i in range(1,19))
        if modality=='prescriptions':return (*tuple(f'P{i:02d}' for i in range(1,18)),*expectation_cases()[0])
        raise HistoryError('structured_input_rejected')

    def _input(self,modality,scenario):
        try:
            if scenario not in self.scenarios(modality):raise HistoryError('structured_input_rejected')
            if modality=='prescriptions' and scenario in expectation_cases()[0]:
                return encode_json(expectation_cases()[0][scenario])
            if modality=='vitals' and re.fullmatch(r'V[0-9]{2}',scenario):
                reference=f'data/synthetic/vitals_v1/{scenario}.json'
                manifest=strict_json(checked_path('data/synthetic/vitals_v1/manifest.json',self.root).read_bytes())
                expected=manifest['files'][scenario+'.json']['sha256']
            elif modality=='prescriptions' and re.fullmatch(r'P[0-9]{2}',scenario):
                generated=checked_path('data/synthetic/prescriptions_v1/manifest.json',self.root)
                if generated.is_file():
                    receipt=strict_json(generated.read_bytes())
                    reference=f'data/synthetic/prescriptions_v1/{scenario}_input.json'
                    expected=receipt['files'][scenario+'_input.json']['sha256']
                else:
                    # Historical installations remain readable without rewriting evidence.
                    reference=f'data/interim/prescriptions/day12_closeout_v1/{scenario}_input.json'
                    receipt=strict_json(checked_path('reports/DAY_12_TASKS_04_05_2026-11-05.json',self.root).read_bytes())
                    expected=receipt['artifact_sha256'][scenario+'_input.json']
            else:raise ValueError()
            raw=checked_path(reference,self.root).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=expected:raise HistoryError('scenario_changed')
            return raw
        except HistoryError:raise
        except (ValueError,KeyError,TypeError,OSError) as exc:raise HistoryError('scenario_unavailable') from exc

    def _persist(self,database,modality,prepared):
        path=self.writable_path(database)
        with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            if SQLitePatientRepository(connection).get_by_id(prepared.session.subject.patient_id) is None:
                raise HistoryError('invalid_patient')
            uow=SQLiteMultimodalUnitOfWork(connection)
            existing=uow.sessions.get_by_id(prepared.session.session_id)
            if existing is not None:
                if existing!=prepared.session or set(uow.events.list_for_session(existing.session_id))!=set(prepared.events):
                    raise HistoryError('registration_conflict')
            reference=prepared.events[0].evidence_ref.split('#')[0]
            evidence=checked_path(reference,self.root)
            if evidence.parent!=path.parent or evidence.suffix!='.json':raise HistoryError('workspace_required')
            if hashlib.sha256(prepared.evidence).hexdigest()!=prepared.evidence_sha256:
                raise HistoryError('evidence_invalid')
            if evidence.exists():
                if evidence.read_bytes()!=prepared.evidence:raise HistoryError('evidence_conflict')
            else:
                if existing is not None:raise HistoryError('evidence_missing')
                try:
                    with evidence.open('xb') as stream:
                        stream.write(prepared.evidence);stream.flush()
                        import os
                        os.fsync(stream.fileno())
                except FileExistsError:
                    if evidence.read_bytes()!=prepared.evidence:raise HistoryError('evidence_conflict')
            register=register_prepared_acoustics if modality=='acoustics' else register_prepared_vitals if modality=='vitals' else register_prepared_prescriptions
            return register(prepared,RegisterMultimodalSession(uow),evidence.read_bytes)

    def register_scenario(self,database,patient_id,modality,scenario,progress=lambda stage:None,*,run_id=None):
        path=self.writable_path(database);progress('validating')
        if modality=='acoustics':return self._register_acoustic(database,patient_id,scenario,progress,run_id=run_id)
        raw=self._input(modality,scenario)
        run=uuid4() if run_id is None else run_id
        reference=(path.parent/f'{modality}_{run}.json').relative_to(self.root).as_posix()
        prepare=prepare_vitals if modality=='vitals' else prepare_prescriptions
        try:
            if modality=='prescriptions' and scenario.startswith('E'):
                bundle=strict_json(raw)
                prepared=prepare_prescription_expectation(encode_json(bundle['pair']),bundle['plan'],run_id=run,evidence_ref=reference)
            else:prepared=prepare(raw,run_id=run,evidence_ref=reference)
        except (ValueError,TypeError,KeyError) as exc:raise HistoryError('structured_input_rejected') from exc
        if prepared.session.subject.patient_id!=patient_id:raise HistoryError('invalid_patient')
        # Check patient before caching/writing evidence; no implicit registry creation.
        with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            if SQLitePatientRepository(connection).get_by_id(patient_id) is None:raise HistoryError('invalid_patient')
        key=str(run);entry=(str(path),modality,scenario,prepared)
        if key in self.structured_prepared and self.structured_prepared[key]!=entry:
            raise HistoryError('registration_conflict')
        self.structured_prepared[key]=entry
        progress('saving')
        try:self._persist(database,modality,prepared)
        except (HistoryError,ValueError,OSError,sqlite3.Error) as exc:
            return StructuredOutcome(key,str(prepared.session.session_id),modality,scenario,False,
                exc.code if isinstance(exc,HistoryError) else 'structured_persistence_failed')
        return StructuredOutcome(key,str(prepared.session.session_id),modality,scenario,True)

    def _register_acoustic(self,database,patient_id,scenario,progress,*,run_id=None):
        if scenario not in self.scenarios('acoustics'):raise HistoryError('structured_input_rejected')
        path=self.writable_path(database)
        with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2)) as connection:
            if SQLitePatientRepository(connection).get_by_id(patient_id) is None:raise HistoryError('invalid_patient')
        source=acoustic_source(self.root,scenario)
        analyzer=self.pause_analyzer_factory() if self.pause_analyzer_factory else LocalPauseAnalyzer(self.root)
        progress('processing')
        try:result=analyzer.analyze(source['audio_ref'],expected_sha256=source['sha256'])
        except AcousticInputError as exc:raise HistoryError('acoustic_input_invalid') from exc
        except AcousticDecoderUnavailable as exc:raise HistoryError('acoustic_decoder_unavailable') from exc
        if result.source_sha256!=source['sha256']:raise HistoryError('acoustic_input_invalid')
        run=uuid4() if run_id is None else run_id
        reference=(path.parent/f'acoustics_{run}.json').relative_to(self.root).as_posix()
        prepared=prepare_acoustics(result.features,source,run_id=run,patient_id=patient_id,
            processed_at=datetime.now(timezone.utc),evidence_ref=reference,is_mock=result.is_mock,
            processing_seconds=result.processing_seconds)
        if strict_json(prepared.evidence)['assessment']!=strict_json(encode_json(asdict(result.assessment))):
            raise HistoryError('evidence_invalid')
        key=str(run);entry=(str(path),'acoustics',scenario,prepared)
        if key in self.structured_prepared and self.structured_prepared[key]!=entry:raise HistoryError('registration_conflict')
        self.structured_prepared[key]=entry;progress('saving')
        try:self._persist(database,'acoustics',prepared)
        except (HistoryError,ValueError,OSError,sqlite3.Error) as exc:
            return StructuredOutcome(key,str(prepared.session.session_id),'acoustics',scenario,False,
                exc.code if isinstance(exc,HistoryError) else 'structured_persistence_failed')
        return StructuredOutcome(key,str(prepared.session.session_id),'acoustics',scenario,True)

    def retry_structured(self,database,run_id):
        path=self.writable_path(database)
        if run_id not in self.structured_prepared:raise HistoryError('no_pending_registration')
        original,modality,scenario,prepared=self.structured_prepared[run_id]
        if str(path)!=original:raise HistoryError('workspace_required')
        try:self._persist(database,modality,prepared)
        except HistoryError:raise
        except (ValueError,OSError,sqlite3.Error) as exc:raise HistoryError('structured_persistence_failed') from exc
        return StructuredOutcome(run_id,str(prepared.session.session_id),modality,scenario,True)

    def review(self,database,session_id,request,expected_evidence_ref):
        path=self.writable_path(database)
        detail=self.reader.detail(str(path),session_id).document
        row=next((r for r in detail['events'] if r['event']['event_id']==str(request.event_id)),None)
        if row is None or row['event']['evidence_ref']!=expected_evidence_ref:raise HistoryError('evidence_invalid')
        with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            try:return review_event_sqlite(request,connection=connection)
            except ValueError as exc:raise HistoryError('review_conflict') from exc
