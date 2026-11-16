"""Versioned literal evidence validation and evaluation, independent of providers."""
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Literal

from .text_evaluation import exact_counts

VOCABULARY = ('dor no peito', 'falta de ar', 'tontura', 'dor')
SENTIMENTS = ('positive', 'neutral', 'negative', 'mixed', 'unknown')
TERM_PATTERN = re.compile(r'\b(dor no peito|falta de ar|tontura|dor)\b', re.I)


class InvalidTextResponse(ValueError):
    """Provider output violates the v3 contract; never repaired automatically."""


class TextCapacityError(ValueError):
    """Input cannot be represented within the protocol limits."""


@dataclass(frozen=True, slots=True)
class QuoteEvidenceV3:
    quote_start: int
    quote_end: int
    quote: str


@dataclass(frozen=True, slots=True)
class TermEvidenceV3:
    term: str
    term_start: int
    term_end: int
    literal_term: str
    evidence: QuoteEvidenceV3


@dataclass(frozen=True, slots=True)
class TextAnalysisV3:
    sentiment: Literal['positive', 'neutral', 'negative', 'mixed', 'unknown']
    sentiment_evidence: tuple[QuoteEvidenceV3, ...]
    terms: tuple[TermEvidenceV3, ...]
    source: Literal['mock', 'ollama_local', 'ollama_cloud']
    model: str
    input_sha256: str
    protocol_version: str = 'text-analysis-v3'


def check_input(text, language='pt-BR'):
    if language != 'pt-BR' or not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('Nonempty pt-BR input up to 4000 characters required')
    if len(list(TERM_PATTERN.finditer(text))) > 8:
        raise TextCapacityError('More than eight eligible term occurrences')


def validate_text_response_v3(content, text, *, source, model):
    check_input(text)
    if source not in ('mock', 'ollama_local', 'ollama_cloud') or not isinstance(model, str) or not model.strip():
        raise ValueError('Explicit provider source and model required')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise InvalidTextResponse('Duplicate JSON key')
            result[key] = value
        return result
    def reject(value): raise InvalidTextResponse('Nonfinite JSON value')
    def quote_evidence(item):
        if not isinstance(item, dict) or set(item) != {'quote'}:
            raise InvalidTextResponse('Invalid quote schema')
        quote = item['quote']
        if not isinstance(quote, str) or not quote.strip() or len(quote) > 300:
            raise InvalidTextResponse('Invalid quote')
        start = text.find(quote)
        if start < 0 or text.find(quote, start + 1) >= 0:
            raise InvalidTextResponse('Quote absent or ambiguous')
        return QuoteEvidenceV3(start, start + len(quote), quote)
    def bounded_list(value):
        if not isinstance(value, list) or len(value) > 8:
            raise InvalidTextResponse('Invalid evidence list')
        return value
    try:
        if not isinstance(content, str) or len(content) > 16000:
            raise InvalidTextResponse('Invalid response size/type')
        data = json.loads(content, object_pairs_hook=pairs, parse_constant=reject)
        if not isinstance(data, dict) or set(data) != {'sentiment', 'sentiment_evidence', 'terms'}:
            raise InvalidTextResponse('Invalid response schema')
        if data['sentiment'] not in SENTIMENTS:
            raise InvalidTextResponse('Invalid sentiment')
        sentiment = tuple(quote_evidence(e) for e in bounded_list(data['sentiment_evidence']))
        if len(set(sentiment)) != len(sentiment): raise InvalidTextResponse('Duplicate sentiment evidence')
        if data['sentiment'] != 'unknown' and not sentiment:
            raise InvalidTextResponse('Missing sentiment evidence')
        # Match against the full original input, preventing a clipped quote from
        # turning the 'dor' inside 'dor no peito' into a different eligible term.
        eligible = tuple(TERM_PATTERN.finditer(text))
        terms = []; seen = set()
        for item in bounded_list(data['terms']):
            if not isinstance(item, dict) or set(item) != {'term', 'quote'} or item['term'] not in VOCABULARY:
                raise InvalidTextResponse('Invalid canonical term/schema')
            evidence = quote_evidence({'quote': item['quote']})
            matches = [m for m in eligible if m.group().lower() == item['term']
                       and evidence.quote_start <= m.start() and m.end() <= evidence.quote_end]
            if len(matches) != 1: raise InvalidTextResponse('Term absent or ambiguous inside evidence')
            match = matches[0]; key = (item['term'], match.start(), match.end())
            if key in seen: raise InvalidTextResponse('Duplicate term occurrence')
            seen.add(key)
            terms.append(TermEvidenceV3(*key, match.group(), evidence))
        return TextAnalysisV3(data['sentiment'], sentiment, tuple(terms), source, model,
                              hashlib.sha256(text.encode('utf-8')).hexdigest())
    except (ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, InvalidTextResponse): raise
        raise InvalidTextResponse('Invalid v3 response') from exc


def evaluate_text_v3(analysis, reference, *, input_text, provider_error=None):
    """Draft sentiment references cannot silently become scored ground truth."""
    sha = hashlib.sha256(input_text.encode('utf-8')).hexdigest()
    if reference['input_sha256'] != sha or (analysis is not None and analysis.input_sha256 != sha):
        raise ValueError('Input/reference/analysis hash mismatch')
    expected = [(t['term'], t['term_start'], t['term_end']) for t in reference['terms']]
    for term, start, end in expected:
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(input_text):
            raise ValueError('Invalid reference interval')
        if (term, start, end) not in [(m.group().lower(), m.start(), m.end()) for m in TERM_PATTERN.finditer(input_text)]:
            raise ValueError('Reference is not an eligible literal occurrence')
    if len(set(expected)) != len(expected): raise ValueError('Duplicate reference occurrence')
    predicted = [] if analysis is None else [(t.term, t.term_start, t.term_end) for t in analysis.terms]
    reviewed = reference.get('review_status') == 'approved'
    sentiment_reviewed = reviewed and reference.get('sentiment_review_status') == 'approved'
    if sentiment_reviewed and reference.get('sentiment') not in SENTIMENTS:
        raise ValueError('Invalid approved sentiment reference')
    return dict(provider_valid=analysis is not None, provider_error=provider_error,
                reference_review_status=reference.get('review_status'),
                reference_provisional=not reviewed,
                term_occurrences=exact_counts(predicted, expected),
                unique_terms=exact_counts(set(t[0] for t in predicted), set(t[0] for t in expected)),
                sentiment_scorable=sentiment_reviewed,
                sentiment_predicted=None if analysis is None else analysis.sentiment,
                sentiment_correct=(analysis is not None and analysis.sentiment == reference['sentiment'])
                    if sentiment_reviewed else None,
                sentiment_abstained=analysis is not None and analysis.sentiment == 'unknown')
