"""Bounded RGB temporal evidence on a dataset identity; no clinical classification."""
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
from uuid import UUID, uuid5

from .register_vitals import encode_json
from medassistmultimodal.domain.session import Session,SubjectIdentity,SubjectKind,require_uuid,utc_datetime
from medassistmultimodal.domain.events import MultimodalEvent,SourceKind
from medassistmultimodal.domain.temporal_quality import OriginalAngle,OriginalFrame,QualityProfile,assess_angular_quality
from medassistmultimodal.domain.temporal_segmentation import SegmentationProfile,segment_repetitions
from medassistmultimodal.domain.elbow_deviation import detect_elbow_deviation


@dataclass(frozen=True,slots=True)
class PreparedVideo:
    run_id: UUID
    session: Session
    events: tuple[MultimodalEvent,...]
    evidence: bytes
    evidence_sha256: str


def prepare_video(frames,source,*,run_id,processed_at,evidence_ref,analyze_elbow=False):
    require_uuid(run_id,'run_id');processed_at=utc_datetime(processed_at,'processed_at')
    frames=tuple(frames)
    first=source['first_frame'];last=source['last_frame']
    if type(analyze_elbow) is not bool:raise ValueError('Explicit analysis mode required')
    limit=15148 if analyze_elbow else 449
    if (type(first) is not int or type(last) is not int or not 0<=first<=last<=limit
        or last-first+1>450 or [f.frame_index for f in frames]!=list(range(first,last+1))):raise ValueError('Invalid bounded interval')
    if source['fps']!=30 or source['group']!='development':raise ValueError('Unsupported video source')
    if source['dataset_id']!='rehab26-v1' or not source['participant_ref'].startswith('P-'):raise ValueError('Dataset identity required')
    if type(source['is_mock']) is not bool:raise ValueError('Mock declaration required')
    if analyze_elbow and (source.get('coordinate_space')!='mediapipe_tasks_world_meters'
        or type(source.get('camera')) is not int or source['camera']!=1
        or type(source.get('declared_frames')) is not int or last>=source['declared_frames']):
        raise ValueError('World 3D camera 1 source required')
    for name in ('video_sha256','model_sha256'):
        value=source[name]
        if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid hash')
    subject=SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT,dataset_id=source['dataset_id'],participant_ref=source['participant_ref'])
    session=Session(session_id=uuid5(run_id,'session'),subject=subject,started_at=processed_at)
    quality=assess_angular_quality(frames,evidence_ref=source['video_ref'],profile=QualityProfile())
    segments=segment_repetitions(quality,profile=SegmentationProfile())
    coverage={name:sum(getattr(f,name).usable_degrees is not None for f in quality.frames)/len(frames) for name in ('right_elbow','right_arm_trunk')}
    intervals=[]
    for name in ('right_elbow','right_arm_trunk'):
        for f in quality.frames:
            angle=getattr(f,name)
            if angle.usable_degrees is not None:continue
            reason=angle.original.reason or 'angular_discontinuity';index=f.original.frame_index
            if intervals and intervals[-1]['measure']==name and intervals[-1]['reason']==reason and intervals[-1]['last_frame']==index-1:
                intervals[-1]['last_frame']=index
            else:intervals.append(dict(measure=name,reason=reason,first_frame=index,last_frame=index))
    doc=dict(schema_version='rgb-video-evidence-v1',run_id=str(run_id),subject=asdict(subject),
        processed_at=processed_at.isoformat(),time_basis='processing_utc_and_video_relative_frames',source=source,
        processor='rgb-temporal-v1',quality_profile=asdict(quality.profile),segmentation_profile=asdict(segments.profile),
        original_frames=[asdict(f) for f in frames],
        timeline=[dict(frame=f.original.frame_index,seconds=f.nominal_seconds,
            **{name:dict(degrees=getattr(f,name).usable_degrees,state=getattr(f,name).state.value) for name in coverage}) for f in quality.frames],
        cycles=[asdict(c) for c in segments.cycles],quality_intervals=intervals,
        notices=[asdict(n) for n in segments.notices],
        summary=dict(input_frames=len(frames),detected_cycles=len(segments.cycles),coverage=coverage,quality_intervals=len(intervals)),
        clinical_validation=False,exercise_correctness_evaluated=False,temporal_alignment_with_npy_validated=False)
    if analyze_elbow:
        result=asdict(detect_elbow_deviation(frames,first,last))
        doc.update(schema_version='rgb-video-evidence-v2',processor='rgb-elbow-v1',
            elbow_analysis=result,interval_basis='caller_supplied_not_automatic_segmentation',
            deviation_candidates=[result] if result['status']=='deviation' else [])
    raw=encode_json(doc);sha=hashlib.sha256(raw).hexdigest()
    fragments=['summary']+[f'cycles/{i}' for i in range(len(segments.cycles))]+[f'quality_intervals/{i}' for i in range(len(intervals))]
    if analyze_elbow and doc['deviation_candidates']:fragments.append('deviation_candidates/0')
    events=tuple(MultimodalEvent(event_id=uuid5(run_id,f'{sha}:{fragment}'),session_id=session.session_id,
        subject_kind=subject.kind,patient_id=None,dataset_id=subject.dataset_id,participant_ref=subject.participant_ref,
        source_kind=SourceKind.DATASET,source='rehab26-rgb-video-v1',timestamp=processed_at,
        confidence=None,evidence_ref=f'{evidence_ref}#sha256={sha}&item=/{fragment}',processor=doc['processor'],
        is_mock=source['is_mock']) for fragment in fragments)
    return PreparedVideo(run_id,session,events,raw,sha)


def restore_video(document,evidence_ref):
    """Recheck bounded deterministic quality/segmentation; never decode or infer pose."""
    if document['schema_version'] not in ('rgb-video-evidence-v1','rgb-video-evidence-v2'):raise ValueError('Unsupported schema')
    frames=tuple(OriginalFrame(frame_index=f['frame_index'],
        right_elbow=OriginalAngle(**f['right_elbow']),right_arm_trunk=OriginalAngle(**f['right_arm_trunk']),
        visibility=tuple(tuple(p) for p in f['visibility'])) for f in document['original_frames'])
    return prepare_video(frames,document['source'],run_id=UUID(document['run_id']),
        processed_at=datetime.fromisoformat(document['processed_at']),evidence_ref=evidence_ref,
        analyze_elbow=document['schema_version']=='rgb-video-evidence-v2')
