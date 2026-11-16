import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from medassistmultimodal.application.llm import LLMProviderUnavailableError
from medassistmultimodal.domain.text_analysis_v3 import TERM_PATTERN
from medassistmultimodal.providers.ollama_text_v3 import TextRuntimeV3

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('evaluate_v3',ROOT/'scripts/evaluate_text_v3.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def copy_frozen_plan(tmp_path):
    plan=runner.build_plan(ROOT,TextRuntimeV3())
    for name in plan['frozen_hashes']:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    return plan


class OfflineProvider:
    def __init__(self,**kwargs):self.last_call={}
    def generate(self,*,system_prompt,text):
        sentences=[m.group().strip() for m in re.finditer(r'[^.!?]+[.!?]?',text)]
        terms=[]
        for m in TERM_PATTERN.finditer(text):
            quote=next(s for s in sentences if text.find(s)<=m.start()<text.find(s)+len(s))
            terms.append(dict(term=m.group().lower(),quote=quote))
        self.last_call=dict(http_status=200,seconds=0,metrics=None,source='mock_offline_test')
        return json.dumps(dict(sentiment='neutral',sentiment_evidence=[dict(quote=sentences[0])],terms=terms))


def metadata_for(plan):
    return lambda path:({'models':[dict(name=plan['model'],digest=plan['expected_model_manifest_digest'])]}
                        if path=='/api/tags' else {'version':'offline-fixture'})


def test_plan_preparation_no_network_and_exact_ten_approved_entries():
    plan=runner.build_plan(ROOT,TextRuntimeV3());runner.verify_plan(plan,ROOT)
    assert len(plan['order'])==10 and plan['requests_executed_during_preparation']==0
    assert plan['corpus_known'] and not plan['independent_validation']
    assert plan['source']=='ollama_cloud' and plan['model']=='gpt-oss:120b-cloud'


def test_cloud_guard_before_metadata_or_output(tmp_path):
    plan=copy_frozen_plan(tmp_path);metadata=Mock()
    with pytest.raises(ValueError):runner.execute_plan(plan,tmp_path,read_metadata=metadata)
    metadata.assert_not_called();assert not (tmp_path/plan['output']).exists()


def test_offline_execute_loop_and_occurrence_metrics(tmp_path):
    plan=copy_frozen_plan(tmp_path)
    summary=runner.execute_plan(plan,tmp_path,allow_cloud=True,
                                provider_factory=OfflineProvider,read_metadata=metadata_for(plan))
    assert summary['attempts']==10 and summary['not_attempted']==0
    assert all(g['valid']==5 and g['term_occurrences']['tp']==10 for g in summary['groups'].values())
    assert all(g['term_occurrences']['f1']==1 for g in summary['groups'].values())
    assert len(list((tmp_path/plan['output']).glob('A*.json')))==10
    assert summary['provider_totals']['usage']['eval_count']['total_available'] is None
    assert summary['provider_totals']['usage']['eval_count']['calls_with_metric']==0


def test_changed_plan_or_source_blocks_execution(tmp_path):
    plan=copy_frozen_plan(tmp_path)
    plan['runtime']['max_tokens']=2048
    with pytest.raises(ValueError):runner.verify_plan(plan,tmp_path)
    plan=runner.build_plan(ROOT,TextRuntimeV3())
    (tmp_path/runner.REFERENCES).write_text('{}')
    with pytest.raises(ValueError):runner.verify_plan(plan,tmp_path)


def test_plan_limit_stops_without_retry(tmp_path):
    plan=copy_frozen_plan(tmp_path)
    class Limited:
        def __init__(self,**kwargs):self.last_call={}
        def generate(self,**kwargs):
            self.last_call=dict(http_status=429)
            raise LLMProviderUnavailableError('offline limit')
    summary=runner.execute_plan(plan,tmp_path,allow_cloud=True,
        provider_factory=Limited,read_metadata=metadata_for(plan))
    assert summary['attempts']==1 and summary['not_attempted']==9


def test_missing_model_never_creates_run_or_calls_provider(tmp_path):
    plan=copy_frozen_plan(tmp_path);factory=Mock()
    with pytest.raises(ValueError):runner.execute_plan(plan,tmp_path,allow_cloud=True,
        provider_factory=factory,read_metadata=lambda path:{'models':[]})
    factory.assert_not_called();assert not (tmp_path/plan['output']).exists()


def test_explicit_cli_backend_cannot_be_ignored(tmp_path,monkeypatch):
    plan=copy_frozen_plan(tmp_path);path=tmp_path/'configs/day16_text_evaluation_v3.json'
    path.parent.mkdir(parents=True);path.write_text(json.dumps(plan))
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    with pytest.raises(ValueError,match='backend differs'):
        runner.main(['--execute','--allow-cloud','--backend','qwen_cpu'])


@pytest.mark.parametrize('content,category',[
    ('{}','schema'),
    (json.dumps(dict(sentiment='neutral',sentiment_evidence=[dict(quote='dor inexistente')],terms=[])),'evidence'),
])
def test_schema_and_literal_errors_have_distinct_telemetry(content,category):
    result=SimpleNamespace(provider_error='InvalidTextResponse')
    telemetry=runner.validation_telemetry(result,dict(content=content),'Não senti dor.',TextRuntimeV3())
    assert telemetry['error_category']==category
