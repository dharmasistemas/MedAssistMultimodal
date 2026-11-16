"""Keep deterministic mentions when optional text provider is unavailable/invalid."""
from dataclasses import dataclass
from medassistmultimodal.domain.text_context import TermMention,detect_term_contexts
from .audio import TextAnalysis,TextAnalyzer,AudioProviderUnavailableError
from .llm import LLMProviderError


@dataclass(frozen=True, slots=True)
class ReportTextResult:
    mentions: tuple[TermMention,...]
    analysis: TextAnalysis | None
    provider_error: str | None


def analyze_report_text(text: str,analyzer: TextAnalyzer | None = None) -> ReportTextResult:
    mentions=detect_term_contexts(text)
    if analyzer is None:return ReportTextResult(mentions,None,'provider_not_configured')
    try:return ReportTextResult(mentions,analyzer.analyze(text,language='pt-BR'),None)
    except (AudioProviderUnavailableError,LLMProviderError) as exc:
        return ReportTextResult(mentions,None,type(exc).__name__)
