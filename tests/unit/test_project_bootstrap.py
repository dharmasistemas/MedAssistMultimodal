"""Configuração local segura e baseline sem dependências de serviços."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ProjectBootstrapTests(unittest.TestCase):
    def test_defaults_are_offline_and_azure_is_pending(self):
        settings = dict(line.split("=", 1) for line in
                        (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
                        if line and not line.startswith("#"))
        self.assertEqual(settings["AZURE_STATUS"], "PENDENTE_FIAP")
        self.assertEqual(settings["RUN_AZURE_INTEGRATION"], "0")
        self.assertEqual(settings["LLM_ENABLED"], "0")
        self.assertEqual(settings["OLLAMA_MODEL"], "qwen2.5:7b-instruct")

    def test_baseline_runs_without_site_packages_or_services(self):
        # -S omite site-packages; apenas stdlib e o pacote fonte ficam disponíveis.
        code = ("import sys; sys.path.insert(0, " + repr(str(ROOT / "src")) + "); "
                "from medassistmultimodal.__main__ import main; main()")
        result = subprocess.run([sys.executable, "-B", "-S", "-c", code],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        status = json.loads(result.stdout)
        self.assertEqual(status["status"], "baseline_offline")
        self.assertFalse(status["llm_required"])
