import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from medassistmultimodal.application.register_vitals import strict_json,encode_json
from medassistmultimodal.application.llm import LLMProviderError,LLMProviderTimeoutError

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('sentiment_contrast_runner',ROOT/'scripts/evaluate_sentiment_contrast.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


@pytest.fixture
def planned(tmp_path):
    refs=strict_json((ROOT/runner.REFERENCES).read_bytes())
    names=(*runner.CODE_PATHS,runner.REFERENCES,runner.APPROVAL,runner.MODEL_RECORD,
        *(r['input_file'] for r in refs['cases'].values()))
    for name in names:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    (tmp_path/'configs').mkdir()
    return tmp_path,runner.build_plan(tmp_path),refs


def fixture_metadata(plan):
    return lambda path:dict(models=[dict(name=plan['model'],digest=plan['expected_model_manifest_digest'])]) if path=='/api/tags' else {'version':'offline-fixture'}


def provider_factory(refs,mode='valid'):
    by_text={v['input_text']:v for v in refs['cases'].values()}
    class Provider:
        def __init__(self,**kwargs):self.last_call={};self.calls=0
        def generate(self,*,system_prompt,text):
            self.calls+=1;self.last_call=dict(seconds=.1,http_status=None,metrics=dict(prompt_eval_count=10,eval_count=5))
            if mode=='blocked':
                self.last_call['http_status']=401;raise LLMProviderError('Unit fixture')
            if mode=='timeout':raise LLMProviderTimeoutError('Unit fixture')
            if mode=='invalid':return '{invalid'
            if mode=='unknown':return json.dumps(dict(sentiment='unknown',sentiment_evidence=[],terms=[]))
            r=by_text[text]
            return json.dumps(dict(sentiment=r['sentiment'],
                sentiment_evidence=[dict(quote=q['quote']) for q in r['sentiment_evidence_reference']],
                terms=[dict(term=t['term'],quote=text[max(0,t['term_start']-16):min(len(text),t['term_end']+16)]) for t in r['terms']]))
    return Provider


def test_prepare_is_offline_and_plan_hashes_are_reproducible(planned,monkeypatch):
    root,plan,_=planned
    monkeypatch.setattr(runner,'metadata',Mock(side_effect=AssertionError('Network forbidden')))
    monkeypatch.setattr(runner,'ROOT',root)
    runner.main([])
    saved=strict_json((root/runner.PLAN).read_bytes())
    assert saved==plan and saved['attempts_planned']==6
    assert saved['class_counts']==dict(positive=2,negative=2,mixed=1,neutral=1)
    assert saved['preparation_model_requests']==0
    assert saved['runtime']==dict(backend='gpt_oss_cloud',max_tokens=1536,timeout_seconds=180.)
    runner.verify_plan(plan,root);runner.metadata.assert_not_called()


def test_cloud_requires_explicit_opt_in_before_metadata_or_factory(planned):
    root,plan,_=planned;metadata=Mock();factory=Mock()
    with pytest.raises(ValueError,match='Explicit'):runner.execute_plan(plan,root,read_metadata=metadata,provider_factory=factory)
    metadata.assert_not_called();factory.assert_not_called()
    assert not (root/runner.OUTPUT).exists()


@pytest.mark.parametrize('change',['input','reference','code','plan'])
def test_mutation_blocks_before_any_provider(planned,change):
    root,plan,refs=planned
    if change=='plan':plan['runtime']['max_tokens']=2048
    else:
        name=refs['cases']['S01']['input_file'] if change=='input' else runner.REFERENCES if change=='reference' else runner.CODE_PATHS[0]
        with (root/name).open('ab') as f:f.write(b' ')
    read=Mock();factory=Mock()
    with pytest.raises(ValueError):runner.execute_plan(plan,root,allow_cloud=True,read_metadata=read,provider_factory=factory)
    read.assert_not_called();factory.assert_not_called()


def test_changed_model_stops_without_output_or_fallback(planned):
    root,plan,_=planned;factory=Mock()
    with pytest.raises(ValueError,match='manifest'):
        runner.execute_plan(plan,root,allow_cloud=True,provider_factory=factory,
            read_metadata=lambda path:{'models':[{'name':plan['model'],'digest':'0'*64}]})
    factory.assert_not_called();assert not (root/runner.OUTPUT).exists()


def test_mock_execution_confusion_counts_usage_and_exclusive_output(planned):
    root,plan,refs=planned
    s=runner.execute_plan(plan,root,allow_cloud=True,provider_factory=provider_factory(refs),read_metadata=fixture_metadata(plan))
    assert s['valid']==6 and s['correct']==6 and s['accuracy_all_attempts']==1
    assert s['term_occurrences']['tp']==7 and s['term_occurrences']['fn']==0
    assert s['per_class']['unknown']['attempts']==0
    assert s['semantic_evidence_review']=='pending_human_review'
    assert s['provider_injected'] is True and s['cloud_used'] is False
    assert s['usage']['prompt_eval_count']['total_available']==60
    read=Mock()
    with pytest.raises(ValueError,match='already exists'):runner.execute_plan(plan,root,allow_cloud=True,read_metadata=read)
    read.assert_not_called()


@pytest.mark.parametrize('mode',['invalid','timeout','unknown','blocked'])
def test_failure_unknown_and_access_limit_are_distinct(planned,mode):
    root,plan,refs=planned
    s=runner.execute_plan(plan,root,allow_cloud=True,provider_factory=provider_factory(refs,mode),read_metadata=fixture_metadata(plan))
    assert s['attempts']==(1 if mode=='blocked' else 6)
    assert s['not_attempted']==(5 if mode=='blocked' else 0)
    assert s['valid']==(6 if mode=='unknown' else 0)
    assert s['correct']==0
    column='unknown' if mode=='unknown' else 'provider_failure'
    assert sum(row[column] for row in s['confusion'].values())==s['attempts']
    if mode=='blocked':assert not (root/runner.OUTPUT/'S02.json').exists()


def test_empty_metrics_do_not_become_false_perfect_accuracy():
    s=runner.aggregate([])
    assert s['accuracy_valid'] is None and s['accuracy_all_attempts'] is None
    assert s['term_occurrences']['precision'] is None and s['seconds'] is None
