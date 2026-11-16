"""Injected, local-evidence audio pipeline. No persistence or provider creation."""
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Literal, Protocol
from uuid import UUID

from medassistmultimodal.domain.audio_features import AudioFeatures
from medassistmultimodal.domain.session import (
    SubjectIdentity, SubjectKind, require_uuid, require_text, utc_datetime,
)
from medassistmultimodal.domain.text_context import TermMention, detect_term_contexts
from medassistmultimodal.domain.text_analysis_v3 import (
    InvalidTextResponse, TextCapacityError, check_input, validate_text_response_v3,
)
from medassistmultimodal.providers.whisper_local import WhisperRun, checked_path
from .audio import Transcript, AudioNoSpeechError, AudioProviderUnavailableError
from .llm import LLMProviderTimeoutError, LLMProviderInvalidResponseError, LLMProviderError
from .text_analysis_v3 import SYSTEM_PROMPT_V3, TextResponseProviderV3
from .register_vitals import encode_json


class DetailedTranscriber(Protocol):
    def transcribe_with_details(self, audio_ref: str, *, language: str = 'pt-BR') -> WhisperRun: ...


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    name: str
    model: str
    version: str
    source: Literal['mock', 'whisper', 'ollama_local', 'ollama_cloud']
    is_mock: bool

    def __post_init__(self):
        for field in ('name', 'model', 'version'): require_text(getattr(self, field), field)
        if self.source not in ('mock', 'whisper', 'ollama_local', 'ollama_cloud'):
            raise ValueError('Unsupported provider source')
        if type(self.is_mock) is not bool or self.is_mock != (self.source == 'mock'):
            raise ValueError('Mock identity must be explicit and consistent')


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioProcessingRequest:
    run_id: UUID
    session_id: UUID
    patient_id: str
    session_timestamp: datetime
    processing_timestamp: datetime
    audio_ref: str
    expected_sha256: str
    origin_ref: str
    permission_ref: str
    origin_kind: Literal['human_recording', 'synthetic_tts']
    permission_declared: bool
    llm_enabled: bool = False
    cloud_text_authorized: bool = False


@dataclass(frozen=True, slots=True)
class ProcessedAudio:
    status: Literal['completed', 'degraded', 'failed', 'rejected']
    evidence: bytes
    evidence_sha256: str

    @property
    def document(self):
        """Fresh decoded view; callers cannot mutate the prepared evidence bytes."""
        return json.loads(self.evidence)


def _finite(value, *, positive=False):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and (value > 0 if positive else value >= 0))


def _valid_features(value):
    if not isinstance(value, AudioFeatures): return False
    if (not value.version or type(value.sample_rate_hz) is not int or value.sample_rate_hz <= 0
            or type(value.sample_count) is not int or value.sample_count <= 0): return False
    if not all(_finite(getattr(value, k), positive=True) for k in (
        'duration_seconds', 'energy_window_seconds', 'low_energy_rms_threshold',
        'minimum_low_energy_seconds')): return False
    if not all(_finite(getattr(value, k)) for k in ('rms_normalized', 'peak_abs_normalized')): return False
    if abs(value.duration_seconds-value.sample_count/value.sample_rate_hz) > 1e-6: return False
    if not isinstance(value.low_energy_intervals, tuple): return False
    previous = 0.0
    for interval in value.low_energy_intervals:
        if (not _finite(interval.start_seconds) or not _finite(interval.end_seconds)
                or not previous <= interval.start_seconds < interval.end_seconds <= value.duration_seconds):
            return False
        previous = interval.end_seconds
    return True


class ProcessAudio:
    """Prepare one immutable execution; rerunning ASR is a new execution, not retry."""

    def __init__(self, *, root: Path, patient_exists: Callable[[str], bool],
                 transcriber: DetailedTranscriber, asr_identity: ProviderIdentity,
                 text_provider: TextResponseProviderV3 | None = None,
                 text_identity: ProviderIdentity | None = None,
                 rule_detector=detect_term_contexts):
        if asr_identity.source not in ('mock', 'whisper'):
            raise ValueError('ASR must be local Whisper or explicit mock')
        if text_identity is not None and text_identity.source not in ('mock', 'ollama_local', 'ollama_cloud'):
            raise ValueError('Text identity must identify text processing')
        self.root = Path(root).absolute()
        self.patient_exists = patient_exists
        self.transcriber = transcriber
        self.asr_identity = asr_identity
        self.text_provider = text_provider
        self.text_identity = text_identity
        self.rule_detector = rule_detector
        self.rule_is_mock = rule_detector is not detect_term_contexts

    def execute(self, request: AudioProcessingRequest) -> ProcessedAudio:
        document = dict(schema_version='audio-processing-evidence-v1', identity=None, time=None,
                        input=dict(status='rejected', error=None),
                        asr=dict(status='not_run', provider=None, result=None, error=None),
                        acoustics=dict(status='not_run', result=None, error=None),
                        rules=dict(status='not_run', version='context-terms-v1', items=None, error=None),
                        llm=dict(status='not_run', provider=None, protocol='text-analysis-v3',
                                 input_sha256=None, result=None, error=None, seconds=None),
                        summary=dict(status='rejected', counts=None, clinical_validation=False))

        def finish(status):
            document['summary']['status'] = status
            items = document['rules']['items']
            if items is not None:
                document['summary']['counts'] = dict(
                    mentions=len(items),
                    by_context=dict(Counter(i['context'] for i in items)),
                    by_classification=dict(Counter(i['classification'] for i in items)))
            evidence = encode_json(document)
            return ProcessedAudio(status, evidence, hashlib.sha256(evidence).hexdigest())

        try:
            if not isinstance(request, AudioProcessingRequest): raise ValueError('Invalid request')
            require_uuid(request.run_id, 'run_id'); require_uuid(request.session_id, 'session_id')
            SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT, patient_id=request.patient_id)
            if self.patient_exists(request.patient_id) is not True: raise ValueError('Unknown fictional patient')
            session_time = utc_datetime(request.session_timestamp, 'session_timestamp')
            process_time = utc_datetime(request.processing_timestamp, 'processing_timestamp')
            if request.origin_kind not in ('human_recording', 'synthetic_tts'): raise ValueError('Origin required')
            if request.permission_declared is not True: raise ValueError('Permission declaration required')
            if type(request.llm_enabled) is not bool or type(request.cloud_text_authorized) is not bool:
                raise ValueError('Explicit boolean settings required')
            if not isinstance(request.expected_sha256, str) or re.fullmatch('[0-9a-f]{64}', request.expected_sha256) is None:
                raise ValueError('SHA256 required')
            audio = checked_path(request.audio_ref, self.root)
            if not audio.is_file() or audio.suffix.lower() not in ('.wav', '.mp3', '.m4a'):
                raise ValueError('Unsupported media')
            safe_refs = {}
            provenance_hashes = {}
            for field in ('origin_ref', 'permission_ref'):
                value = checked_path(getattr(request, field), self.root)
                if not value.is_file(): raise ValueError('Missing provenance reference')
                safe_refs[field] = value.relative_to(self.root).as_posix()
                provenance_hashes[field+'_sha256'] = hashlib.sha256(value.read_bytes()).hexdigest()
            observed = hashlib.sha256(audio.read_bytes()).hexdigest()
            document['identity'] = dict(run_id=str(request.run_id), session_id=str(request.session_id),
                patient_id=request.patient_id, subject_kind='synthetic_patient', source_kind='simulated')
            document['time'] = dict(session_timestamp_utc=session_time.isoformat(),
                processing_timestamp_utc=process_time.isoformat(), time_basis='explicit_session_and_processing_utc')
            document['input'].update(audio_ref=audio.relative_to(self.root).as_posix(),
                expected_sha256=request.expected_sha256, observed_sha256=observed,
                format=audio.suffix.lower(), origin_kind=request.origin_kind,
                permission_declared=True, **safe_refs, **provenance_hashes)
            if observed != request.expected_sha256: raise ValueError('Hash mismatch')
            document['input']['status'] = 'accepted'
        except (ValueError, TypeError, OSError):
            document['input'].update(status='rejected', error='invalid_input_or_provenance')
            return finish('rejected')

        asr = document['asr']; asr['provider'] = asdict(self.asr_identity)
        started = time.perf_counter()
        try:
            if self.transcriber is None:
                raise AudioProviderUnavailableError('ASR not configured')
            run = self.transcriber.transcribe_with_details(document['input']['audio_ref'], language='pt-BR')
            if not isinstance(run, WhisperRun) or not isinstance(run.transcript, Transcript):
                raise ValueError('Invalid ASR contract')
            transcript = run.transcript
            transcript.__post_init__()
            expected_ref = f"{document['input']['audio_ref']}#sha256={request.expected_sha256}"
            if (transcript.source != self.asr_identity.source or transcript.language != 'pt-BR'
                    or transcript.evidence_ref != expected_ref or run.source_sha256 != request.expected_sha256
                    or not _finite(run.processing_seconds)):
                raise ValueError('Invalid ASR provenance')
            if _valid_features(run.features) and any(
                    s.end_seconds > run.features.duration_seconds+0.02 for s in transcript.segments):
                raise ValueError('ASR segment outside decoded duration')
            asr.update(status='succeeded', result=asdict(transcript),
                       input_text_sha256=hashlib.sha256(transcript.text.encode()).hexdigest())
        except AudioNoSpeechError:
            asr.update(status='no_speech', error='no_speech')
        except AudioProviderUnavailableError:
            asr.update(status='unavailable', error='asr_unavailable')
        except (ValueError, TypeError, AttributeError):
            asr.update(status='invalid_output', error='invalid_asr_output')
        except Exception:
            asr.update(status='unavailable', error='asr_provider_error')
        asr['seconds'] = time.perf_counter()-started

        def unchanged():
            try:
                checked_path(str(audio), self.root)
                digest = hashlib.sha256(audio.read_bytes()).hexdigest()
                document['input']['final_sha256'] = digest
                return digest == request.expected_sha256
            except (ValueError, OSError): return False

        if not unchanged():
            document['input'].update(status='rejected', error='source_changed_during_processing')
            asr.update(status='invalid_output', result=None, error='source_changed_during_processing')
            return finish('rejected')
        if asr['status'] != 'succeeded':
            document['acoustics'].update(status='unavailable', error='bundled_asr_result_unavailable')
            return finish('failed')

        try:
            if not _valid_features(run.features): raise ValueError('Invalid features')
            if any(s.end_seconds > run.features.duration_seconds+0.02 for s in transcript.segments):
                raise ValueError('Segments outside audio')
            document['acoustics'].update(status='succeeded', result=asdict(run.features),
                processor=run.features.version, units='seconds; Hz; sample_count; normalized amplitude',
                is_mock=self.asr_identity.is_mock)
        except (ValueError, TypeError, AttributeError):
            document['acoustics'].update(status='unavailable', error='invalid_acoustic_output')

        text = transcript.text
        rules = document['rules']
        if len(text) > 4000:
            rules.update(status='unsupported_input', error='text_over_4000_characters')
        else:
            try:
                mentions = self.rule_detector(text)
                items = []
                for mention in mentions:
                    if not isinstance(mention, TermMention): raise ValueError('Invalid rule result')
                    if (not 0 <= mention.start < mention.end <= len(text)
                            or text[mention.start:mention.end] != mention.quote):
                        raise ValueError('Invalid rule evidence')
                    if mention.context == 'affirmed_current': classification = 'candidate_for_human_review'
                    elif mention.context == 'unknown': classification = 'context_uncertain'
                    elif mention.context in ('negated_current', 'conditional', 'third_party',
                                              'affirmed_historical', 'affirmed_earlier_in_session'):
                        classification = 'context_information'
                    else: raise ValueError('Invalid rule context')
                    items.append(dict(**asdict(mention), classification=classification,
                                      review_status='pending_review', confidence=None))
                rules.update(status='succeeded_with_mentions' if items else 'succeeded_no_mentions',
                             items=items, is_mock=self.rule_is_mock)
            except Exception:
                rules.update(status='unavailable', error='rule_processing_error', items=None)

        llm = document['llm']
        if not request.llm_enabled:
            llm['status'] = 'disabled'
        else:
            identity = self.text_identity
            if identity: llm['provider'] = asdict(identity)
            llm['input_sha256'] = asr['input_text_sha256']
            try:
                check_input(text)
                if self.text_provider is None or identity is None:
                    llm.update(status='not_configured', error='text_provider_not_configured')
                elif identity.source == 'ollama_cloud' and not request.cloud_text_authorized:
                    llm.update(status='not_configured', error='cloud_text_not_authorized')
                else:
                    llm['cloud_text_authorized'] = request.cloud_text_authorized
                    started = time.perf_counter()
                    try:
                        content = self.text_provider.generate(system_prompt=SYSTEM_PROMPT_V3, text=text)
                        analysis = validate_text_response_v3(content, text, source=identity.source, model=identity.model)
                        llm.update(status='succeeded', result=asdict(analysis))
                    finally:
                        llm['seconds'] = time.perf_counter()-started
            except TextCapacityError:
                llm.update(status='unsupported_input', error='more_than_eight_term_occurrences')
            except (InvalidTextResponse, LLMProviderInvalidResponseError):
                llm.update(status='invalid_response', error='invalid_text_response')
            except (LLMProviderTimeoutError, TimeoutError):
                llm.update(status='timeout', error='text_provider_timeout')
            except (LLMProviderError, AudioProviderUnavailableError):
                llm.update(status='unavailable', error='text_provider_unavailable')
            except ValueError:
                llm.update(status='unsupported_input', error='text_input_unsupported')
            except Exception:
                llm.update(status='unavailable', error='text_provider_error')
        if not unchanged():
            document['input'].update(status='rejected', error='source_changed_during_processing')
            return finish('rejected')
        complete = (document['acoustics']['status'] == 'succeeded'
                    and rules['status'] in ('succeeded_with_mentions', 'succeeded_no_mentions')
                    and llm['status'] in ('disabled', 'succeeded'))
        return finish('completed' if complete else 'degraded')
