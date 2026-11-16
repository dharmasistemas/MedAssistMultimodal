"""Contratos offline com respostas explícitas, sem leitura de mídia ou nuvem."""
import unittest
from medassistmultimodal.application.audio import (
    AudioProviderUnavailableError, SpeechTranscriber, TextAnalyzer, TextAnalysis, Transcript,
)
from medassistmultimodal.providers.mock_audio import MockSpeechTranscriber, MockTextAnalyzer


class MockAudioTests(unittest.TestCase):
    def test_transcript_is_deterministic_and_declares_mock_origin(self):
        transcriber: SpeechTranscriber = MockSpeechTranscriber({"fixture-1": "Sessão sintética concluída."})
        first = transcriber.transcribe("fixture-1")
        self.assertEqual(first, transcriber.transcribe("fixture-1"))
        self.assertEqual(first.source, "mock")
        self.assertEqual(first.evidence_ref, "fixture-1")
        self.assertEqual(first.language, "pt-BR")

    def test_missing_provider_fixture_has_controlled_failure(self):
        with self.assertRaises(AudioProviderUnavailableError):
            MockSpeechTranscriber({}).transcribe("missing")
        with self.assertRaises(AudioProviderUnavailableError):
            MockTextAnalyzer({}).analyze("missing")

    def test_empty_reference_text_or_language_is_rejected(self):
        with self.assertRaises(ValueError):
            MockSpeechTranscriber({}).transcribe(" ")
        with self.assertRaises(ValueError):
            MockSpeechTranscriber({}).transcribe("fixture", language=" ")
        with self.assertRaises(ValueError):
            MockTextAnalyzer({}).analyze(" ")

    def test_analysis_is_fixture_not_inferred_sentiment_or_clinical_alert(self):
        expected = TextAnalysis("neutral", ("sessão sintética",))
        analyzer: TextAnalyzer = MockTextAnalyzer({"Sessão sintética.": expected})
        self.assertEqual(analyzer.analyze("Sessão sintética."), expected)
        self.assertEqual(expected.source, "mock")

    def test_invalid_model_results_and_wrong_fixture_origin_are_rejected(self):
        with self.assertRaises(ValueError):
            TextAnalysis("diagnosis", ())
        with self.assertRaises(ValueError):
            TextAnalysis("neutral", (" ",))
        with self.assertRaises(ValueError):
            Transcript(" ", "pt-BR", "mock", "fixture")
        with self.assertRaises(ValueError):
            MockTextAnalyzer({"text": TextAnalysis("neutral", (), "azure")})
