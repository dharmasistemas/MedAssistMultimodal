import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from medassistmultimodal.application.text_analysis_v3 import SYSTEM_PROMPT_V3 as ORIGINAL
from medassistmultimodal.application.text_analysis_v3_prompt_v2 import (
    SYSTEM_PROMPT_V3, PROMPT_EXAMPLES, analyze_text_v3,
)
from medassistmultimodal.domain.text_analysis_v3 import validate_text_response_v3
from medassistmultimodal.providers.ollama_text_v3_prompt_v2 import OllamaTextProviderV3

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('text,response', PROMPT_EXAMPLES)
def test_examples_obey_unchanged_contract(text, response):
    analysis = validate_text_response_v3(json.dumps(response), text, source='mock', model='fixture')
    assert analysis.sentiment == response['sentiment']


def test_new_prompt_sent_verbatim_without_original_prompt_substitution():
    recorded = {}
    def opener(request, timeout):
        recorded.update(json.loads(request.data))
        return io.BytesIO(json.dumps(dict(model='gpt-oss:120b', done=True, done_reason='stop',
            message=dict(content=json.dumps(PROMPT_EXAMPLES[0][1])))).encode())
    provider = OllamaTextProviderV3(allow_requests=True, opener=opener)
    result = analyze_text_v3('Não senti dor.', provider)
    assert result.analysis
    assert recorded['messages'][0]['content'] == SYSTEM_PROMPT_V3
    assert SYSTEM_PROMPT_V3 != ORIGINAL
    assert result.mentions[0].context == 'negated_current'


def test_missing_neutral_evidence_still_rejected_and_rules_preserved():
    provider = Mock()
    provider.generate.return_value = json.dumps(dict(sentiment='neutral', sentiment_evidence=[], terms=[]))
    result = analyze_text_v3('Não senti dor.', provider)
    assert result.analysis is None and result.provider_error == 'InvalidTextResponse'
    assert result.mentions[0].context == 'negated_current'


def test_requests_disabled_and_old_prompt_rejected_before_network():
    opener = Mock()
    provider = OllamaTextProviderV3(opener=opener)
    with pytest.raises(ValueError):
        provider.generate(system_prompt=SYSTEM_PROMPT_V3, text='dor')
    provider.allow_requests = True
    with pytest.raises(ValueError):
        provider.generate(system_prompt=ORIGINAL, text='dor')
    opener.assert_not_called()


def test_both_frozen_plans_verify_and_outputs_are_separate():
    modules = []
    for filename in ('evaluate_text_v3.py', 'evaluate_text_v3_prompt_v2.py'):
        spec = importlib.util.spec_from_file_location(filename[:-3], ROOT/'scripts'/filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    old, new = modules
    original = json.loads((ROOT/'configs/day16_text_evaluation_v3_final.json').read_text())
    old.verify_plan(original, ROOT)
    plan = new.build_plan(ROOT, new.TextRuntimeV3())
    new.verify_plan(plan, ROOT)
    assert plan['output'] != original['output']
    assert plan['prompt_sha256'] != original['prompt_sha256']
    assert plan['input_hashes'] == original['input_hashes']
    assert plan['runtime'] == original['runtime']
    assert plan['requests_executed_during_preparation'] == 0
