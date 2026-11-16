"""Configured adapter exercises the real transport with an offline opener."""
from dataclasses import FrozenInstanceError
import io
import json
from unittest.mock import patch

import pytest

from medassistmultimodal.application.analyze_report_text import analyze_report_text
from medassistmultimodal.providers.qwen_text_configured import (
    ConfiguredQwenTextAnalyzer, QwenRuntimeConfig,
)
from medassistmultimodal.providers.qwen_text_v2 import MODEL, SYSTEM_PROMPT


def invoke(config=None, content=None):
    adapter = ConfiguredQwenTextAnalyzer(config=config)
    captured = {}
    def opener(request, timeout):
        captured.update(payload=json.loads(request.data), timeout=timeout,
                        url=request.full_url)
        data = {'sentiment': 'neutral', 'sentiment_evidence': [{'quote': 'Não senti dor.'}],
                'key_phrases': [{'quote': 'dor'}]} if content is None else content
        return io.BytesIO(json.dumps({'model': MODEL, 'message': {'content': json.dumps(data)},
                                      'done_reason': 'stop'}).encode())
    with patch.object(adapter.provider, '_opener', side_effect=opener):
        result = analyze_report_text('Não senti dor.', adapter)
    return adapter, result, captured


def test_default_cpu_settings_reach_http_request_and_evidence_validation():
    adapter, result, captured = invoke()
    assert captured['url'] == 'http://127.0.0.1:11434/api/chat'
    assert captured['timeout'] == 180
    assert captured['payload']['options'] == {
        'temperature': 0, 'num_predict': 768, 'num_ctx': 4096, 'num_gpu': 0}
    assert captured['payload']['messages'][0]['content'] == SYSTEM_PROMPT
    assert result.provider_error is None and result.analysis.evidence[-1].start == 10
    assert result.mentions[0].context == 'negated_current'
    assert adapter.runtime_config == QwenRuntimeConfig()


def test_custom_settings_and_explicit_auto_acceleration_are_request_scoped():
    config = QwenRuntimeConfig(cpu_only=False, num_ctx=8192, timeout_seconds=240)
    _, result, captured = invoke(config)
    assert result.analysis and captured['timeout'] == 240
    assert captured['payload']['options']['num_ctx'] == 8192
    assert captured['payload']['options']['num_gpu'] == -1
    assert ConfiguredQwenTextAnalyzer().runtime_config.cpu_only is True


@pytest.mark.parametrize('kwargs', [
    {'cpu_only': 0}, {'cpu_only': 'true'}, {'num_ctx': True}, {'num_ctx': 1023},
    {'num_ctx': 32769}, {'num_ctx': 4096.0}, {'timeout_seconds': True},
    {'timeout_seconds': 0}, {'timeout_seconds': 601}, {'timeout_seconds': float('inf')},
    {'timeout_seconds': float('nan')}, {'timeout_seconds': '180'},
])
def test_invalid_config_rejected_before_provider_creation(kwargs):
    with pytest.raises(ValueError): QwenRuntimeConfig(**kwargs)


@pytest.mark.parametrize('ctx,timeout', [(1024, 1), (32768, 600)])
def test_config_boundaries(ctx, timeout):
    assert QwenRuntimeConfig(num_ctx=ctx, timeout_seconds=timeout).num_ctx == ctx


def test_config_is_immutable_and_type_checked():
    with pytest.raises(FrozenInstanceError): QwenRuntimeConfig().cpu_only = False
    with pytest.raises(ValueError): ConfiguredQwenTextAnalyzer(config={})


def test_invalid_quote_still_rejected_and_rules_preserved():
    _, result, _ = invoke(content={'sentiment': 'positive',
        'sentiment_evidence': [{'quote': 'Estou bem.'}], 'key_phrases': []})
    assert result.analysis is None and result.provider_error == 'LLMProviderInvalidResponseError'
    assert result.mentions[0].context == 'negated_current'


def test_timeout_preserves_mentions_without_retry_or_gpu_fallback():
    adapter = ConfiguredQwenTextAnalyzer()
    with patch.object(adapter.provider, '_opener', side_effect=TimeoutError()) as call:
        result = analyze_report_text('Não senti dor.', adapter)
    assert call.call_count == 1 and result.analysis is None
    assert result.provider_error == 'AudioProviderUnavailableError'
    assert result.mentions[0].context == 'negated_current'


def test_endpoint_and_language_guards_inherited():
    adapter = ConfiguredQwenTextAnalyzer()
    with patch.object(adapter.provider, '_opener') as call:
        with pytest.raises(ValueError): adapter.analyze('dor', language='en')
        adapter.provider.base_url = 'https://ollama.com'
        with pytest.raises(ValueError): adapter.analyze('dor')
    call.assert_not_called()
