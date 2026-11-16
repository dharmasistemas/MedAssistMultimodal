"""Validação LOCAL de contingência Azure; não contém clientes ou chamadas HTTP."""
from __future__ import annotations
import argparse
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from medassistmultimodal.infrastructure.config import ConfigurationError, load_env_file


def _flag(values: Mapping[str, str], name: str) -> bool:
    value = values.get(name, "0").strip()
    if value not in {"0", "1"}:
        raise ConfigurationError(f"{name} deve ser 0 ou 1")
    return value == "1"


@dataclass(frozen=True, slots=True)
class AzureF0Settings:
    mode: str = "mock"
    subscription_confirmed: bool = False
    speech_f0_confirmed: bool = False
    language_f0_confirmed: bool = False
    run_integration: bool = False
    speech_tier: str = "F0"
    language_tier: str = "F0"
    speech_region: str = ""
    speech_key: str = field(default="", repr=False)
    language_endpoint: str = field(default="", repr=False)
    language_key: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if self.mode not in {"mock", "azure"}:
            raise ConfigurationError("AUDIO_PROVIDER deve ser mock ou azure")
        if self.speech_tier != "F0" or self.language_tier != "F0":
            raise ConfigurationError("Contingência aceita somente F0; nenhum fallback pago")
        if self.speech_region and not re.fullmatch(r"[a-z][a-z0-9]{1,63}", self.speech_region):
            raise ConfigurationError("AZURE_SPEECH_REGION inválida")
        if self.language_endpoint:
            try:
                parsed = urlsplit(self.language_endpoint)
                host = parsed.hostname or ""
                valid = (parsed.scheme == "https" and not parsed.username and not parsed.password
                         and not parsed.query and not parsed.fragment and parsed.path in {"", "/"}
                         and parsed.port in {None, 443}
                         and host.endswith((".cognitiveservices.azure.com", ".api.cognitive.microsoft.com")))
            except ValueError:
                valid = False
            if not valid:
                raise ConfigurationError("AZURE_LANGUAGE_ENDPOINT deve ser endpoint HTTPS público Azure sem parâmetros")

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> AzureF0Settings:
        values = os.environ if values is None else values
        return cls(
            mode=values.get("AUDIO_PROVIDER", "mock").strip(),
            subscription_confirmed=_flag(values, "AZURE_SUBSCRIPTION_CONFIRMED"),
            speech_f0_confirmed=_flag(values, "AZURE_SPEECH_F0_CONFIRMED"),
            language_f0_confirmed=_flag(values, "AZURE_LANGUAGE_F0_CONFIRMED"),
            run_integration=_flag(values, "RUN_AZURE_INTEGRATION"),
            speech_tier=values.get("AZURE_SPEECH_TIER", "F0").strip(),
            language_tier=values.get("AZURE_LANGUAGE_TIER", "F0").strip(),
            speech_region=values.get("AZURE_SPEECH_REGION", "").strip(),
            speech_key=values.get("AZURE_SPEECH_KEY", "").strip(),
            language_endpoint=values.get("AZURE_LANGUAGE_ENDPOINT", "").strip(),
            language_key=values.get("AZURE_LANGUAGE_KEY", "").strip(),
        )

    def configuration_blockers(self) -> tuple[str, ...]:
        required = {
            "AZURE_SUBSCRIPTION_CONFIRMED": self.subscription_confirmed,
            "AZURE_SPEECH_F0_CONFIRMED": self.speech_f0_confirmed,
            "AZURE_LANGUAGE_F0_CONFIRMED": self.language_f0_confirmed,
            "AZURE_SPEECH_REGION": bool(self.speech_region),
            "AZURE_SPEECH_KEY": bool(self.speech_key),
            "AZURE_LANGUAGE_ENDPOINT": bool(self.language_endpoint),
            "AZURE_LANGUAGE_KEY": bool(self.language_key),
        }
        return tuple(name for name, present in required.items() if not present)

    def diagnostic(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "local_configuration_complete": not self.configuration_blockers(),
            "missing_configuration": self.configuration_blockers(),
            "integration_opt_in": self.run_integration,
            "real_adapter_implemented": False,
            "cloud_sku_verified": False,
            "network_calls_performed": False,
            "note": "Validação local; declarações F0 não verificam assinatura, recurso ou cobrança no Azure.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Confere configuração local Azure sem rede")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--require-configured", action="store_true")
    args = parser.parse_args()
    try:
        load_env_file(args.env_file)
        settings = AzureF0Settings.from_env()
    except ConfigurationError as error:
        print(json.dumps({"configuration_error": str(error), "network_calls_performed": False}, ensure_ascii=False))
        return 2
    print(json.dumps(settings.diagnostic(), ensure_ascii=False, indent=2))
    return 2 if args.require_configured and settings.configuration_blockers() else 0


if __name__ == "__main__":
    raise SystemExit(main())
