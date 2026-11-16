"""Standalone simulated acoustic evidence; does not require ASR or a language model."""
from dataclasses import asdict,dataclass
from datetime import datetime
import hashlib
import math
import re
from uuid import UUID,uuid5

from .register_vitals import encode_json
from medassistmultimodal.domain.audio_features import AudioFeatures,LowEnergyInterval
from medassistmultimodal.domain.internal_pauses import detect_internal_pauses
from medassistmultimodal.domain.session import Session,SubjectIdentity,SubjectKind,require_uuid,utc_datetime
from medassistmultimodal.domain.events import MultimodalEvent,SourceKind


@dataclass(frozen=True,slots=True)
class PreparedAcoustics:
    run_id: UUID
    session: Session
    events: tuple[MultimodalEvent,...]
    evidence: bytes
    evidence_sha256: str


def prepare_acoustics(features,source,*,run_id,patient_id,processed_at,evidence_ref,is_mock=False,processing_seconds=0.):
    require_uuid(run_id,'run_id');processed_at=utc_datetime(processed_at,'processed_at')
    if type(is_mock) is not bool or isinstance(processing_seconds,bool) or not isinstance(processing_seconds,(int,float)) or not math.isfinite(processing_seconds) or processing_seconds<0:
        raise ValueError('Invalid processing metadata')
    if (source['case_id'] not in ('AP01','AP02','AP03') or source['origin_kind']!='tts'
        or source['permission_declared'] is not True or not source['permission_ref']
        or not isinstance(source['sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',source['sha256'])
        or not source['audio_ref'].startswith('data/interim/audio/elevenlabs_tests/')
        or any(p in ('..','_backup','.git') for p in source['audio_ref'].split('/'))):raise ValueError('Invalid acoustic origin')
    subject=SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT,patient_id=patient_id)
    session=Session(session_id=uuid5(run_id,'session'),subject=subject,started_at=processed_at)
    result=asdict(detect_internal_pauses(features))
    doc=dict(schema_version='acoustic-pause-evidence-v1',run_id=str(run_id),subject=asdict(subject),
        processed_at=processed_at.isoformat(),time_basis='processing_utc_and_audio_relative_seconds',
        input=source,features=asdict(features),assessment=result,is_mock=is_mock,
        processing_seconds=processing_seconds,asr='not_run',llm='not_run',clinical_validation=False,
        summary=dict(status=result['status'],reason=result['reason'],case_id=source['case_id']),
        candidates=[result] if result['status']=='signal' else [])
    raw=encode_json(doc);sha=hashlib.sha256(raw).hexdigest()
    fragments=['summary']+(['candidates/0'] if doc['candidates'] else [])
    events=tuple(MultimodalEvent(event_id=uuid5(run_id,f'{sha}:{fragment}'),session_id=session.session_id,
        subject_kind=subject.kind,patient_id=patient_id,source_kind=SourceKind.SIMULATED,
        source='simulated-acoustic-pauses-v1',timestamp=processed_at,confidence=None,
        evidence_ref=f'{evidence_ref}#sha256={sha}&item=/{fragment}',processor='internal-pauses-v1',is_mock=is_mock) for fragment in fragments)
    return PreparedAcoustics(run_id,session,events,raw,sha)


def restore_acoustics(doc,reference):
    if doc['schema_version']!='acoustic-pause-evidence-v1':raise ValueError('Unsupported acoustic schema')
    f=dict(doc['features']);f['low_energy_intervals']=tuple(LowEnergyInterval(**x) for x in f['low_energy_intervals'])
    return prepare_acoustics(AudioFeatures(**f),doc['input'],run_id=UUID(doc['run_id']),
        patient_id=doc['subject']['patient_id'],processed_at=datetime.fromisoformat(doc['processed_at']),
        evidence_ref=reference,is_mock=doc['is_mock'],processing_seconds=doc['processing_seconds'])


def register_prepared_acoustics(prepared,use_case,read_evidence):
    if read_evidence()!=prepared.evidence:raise ValueError('Acoustic evidence differs')
    return use_case.execute(prepared.session,prepared.events,correlation_id=uuid5(prepared.run_id,'register-acoustics'))


def acoustic_lines(doc):
    r=doc['assessment'];p=r['profile'];s=doc['input']
    labels={'signal':'Padrão experimental de pausas frequentes — requer revisão',
        'no_signal':'Sem sinal do perfil de pausas; não comprova normalidade',
        'insufficient_evidence':'Evidência acústica insuficiente'}
    fraction='Indisponível' if r['long_pause_fraction'] is None else f"{r['long_pause_fraction']:.1%}"
    lines=[labels[r['status']],f"Áudio simulado {s['case_id']} | Voz: {s.get('voice_name','Não informada')} | Modelo TTS: {s.get('tts_model','Não informado')}",
        f"Motivo: {r['reason']} | Pausas longas: {r['long_pause_count']} | Fração central: {fraction}",
        f"Critério: pelo menos {p['min_long_pauses']} pausas >= {p['long_pause_seconds']} s e fração >= {p['min_fraction_percent']}%.",
        'Energia é uma medida técnica: não identifica respiração, cansaço ou condição médica.',
        'ASR e LLM não executados nesta análise. Os intervalos abaixo são calculados, não anotações humanas.']
    for x in r['long_pauses']:lines.append(f"• Pausa: {x['start_seconds']:.3f}–{x['end_seconds']:.3f} s | duração {x['duration_seconds']:.3f} s")
    lines += [f"Fonte: {s['audio_ref']} | SHA-256: {s['sha256']}",f"Processamento UTC: {doc['processed_at']} | Mock: {doc['is_mock']}"]
    return lines
