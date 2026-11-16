"""Known local RGB clip, bounded extraction, verified dataset sessions and work-copy writes."""
from contextlib import closing
from dataclasses import asdict,replace
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import re
import sqlite3
from uuid import UUID,uuid4,uuid5

from medassistmultimodal.application.desktop_history import HistoryError,SessionDetail
from medassistmultimodal.application.register_vitals import strict_json,encode_json
from medassistmultimodal.application.register_video import prepare_video,restore_video
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.application.movement_inspection import inspect_pose
from medassistmultimodal.domain.temporal_quality import OriginalAngle,OriginalFrame
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.domain.session import SubjectKind
from medassistmultimodal.providers.whisper_local import checked_path
from .video_pose import VideoReader,MediaPipePose
from .desktop_vitals import MultimodalHistoryReader
from .structured_workspace import StructuredWorkspace,StructuredOutcome
from .sqlite_session_repository import SQLiteSessionRepository
from .sqlite_event_repository import SQLiteEventRepository
from .sqlite_event_review import event_review_history
from .sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork

MANIFEST='data/manifests/day07_rgb_assets.json'
PARTICIPANT='P-0236ac1b114742088a082d0b6163bae1'
# Known development intervals only; reference labels never enter the detector.
ELBOW_CASES=dict(zip((f'D9-{i:02}' for i in range(1,11)),
    ((20,99),(111,199),(736,885),(897,1056),(5160,5212),(7266,7332),
     (7927,8002),(13933,13999),(14509,14590),(14599,14690))))


def validate_interval(first,last,case_id=None):
    if type(first) is not int or type(last) is not int:raise HistoryError('video_interval_invalid')
    if case_id is None:
        valid=0<=first<=last<=449
    else:
        valid=isinstance(case_id,str) and ELBOW_CASES.get(case_id)==(first,last)
    if not valid:raise HistoryError('video_interval_invalid')


def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024**2),b''):sha.update(chunk)
    return sha.hexdigest()


def assets(root):
    try:
        manifest=strict_json(checked_path(MANIFEST,root).read_bytes())
        if manifest['video']['participant_ref']!=PARTICIPANT or manifest['video']['group']!='development':raise ValueError()
        for name in ('video','model'):
            item=manifest[name];path=checked_path(item['path'],root)
            if digest(path)!=item['sha256']:raise ValueError()
        return manifest
    except (ValueError,OSError,KeyError,TypeError) as exc:raise HistoryError('video_assets_invalid') from exc


class VideoHistoryReader(MultimodalHistoryReader):
    def dataset_sessions(self,database):
        with self._connection(database) as connection:
            return SQLiteSessionRepository(connection).list_for_dataset_participant('rehab26-v1',PARTICIPANT)

    def detail(self,database,session_id):
        with self._connection(database) as connection:
            session=SQLiteSessionRepository(connection).get_by_id(session_id)
            if session is None:raise HistoryError('session_not_found')
            if session.subject.kind is not SubjectKind.DATASET_PARTICIPANT:return super().detail(database,session_id)
            try:
                events=SQLiteEventRepository(connection).list_for_session(session_id)
                if not events or any(e.source!='rehab26-rgb-video-v1' for e in events):raise ValueError()
                refs={e.evidence_ref.split('#')[0] for e in events}
                if len(refs)!=1:raise ValueError()
                reference=refs.pop();path=checked_path(reference,self.root)
                if not path.is_relative_to(self.root/'data/interim/audio/desktop_workspaces_v1'):raise ValueError()
                try:raw=path.read_bytes()
                except FileNotFoundError as exc:raise HistoryError('evidence_missing') from exc
                doc=strict_json(raw)
                if doc['schema_version'] not in ('rgb-video-evidence-v1','rgb-video-evidence-v2'):raise ValueError()
                restored=restore_video(doc,reference)
                if restored.evidence!=raw or restored.session!=session:raise ValueError()
                expected={e.event_id:e for e in restored.events}
                if set(expected)!={e.event_id for e in events}:raise ValueError()
                rows=[]
                for e in events:
                    if replace(e,review_status=ReviewStatus.PENDING_REVIEW)!=expected[e.event_id]:raise ValueError()
                    fragment=e.evidence_ref.split('&item=/')[1].split('/')
                    item=doc[fragment[0]] if len(fragment)==1 else doc[fragment[0]][int(fragment[1])]
                    metadata=asdict(e);metadata.update(event_id=str(e.event_id),session_id=str(e.session_id),timestamp=e.timestamp.isoformat())
                    rows.append(dict(event=metadata,evidence_item=item,modality='video'))
                return SessionDetail(encode_json(dict(session=dict(session_id=str(session_id),subject_kind=session.subject.kind,
                    patient_id=None,dataset_id=session.subject.dataset_id,participant_ref=session.subject.participant_ref,started_at=session.started_at.isoformat()),
                    events=rows,documents=[],vitals=[],prescriptions=[],videos=[dict(reference=reference,sha256=restored.evidence_sha256,evidence=doc)],
                    integrity='verified',unsupported_sources=[],review_histories={str(e.event_id):event_review_history(e.event_id,connection=connection) for e in events},
                    clinical_validation=False,access_mode='read_only')))
            except HistoryError:raise
            except (ValueError,KeyError,TypeError,OSError,IndexError,AttributeError) as exc:raise HistoryError('evidence_invalid') from exc


class VideoWorkspace(StructuredWorkspace):
    def __init__(self,root,**kwargs):
        super().__init__(root,**kwargs);self.reader=VideoHistoryReader(self.root);self.video_prepared={}

    def process_video(self,database,first,last,progress=lambda stage:None,*,case_id=None):
        path=self.writable_path(database)
        validate_interval(first,last,case_id)
        progress('validating');manifest=assets(self.root);source=manifest['video'];model=manifest['model']
        originals=[];progress('processing_video')
        with VideoReader(checked_path(source['path'],self.root)) as reader,MediaPipePose(checked_path(model['path'],self.root)) as detector:
            if reader.info.fps!=30:raise HistoryError('video_interval_invalid')
            for frame in reader.frames(first,last):
                row=inspect_pose(detector.detect(frame),min_visibility=.5)
                originals.append(OriginalFrame(frame.index,
                    **{name:OriginalAngle(row['measurements'][name]['degrees'],row['measurements'][name]['reason']) for name in ('right_elbow','right_arm_trunk')},
                    visibility=tuple((i,row['visibility'][str(i)]) for i in (12,14,16,24))))
        if digest(checked_path(source['path'],self.root))!=source['sha256'] or digest(checked_path(model['path'],self.root))!=model['sha256']:raise HistoryError('video_assets_invalid')
        run=uuid4();reference=(path.parent/f'video_{run}.json').relative_to(self.root).as_posix()
        import cv2
        meta=dict(dataset_id='rehab26-v1',participant_ref=source['participant_ref'],group=source['group'],video_ref=source['path'],
            video_sha256=source['sha256'],model_ref=model['path'],model_sha256=model['sha256'],first_frame=first,last_frame=last,fps=30,
            declared_frames=reader.info.declared_frames,is_mock=False,coordinate_space='mediapipe_tasks_world_meters',
            opencv_version=cv2.__version__,mediapipe_version=importlib.metadata.version('mediapipe'))
        if case_id is not None:meta.update(camera=1,case_id=case_id)
        prepared=prepare_video(originals,meta,run_id=run,processed_at=datetime.now(timezone.utc),evidence_ref=reference,
            analyze_elbow=case_id is not None)
        self.video_prepared[str(run)]=(str(path),prepared);progress('saving')
        try:self._persist_video(database,prepared)
        except (HistoryError,ValueError,OSError,sqlite3.Error):return StructuredOutcome(str(run),str(prepared.session.session_id),'video','RGB',False,'structured_persistence_failed')
        return StructuredOutcome(str(run),str(prepared.session.session_id),'video','RGB',True)

    def _persist_video(self,database,prepared):
        path=self.writable_path(database)
        with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON');uow=SQLiteMultimodalUnitOfWork(connection)
            existing=uow.sessions.get_by_id(prepared.session.session_id)
            if existing is not None and (existing!=prepared.session or set(uow.events.list_for_session(existing.session_id))!=set(prepared.events)):
                raise HistoryError('registration_conflict')
            reference=prepared.events[0].evidence_ref.split('#')[0];file=checked_path(reference,self.root)
            if file.parent!=path.parent:raise HistoryError('workspace_required')
            if file.exists():
                if file.read_bytes()!=prepared.evidence:raise HistoryError('evidence_conflict')
            else:
                if existing:raise HistoryError('evidence_missing')
                with file.open('xb') as stream:stream.write(prepared.evidence)
            if file.read_bytes()!=prepared.evidence or digest(file)!=prepared.evidence_sha256:raise HistoryError('evidence_invalid')
            return RegisterMultimodalSession(uow).execute(prepared.session,prepared.events,correlation_id=uuid5(prepared.run_id,'register-video'))

    def retry_video(self,database,run):
        path=self.writable_path(database)
        if run not in self.video_prepared:raise HistoryError('no_pending_registration')
        original,prepared=self.video_prepared[run]
        if original!=str(path):raise HistoryError('workspace_required')
        self._persist_video(database,prepared)
        return StructuredOutcome(run,str(prepared.session.session_id),'video','RGB',True)

    def preview(self,index):
        if type(index) is not int or not (0<=index<=449 or any(a<=index<=b for a,b in ELBOW_CASES.values())):
            raise HistoryError('video_interval_invalid')
        manifest=assets(self.root)
        import cv2
        with VideoReader(checked_path(manifest['video']['path'],self.root)) as reader:
            frame=next(reader.frames(index,index));image=frame.rgb
            scale=min(720/image.shape[1],960/image.shape[0],1.0);image=cv2.resize(image,(round(image.shape[1]*scale),round(image.shape[0]*scale)))
            return f'P6\n{image.shape[1]} {image.shape[0]}\n255\n'.encode('ascii')+image.tobytes()
