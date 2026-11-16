from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from medassistmultimodal.application.audio import (
    Transcript, TranscriptSegment, AudioNoSpeechError, AudioProviderUnavailableError,
)
from medassistmultimodal.application.process_audio import (
    ProcessAudio, AudioProcessingRequest, ProviderIdentity,
)
from medassistmultimodal.application.llm import LLMProviderTimeoutError
from medassistmultimodal.domain.audio_features import AudioFeatures
from medassistmultimodal.providers.whisper_local import WhisperRun


def fixture(tmp_path, text='Não senti dor.', **kwargs):
    audio=tmp_path/'audio.mp3';audio.write_bytes(b'offline test media')
    (tmp_path/'origin.json').write_text('{}');(tmp_path/'permission.json').write_text('{}')
    sha=hashlib.sha256(audio.read_bytes()).hexdigest()
    request=AudioProcessingRequest(run_id=uuid4(),session_id=uuid4(),patient_id='PAT-001',
        session_timestamp=datetime(2026,11,7,tzinfo=timezone.utc),
        processing_timestamp=datetime(2026,11,7,12,tzinfo=timezone.utc),
        audio_ref='audio.mp3',expected_sha256=sha,origin_ref='origin.json',
        permission_ref='permission.json',origin_kind='synthetic_tts',permission_declared=True)
    transcript=Transcript(text,'pt-BR','mock',f'audio.mp3#sha256={sha}',(TranscriptSegment(0,1,text),))
    features=AudioFeatures('energy-descriptors-v1',16000,16000,1,.1,.2,.02,.01,.2,())
    run=WhisperRun(transcript,features,sha,.2)
    transcriber=Mock();transcriber.transcribe_with_details.return_value=run
    processor=ProcessAudio(root=tmp_path,patient_exists=lambda p:p=='PAT-001',
        transcriber=transcriber,asr_identity=ProviderIdentity('fixture','offline','1','mock',True),**kwargs)
    return processor,request,transcriber,run


def llm_identity(source='mock'):
    return ProviderIdentity('fixture' if source=='mock' else 'ollama','model','1',source,source=='mock')


@pytest.mark.parametrize('text,contexts,classifications',[
    ('Completei a sessão.',[],[]),
    ('Não senti dor.',['negated_current'],['context_information']),
    ('Senti tontura.',['affirmed_current'],['candidate_for_human_review']),
    ('Se sentir falta de ar, aviso. Não tive falta de ar.',
     ['conditional','negated_current'],['context_information','context_information']),
    ('Meu irmão sentiu dor no peito.',['third_party'],['context_information']),
    ('Ontem senti tontura. Hoje não senti tontura.',
     ['affirmed_historical','negated_current'],['context_information','context_information']),
    ('Talvez eu tenha sentido dor.',['unknown'],['context_uncertain']),
    ('No começo senti dor.',['affirmed_earlier_in_session'],['context_information']),
])
def test_context_classification_and_tts_not_conflated_with_mock(tmp_path,text,contexts,classifications):
    p,r,t,run=fixture(tmp_path,text)
    result=p.execute(r);doc=result.document
    assert result.status=='completed'
    assert [i['context'] for i in doc['rules']['items']]==contexts
    assert [i['classification'] for i in doc['rules']['items']]==classifications
    assert doc['input']['origin_kind']=='synthetic_tts' and doc['identity']['source_kind']=='simulated'
    assert doc['asr']['provider']['is_mock'] is True and doc['rules']['is_mock'] is False
    assert doc['llm']['status']=='disabled' and doc['llm']['provider'] is None
    assert all(i['review_status']=='pending_review' and i['confidence'] is None for i in doc['rules']['items'])
    assert 'severity' not in result.evidence.decode() and not doc['summary']['clinical_validation']


@pytest.mark.parametrize('changes',[
    {'patient_id':'PAT-999'}, {'patient_id':'real name'}, {'run_id':uuid4().hex},
    {'permission_declared':False}, {'permission_ref':'missing.json'},
    {'origin_ref':'missing.json'}, {'expected_sha256':'0'*64}, {'expected_sha256':'bad'},
    {'audio_ref':'missing.mp3'}, {'audio_ref':'../audio.mp3'},
    {'session_timestamp':datetime(2026,11,7)}, {'llm_enabled':1},
])
def test_invalid_input_rejected_before_provider(tmp_path,changes):
    p,r,t,run=fixture(tmp_path)
    result=p.execute(replace(r,**changes))
    assert result.status=='rejected' and result.document['rules']['items'] is None
    t.transcribe_with_details.assert_not_called()


@pytest.mark.parametrize('error,status',[
    (AudioNoSpeechError('no speech'),'no_speech'),
    (AudioProviderUnavailableError('private path SECRET'),'unavailable'),
    (RuntimeError('SECRET'),'unavailable'), (ValueError('bad output'),'invalid_output'),
])
def test_asr_failure_has_no_downstream_text(tmp_path,error,status):
    provider=Mock();p,r,t,run=fixture(tmp_path,text_provider=provider,text_identity=llm_identity())
    t.transcribe_with_details.side_effect=error
    result=p.execute(replace(r,llm_enabled=True));doc=result.document
    assert result.status=='failed' and doc['asr']['status']==status
    assert doc['asr']['result'] is None and doc['rules']['status']=='not_run'
    assert doc['llm']['status']=='not_run' and b'SECRET' not in result.evidence
    provider.generate.assert_not_called()


@pytest.mark.parametrize('fault',['object','hash','source','evidence_ref','time','segments'])
def test_invalid_asr_output_is_not_success(tmp_path,fault):
    p,r,t,run=fixture(tmp_path)
    if fault=='object':run=object()
    elif fault=='hash':run=replace(run,source_sha256='0'*64)
    elif fault=='source':run=replace(run,transcript=replace(run.transcript,source='whisper'))
    elif fault=='evidence_ref':run=replace(run,transcript=replace(run.transcript,evidence_ref='other'))
    elif fault=='time':run=replace(run,processing_seconds=float('nan'))
    elif fault=='segments':run=replace(run,transcript=replace(run.transcript,segments=(TranscriptSegment(0,3,'fala'),)))
    t.transcribe_with_details.return_value=run
    doc=p.execute(r).document
    assert doc['summary']['status']=='failed' and doc['asr']['status']=='invalid_output'


@pytest.mark.parametrize('mode',['timeout','unavailable','invalid','not_configured','unknown','positive'])
def test_llm_never_changes_rule_candidates(tmp_path,mode):
    provider=Mock();p,r,t,run=fixture(tmp_path,'Senti tontura.',text_provider=provider,text_identity=llm_identity())
    before=p.execute(r).document['rules']
    if mode=='timeout':provider.generate.side_effect=LLMProviderTimeoutError('SECRET')
    elif mode=='unavailable':provider.generate.side_effect=AudioProviderUnavailableError('SECRET')
    elif mode=='invalid':provider.generate.return_value='```json\n{}\n```'
    elif mode=='not_configured':p.text_provider=None
    else:provider.generate.return_value=json.dumps(dict(sentiment=mode,
        sentiment_evidence=[] if mode=='unknown' else [{'quote':'Senti tontura.'}],terms=[]))
    result=p.execute(replace(r,llm_enabled=True));doc=result.document
    assert doc['rules']==before and b'SECRET' not in result.evidence
    assert doc['llm']['status']==('succeeded' if mode in ('unknown','positive') else
        {'timeout':'timeout','unavailable':'unavailable','invalid':'invalid_response','not_configured':'not_configured'}[mode])
    assert result.status==('completed' if mode in ('unknown','positive') else 'degraded')
    assert provider.generate.call_count<=1


def test_cloud_requires_explicit_text_authorization(tmp_path):
    provider=Mock();p,r,t,run=fixture(tmp_path,text_provider=provider,text_identity=llm_identity('ollama_cloud'))
    doc=p.execute(replace(r,llm_enabled=True)).document
    assert doc['llm']['status']=='not_configured' and doc['summary']['status']=='degraded'
    provider.generate.assert_not_called()


@pytest.mark.parametrize('source',['mock','ollama_local','ollama_cloud'])
def test_valid_llm_provenance_and_abstention(tmp_path,source):
    provider=Mock();provider.generate.return_value=json.dumps(
        dict(sentiment='unknown',sentiment_evidence=[],terms=[]))
    p,r,t,run=fixture(tmp_path,text_provider=provider,text_identity=llm_identity(source))
    result=p.execute(replace(r,llm_enabled=True,cloud_text_authorized=source=='ollama_cloud'))
    doc=result.document
    assert result.status=='completed' and doc['llm']['status']=='succeeded'
    assert doc['llm']['result']['source']==source and doc['llm']['result']['sentiment']=='unknown'
    assert doc['llm']['result']['input_sha256']==doc['asr']['input_text_sha256']
    provider.generate.assert_called_once()


def test_missing_asr_provider_is_unavailable(tmp_path):
    p,r,t,run=fixture(tmp_path);p.transcriber=None
    doc=p.execute(r).document
    assert doc['summary']['status']=='failed' and doc['asr']['status']=='unavailable'


def test_provider_exception_with_personal_path_never_enters_evidence(tmp_path):
    provider=Mock(side_effect=None);provider.generate.side_effect=RuntimeError('C:/personal/SECRET')
    p,r,t,run=fixture(tmp_path,text_provider=provider,text_identity=llm_identity())
    result=p.execute(replace(r,llm_enabled=True))
    assert result.status=='degraded' and b'SECRET' not in result.evidence
    assert result.document['llm']['status']=='unavailable'


@pytest.mark.parametrize('text,rule_status',[('a'*4001,'unsupported_input'),(' '.join(['dor']*9),'succeeded_with_mentions')])
def test_capacity_limits_do_not_remove_available_rules(tmp_path,text,rule_status):
    provider=Mock();p,r,t,run=fixture(tmp_path,text,text_provider=provider,text_identity=llm_identity())
    result=p.execute(replace(r,llm_enabled=True));doc=result.document
    assert result.status=='degraded' and doc['rules']['status']==rule_status
    assert doc['asr']['result']['text']==text and doc['llm']['status']=='unsupported_input'
    provider.generate.assert_not_called()
    if len(text)<4000:assert len(doc['rules']['items'])==9


@pytest.mark.parametrize('stage',['asr','llm'])
def test_source_mutation_rejects_evidence(tmp_path,stage):
    provider=Mock();p,r,t,run=fixture(tmp_path,text_provider=provider,text_identity=llm_identity())
    def mutate_asr(*args,**kwargs):
        (tmp_path/'audio.mp3').write_bytes(b'changed');return run
    def mutate_llm(**kwargs):
        (tmp_path/'audio.mp3').write_bytes(b'changed')
        return json.dumps(dict(sentiment='unknown',sentiment_evidence=[],terms=[]))
    if stage=='asr':t.transcribe_with_details.side_effect=mutate_asr
    else:provider.generate.side_effect=mutate_llm
    result=p.execute(replace(r,llm_enabled=True))
    assert result.status=='rejected' and result.document['input']['error']=='source_changed_during_processing'


def test_acoustic_failure_preserves_transcript_and_rules(tmp_path):
    p,r,t,run=fixture(tmp_path)
    t.transcribe_with_details.return_value=replace(run,features=replace(run.features,rms_normalized=float('nan')))
    doc=p.execute(r).document
    assert doc['summary']['status']=='degraded' and doc['acoustics']['status']=='unavailable'
    assert doc['asr']['result']['text']=='Não senti dor.' and len(doc['rules']['items'])==1


def test_rules_failure_not_empty_success(tmp_path):
    p,r,t,run=fixture(tmp_path,rule_detector=Mock(side_effect=RuntimeError('SECRET')))
    doc=p.execute(r).document
    assert doc['summary']['status']=='degraded' and doc['rules']['status']=='unavailable'
    assert doc['rules']['items'] is None and doc['summary']['counts'] is None


def test_evidence_bytes_immutable_and_hash_verified(tmp_path):
    p,r,t,run=fixture(tmp_path);result=p.execute(r)
    original=result.evidence;view=result.document;view['summary']['status']='faked'
    assert result.document['summary']['status']=='completed' and result.evidence==original
    assert hashlib.sha256(original).hexdigest()==result.evidence_sha256
    assert not list(tmp_path.glob('*.sqlite*'))


@pytest.mark.parametrize('source,mock',[('mock',False),('whisper',True),('other',False)])
def test_provider_provenance_must_be_consistent(source,mock):
    with pytest.raises(ValueError):ProviderIdentity('p','m','1',source,mock)
