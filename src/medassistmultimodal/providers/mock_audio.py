"""Fixtures determinísticas; não leem áudio nem simulam qualidade clínica."""
from collections.abc import Mapping
from medassistmultimodal.application.audio import (
    AudioProviderUnavailableError, Transcript, TextAnalysis,
)


class MockSpeechTranscriber:
    def __init__(self, transcripts: Mapping[str, str]) -> None:
        self._transcripts = dict(transcripts)

    def transcribe(self, audio_ref: str, *, language: str = "pt-BR") -> Transcript:
        if not audio_ref.strip() or not language.strip():
            raise ValueError("Referência e idioma são obrigatórios")
        if audio_ref not in self._transcripts:
            raise AudioProviderUnavailableError("Fixture de transcrição não configurada")
        return Transcript(self._transcripts[audio_ref], language, "mock", audio_ref)


class MockTextAnalyzer:
    def __init__(self, results: Mapping[str, TextAnalysis]) -> None:
        if any(result.source != "mock" for result in results.values()):
            raise ValueError("Fixtures devem declarar source=mock")
        self._results = dict(results)

    def analyze(self, text: str, *, language: str = "pt-BR") -> TextAnalysis:
        if not text.strip() or not language.strip():
            raise ValueError("Texto e idioma são obrigatórios")
        if text not in self._results:
            raise AudioProviderUnavailableError("Fixture de análise não configurada")
        return self._results[text]
