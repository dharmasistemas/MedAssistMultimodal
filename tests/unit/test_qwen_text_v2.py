"""Offline contract tests; no Ollama generation."""
import hashlib
import json
from unittest.mock import patch

import pytest

from medassistmultimodal.application.analyze_report_text import analyze_report_text
from medassistmultimodal.application.llm import (
    LLMResponse, LLMProviderInvalidResponseError, LLMProviderTimeoutError,
)
from medassistmultimodal.providers.qwen_text_v2 import QwenTextAnalyzerV2, MODEL


def output(quote='dor', sentiment='neutral'):
    return {'sentiment': sentiment, 'sentiment_evidence': [{'quote': quote}],
            'key_phrases': [{'quote': quote}]}


def run(text, data, **kwargs):
    analyzer = QwenTextAnalyzerV2()
    response = LLMResponse(json.dumps(data, ensure_ascii=False), 'ollama',
                           kwargs.get('model', MODEL), 1,
                           finish_reason=kwargs.get('finish', 'stop'))
    with patch.object(analyzer.provider, 'generate', return_value=response) as call:
        result = analyzer.analyze(text)
    return result, call.call_args.args[0]


def test_original_a03_quote_resolves_exact_positions_without_model_offsets():
    text = ('Hoje não senti dor no ombro e não tive falta de ar durante o exercício. '
            'Completei a sequência sem esses sintomas.')
    quote = 'Completei a sequência sem esses sintomas.'
    result, request = run(text, output(quote, 'positive'))
    assert [(e.start, e.end) for e in result.evidence] == [(72, 113), (72, 113)]
    assert result.sentiment == 'positive'  # Alignment never corrects semantic labels.
    assert result.input_sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert request.model == MODEL and request.temperature == 0 and request.max_tokens == 768
    assert json.loads(request.user_prompt) == {'text': text}


@pytest.mark.parametrize('text,quote,start', [
    ('dor no início', 'dor', 0), ('Sem dor', 'dor', 4),
    ('🙂 Não senti dor.', 'Não senti dor.', 2),
    ('dor antes; dor depois', 'dor depois', 11), ('x' * 300, 'x' * 300, 0),
])
def test_exact_unicode_boundaries_and_extended_unique_quote(text, quote, start):
    result, _ = run(text, output(quote))
    assert all(e.start == start and text[e.start:e.end] == quote for e in result.evidence)


@pytest.mark.parametrize('text,quote', [
    ('dor e dor', 'dor'), ('aaa', 'aa'), ('dor', 'Dor'), ('dor', 'calor'),
    ('sequência', 'sequência'), ('dor', ''), ('dor', ' '), ('dor', None),
    ('dor', 123), ('x' * 301, 'x' * 301),
])
def test_missing_ambiguous_nonliteral_or_invalid_quote_rejected(text, quote):
    with pytest.raises(LLMProviderInvalidResponseError):
        run(text, output(quote))


@pytest.mark.parametrize('fault', ['offsets', 'duplicate', 'extra', 'missing', 'list',
                                  'too_many', 'sentiment', 'length', 'model'])
def test_strict_schema_and_transport_response(fault):
    data = output(); kwargs = {}
    if fault == 'offsets': data['key_phrases'][0].update(start=0, end=3)
    elif fault == 'duplicate': data['key_phrases'] *= 2
    elif fault == 'extra': data['diagnosis'] = 'x'
    elif fault == 'missing': data['sentiment_evidence'] = []
    elif fault == 'list': data['key_phrases'] = None
    elif fault == 'too_many': data['key_phrases'] *= 9
    elif fault == 'sentiment': data['sentiment'] = []
    elif fault == 'length': kwargs['finish'] = 'length'
    elif fault == 'model': kwargs['model'] = 'other'
    with pytest.raises(LLMProviderInvalidResponseError):
        run('dor', data, **kwargs)


@pytest.mark.parametrize('raw', ['```json\n{}\n```',
    '{"sentiment":"unknown","sentiment":"neutral","sentiment_evidence":[],"key_phrases":[]}',
    '{"sentiment":NaN,"sentiment_evidence":[],"key_phrases":[]}'])
def test_invalid_json_never_accepted(raw):
    analyzer = QwenTextAnalyzerV2()
    with patch.object(analyzer.provider, 'generate', return_value=LLMResponse(raw, 'ollama', MODEL, 1)):
        with pytest.raises(LLMProviderInvalidResponseError): analyzer.analyze('dor')


def test_unknown_and_empty_lists_are_valid():
    result, _ = run('texto', {'sentiment': 'unknown', 'sentiment_evidence': [], 'key_phrases': []})
    assert result.sentiment == 'unknown' and not result.evidence


@pytest.mark.parametrize('text', ['', ' ', 'x' * 4001])
def test_invalid_input_does_not_generate(text):
    analyzer = QwenTextAnalyzerV2()
    with patch.object(analyzer.provider, 'generate') as call:
        with pytest.raises(ValueError): analyzer.analyze(text)
    call.assert_not_called()


def test_local_endpoint_and_language_guards():
    analyzer = QwenTextAnalyzerV2()
    with patch.object(analyzer.provider, 'generate') as call:
        with pytest.raises(ValueError): analyzer.analyze('dor', language='en')
        analyzer.provider.base_url = 'https://ollama.com'
        with pytest.raises(ValueError): analyzer.analyze('dor')
    call.assert_not_called()


def test_timeout_preserves_deterministic_mentions():
    analyzer = QwenTextAnalyzerV2()
    with patch.object(analyzer.provider, 'generate', side_effect=LLMProviderTimeoutError('timeout')):
        result = analyze_report_text('Não senti dor.', analyzer)
    assert result.analysis is None and result.provider_error
    assert result.mentions[0].context == 'negated_current'


def test_ambiguous_evidence_preserves_deterministic_mentions():
    analyzer = QwenTextAnalyzerV2()
    response = LLMResponse(json.dumps(output()), 'ollama', MODEL, 1)
    with patch.object(analyzer.provider, 'generate', return_value=response):
        result = analyze_report_text('Não senti dor. Depois senti dor.', analyzer)
    assert result.analysis is None and result.provider_error == 'LLMProviderInvalidResponseError'
    assert len(result.mentions) == 2
