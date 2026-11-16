"""Configuração de contingência não autentica, não faz rede e não expõe chaves."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from medassistmultimodal.infrastructure.azure_f0_config import AzureF0Settings
from medassistmultimodal.infrastructure.config import ConfigurationError


class AzureF0ConfigurationTests(unittest.TestCase):
    def configured(self):
        return {
            "AUDIO_PROVIDER": "azure", "AZURE_SUBSCRIPTION_CONFIRMED": "1",
            "AZURE_SPEECH_F0_CONFIRMED": "1", "AZURE_LANGUAGE_F0_CONFIRMED": "1",
            "AZURE_SPEECH_REGION": "eastus", "AZURE_SPEECH_KEY": "fixture-speech-secret",
            "AZURE_LANGUAGE_ENDPOINT": "https://fixture.cognitiveservices.azure.com/",
            "AZURE_LANGUAGE_KEY": "fixture-language-secret",
        }

    def test_empty_settings_stay_mock_with_integration_disabled(self):
        settings = AzureF0Settings.from_env({})
        self.assertEqual(settings.mode, "mock")
        self.assertFalse(settings.run_integration)
        self.assertIn("AZURE_SUBSCRIPTION_CONFIRMED", settings.configuration_blockers())
        self.assertFalse(settings.diagnostic()["real_adapter_implemented"])

    def test_complete_settings_are_only_local_declarations_and_hide_secrets(self):
        settings = AzureF0Settings.from_env(self.configured())
        self.assertEqual(settings.configuration_blockers(), ())
        self.assertFalse(settings.diagnostic()["cloud_sku_verified"])
        self.assertFalse(settings.diagnostic()["network_calls_performed"])
        output = repr(settings) + json.dumps(settings.diagnostic())
        for value in ("fixture-speech-secret", "fixture-language-secret", "fixture.cognitiveservices.azure.com"):
            self.assertNotIn(value, output)

    def test_paid_tiers_are_rejected_even_if_other_values_are_present(self):
        for name in ("AZURE_SPEECH_TIER", "AZURE_LANGUAGE_TIER"):
            values = self.configured(); values[name] = "S0"
            with self.subTest(name=name), self.assertRaises(ConfigurationError):
                AzureF0Settings.from_env(values)

    def test_endpoint_rejects_http_non_azure_userinfo_query_and_port(self):
        for endpoint in ("http://fixture.cognitiveservices.azure.com", "https://evil.example",
                         "https://secret@fixture.cognitiveservices.azure.com",
                         "https://fixture.cognitiveservices.azure.com/?key=private-value",
                         "https://fixture.cognitiveservices.azure.com:8080"):
            values = self.configured(); values["AZURE_LANGUAGE_ENDPOINT"] = endpoint
            with self.subTest(endpoint=endpoint), self.assertRaises(ConfigurationError) as caught:
                AzureF0Settings.from_env(values)
            self.assertNotIn(endpoint, str(caught.exception))

    def test_flags_reject_ambiguous_values_without_exposing_values(self):
        with self.assertRaises(ConfigurationError) as caught:
            AzureF0Settings.from_env({"RUN_AZURE_INTEGRATION": "private-value"})
        self.assertNotIn("private-value", str(caught.exception))

    def test_cli_remains_offline_and_reports_missing_configuration(self):
        from medassistmultimodal.infrastructure.azure_f0_config import main
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("AUDIO_PROVIDER=mock\n", encoding="utf-8")
            output = StringIO()
            with patch.dict("os.environ", {}, clear=True), patch("sys.argv", [
                "config", "--env-file", str(env_file), "--require-configured"
            ]), patch("urllib.request.urlopen", side_effect=AssertionError("No network")), \
                 patch("socket.create_connection", side_effect=AssertionError("No network")), redirect_stdout(output):
                result = main()
            self.assertEqual(result, 2)
            self.assertFalse(json.loads(output.getvalue())["network_calls_performed"])
