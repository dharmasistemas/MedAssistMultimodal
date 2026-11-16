"""Optional GPT-OSS/prompt-v2 audio runs over frozen processing and persistence contracts."""
from contextlib import closing
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import sqlite3
from uuid import uuid4

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.process_audio import ProcessAudio,AudioProcessingRequest,ProviderIdentity,ProcessedAudio
from medassistmultimodal.application.register_audio import prepare_audio_registration
from medassistmultimodal.application.register_vitals import strict_json,encode_json
from medassistmultimodal.application.text_analysis_v3 import SYSTEM_PROMPT_V3 as ORIGINAL_PROMPT
from medassistmultimodal.application.text_analysis_v3_prompt_v2 import SYSTEM_PROMPT_V3 as PROMPT_V2
from medassistmultimodal.domain.text_analysis_v3 import validate_text_response_v3
from medassistmultimodal.domain.session import utc_datetime
from medassistmultimodal.providers.ollama_text_v3_prompt_v2 import OllamaTextProviderV3,TextRuntimeV3
from medassistmultimodal.providers.whisper_local import checked_path
from .desktop_video import VideoWorkspace,VideoHistoryReader
from .desktop_workspace import CORPUS,ProcessOutcome
from .sqlite_patient_repository import SQLitePatientRepository
from .sqlite_audio_registration import register_audio_sqlite
from .audio_evidence_store import AudioEvidenceStore

PROMPT_SHA256=hashlib.sha256(PROMPT_V2.encode('utf-8')).hexdigest()
RUNTIME=TextRuntimeV3(timeout_seconds=60)


class PromptV2Bridge:
    """Explicitly translate the frozen processor's prompt to the evaluated revision."""
    def __init__(self,provider):self.provider=provider;self.final_content=None
    def generate(self,*,system_prompt,text):
        if system_prompt!=ORIGINAL_PROMPT:raise ValueError('Unexpected processor prompt')
        content=self.provider.generate(system_prompt=PROMPT_V2,text=text)
        self.final_content=content
        return content


def validate_optional_text(document):
    llm=document['llm']
    if 'runtime' not in llm:return  # Earlier evidence remains governed by its original contract.
    if (llm['prompt_revision']!='text-v3-prompt-v2' or llm['prompt_sha256']!=PROMPT_SHA256
        or llm['runtime']!=dict(model=RUNTIME.model,temperature=0,think='low',max_tokens=1536,timeout_seconds=60)
        or llm['cloud_text_authorized'] is not True):raise ValueError('Text runtime mismatch')
    if llm['status']=='succeeded':
        identity=llm['provider'];text=document['asr']['result']['text']
        checked=validate_text_response_v3(llm['final_content'],text,source=identity['source'],model=identity['model'])
        if strict_json(encode_json(asdict(checked)))!=llm['result']:raise ValueError('Text result differs from final content')


class TextHistoryReader(VideoHistoryReader):
    def detail(self,database,session_id):
        detail=super().detail(database,session_id)
        try:
            for item in detail.document['documents']:validate_optional_text(item['evidence'])
        except (ValueError,KeyError,TypeError) as exc:raise HistoryError('evidence_invalid') from exc
        return detail


class TextWorkspace(VideoWorkspace):
    def __init__(self,root,*,text_provider_factory=None,**kwargs):
        super().__init__(root,**kwargs);self.reader=TextHistoryReader(self.root)
        self.text_provider_factory=text_provider_factory

    def process(self,database,patient_id,case_id,session_at,progress=lambda stage:None,*,llm_enabled=False,cloud_text_authorized=False):
        if type(llm_enabled) is not bool or type(cloud_text_authorized) is not bool:raise ValueError('Explicit boolean flags required')
        if not llm_enabled:return super().process(database,patient_id,case_id,session_at,progress)
        if not cloud_text_authorized:raise HistoryError('cloud_text_authorization_required')
        path=self.writable_path(database);session_at=utc_datetime(session_at,'session_at');progress('validating')
        corpus=strict_json(checked_path(CORPUS,self.root).read_bytes())
        matches=[c for c in corpus['clips'] if c['case_id']==case_id]
        if len(matches)!=1:raise HistoryError('corpus_unavailable')
        clip=matches[0];permission=clip.get('consent_ref') or clip.get('tts_permission_ref')
        if clip.get('human_verified') is not True or not permission:raise HistoryError('permission_required')
        source=checked_path(clip['actual_audio_path'],self.root)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=clip['audio_sha256']:raise HistoryError('audio_changed')
        with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2)) as connection:
            connection.execute('PRAGMA foreign_keys=ON');patients=SQLitePatientRepository(connection)
            if patients.get_by_id(patient_id) is None:raise HistoryError('invalid_patient')
            progress('loading_model');transcriber,asr_identity=self._transcriber()
            # Provider construction does not make a network request; generate is bounded and called once.
            mock=self.text_provider_factory is not None
            provider=self.text_provider_factory() if mock else OllamaTextProviderV3(config=RUNTIME,allow_requests=True)
            bridge=PromptV2Bridge(provider)
            identity=ProviderIdentity('ollama','gpt-oss:120b-cloud','text-v3-prompt-v2','mock' if mock else 'ollama_cloud',mock)
            request=AudioProcessingRequest(run_id=uuid4(),session_id=uuid4(),patient_id=patient_id,
                session_timestamp=session_at,processing_timestamp=datetime.now(timezone.utc),audio_ref=clip['actual_audio_path'],
                expected_sha256=clip['audio_sha256'],origin_ref=CORPUS,permission_ref=permission,
                origin_kind=clip['origin_reported'],permission_declared=True,llm_enabled=True,cloud_text_authorized=True)
            processor=ProcessAudio(root=self.root,patient_exists=lambda p:patients.get_by_id(p) is not None,
                transcriber=transcriber,asr_identity=asr_identity,text_provider=bridge,text_identity=identity)
            progress('processing');result=processor.execute(request)
            if result.status=='rejected':raise HistoryError('audio_rejected')
            doc=result.document;llm=doc['llm']
            llm.update(prompt_revision='text-v3-prompt-v2',prompt_sha256=PROMPT_SHA256,
                runtime=dict(model=RUNTIME.model,temperature=0,think='low',max_tokens=1536,timeout_seconds=60),
                cloud_text_authorized=True,final_content=bridge.final_content if llm['status']=='succeeded' else None)
            metadata=getattr(provider,'last_call',{})
            if isinstance(metadata,dict):
                llm['response_metadata']={k:metadata.get(k) for k in ('source','model_requested','model_returned','finish_reason','metrics','http_status','error_category')}
            raw=encode_json(doc);result=ProcessedAudio(result.status,raw,hashlib.sha256(raw).hexdigest())
            validate_optional_text(doc)
            reference=(path.parent/f'{request.run_id}.json').relative_to(self.root).as_posix()
            prepared=prepare_audio_registration(result,evidence_ref=reference)
            self.prepared[str(request.run_id)]=(str(path),prepared);progress('saving')
            try:register_audio_sqlite(prepared,connection=connection,store=AudioEvidenceStore(self.root))
            except (ValueError,OSError,sqlite3.Error):return ProcessOutcome(str(request.run_id),str(request.session_id),result.status,False)
            return ProcessOutcome(str(request.run_id),str(request.session_id),result.status,True)
