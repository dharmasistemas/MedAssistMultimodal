"""Contratos substituíveis de fala/texto, sem dependência de SDK de nuvem."""
from dataclasses import dataclass
import math
from typing import Literal, Protocol


class AudioProviderUnavailableError(RuntimeError):
    """Provider indisponível ou fixture offline não configurada."""


class AudioNoSpeechError(RuntimeError):
    """Nenhum texto de fala produzido; não equivale a transcrição correta vazia."""


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str

    def __post_init__(self):
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
               for v in (self.start_seconds,self.end_seconds)):
            raise ValueError('Segmento exige tempos finitos')
        if not 0 <= self.start_seconds < self.end_seconds:
            raise ValueError('Intervalo de segmento inválido')
        if not isinstance(self.text,str) or not self.text.strip():
            raise ValueError('Segmento exige texto')


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str
    source: Literal["mock", "azure", "whisper"]
    evidence_ref: str
    segments: tuple[TranscriptSegment, ...] = ()

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.text, self.language, self.evidence_ref)):
            raise ValueError("Transcrição exige texto, idioma e referência de evidência")
        if self.source not in {"mock", "azure", "whisper"}:
            raise ValueError("Origem de transcrição inválida")
        if not isinstance(self.segments,tuple) or any(not isinstance(s,TranscriptSegment) for s in self.segments):
            raise ValueError('Segmentos devem ser tupla tipada')
        if any(b.start_seconds < a.end_seconds for a,b in zip(self.segments,self.segments[1:])):
            raise ValueError('Segmentos sobrepostos ou fora de ordem')


@dataclass(frozen=True, slots=True)
class TextEvidence:
    kind: Literal['sentiment','key_phrase']
    start: int
    end: int
    quote: str

    def __post_init__(self):
        if self.kind not in ('sentiment','key_phrase') or type(self.start) is not int or type(self.end) is not int:
            raise ValueError('Invalid text evidence')
        if not 0<=self.start<self.end or not isinstance(self.quote,str) or not self.quote.strip():
            raise ValueError('Invalid evidence interval/text')


@dataclass(frozen=True, slots=True)
class TextAnalysis:
    sentiment: Literal["positive", "neutral", "negative", "mixed", "unknown"]
    key_phrases: tuple[str, ...]
    source: Literal["mock", "azure", "ollama_qwen"] = "mock"
    evidence: tuple[TextEvidence, ...] = ()
    model: str | None = None
    input_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.sentiment not in {"positive", "neutral", "negative", "mixed", "unknown"}:
            raise ValueError("Rótulo de sentimento inválido")
        if self.source not in {"mock", "azure", "ollama_qwen"}:
            raise ValueError("Origem de análise inválida")
        if not isinstance(self.evidence,tuple) or any(not isinstance(e,TextEvidence) for e in self.evidence):
            raise ValueError('Invalid evidence collection')
        if any(not phrase.strip() for phrase in self.key_phrases):
            raise ValueError("Expressão-chave vazia")


class SpeechTranscriber(Protocol):
    def transcribe(self, audio_ref: str, *, language: str = "pt-BR") -> Transcript: ...


class TextAnalyzer(Protocol):
    def analyze(self, text: str, *, language: str = "pt-BR") -> TextAnalysis: ...
