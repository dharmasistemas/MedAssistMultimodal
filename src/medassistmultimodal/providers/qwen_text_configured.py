"""Explicit runtime settings over the frozen v2 text/evidence contract."""
from dataclasses import dataclass
import math

from .ollama import OllamaProvider
from .qwen_text_v2 import QwenTextAnalyzerV2


@dataclass(frozen=True, slots=True)
class QwenRuntimeConfig:
    """Request-scoped settings; never modifies the Ollama server environment."""

    cpu_only: bool = True
    num_ctx: int = 4096
    timeout_seconds: float = 180.0

    def __post_init__(self):
        if type(self.cpu_only) is not bool:
            raise ValueError('cpu_only must be boolean')
        if type(self.num_ctx) is not int or not 1024 <= self.num_ctx <= 32768:
            raise ValueError('num_ctx must be an integer between 1024 and 32768')
        if (isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds)
                or not 1 <= self.timeout_seconds <= 600):
            raise ValueError('timeout_seconds must be finite and between 1 and 600')


class _ConfiguredOllamaProvider(OllamaProvider):
    def __init__(self, config, *, opener):
        super().__init__(base_url='http://127.0.0.1:11434',
                         timeout_seconds=config.timeout_seconds, opener=opener)
        self._runtime_config = config

    def _build_payload(self, request):
        payload = super()._build_payload(request)
        payload['options'].update(
            num_ctx=self._runtime_config.num_ctx,
            num_gpu=0 if self._runtime_config.cpu_only else -1,
        )
        return payload


class ConfiguredQwenTextAnalyzer(QwenTextAnalyzerV2):
    """V2 validation with CPU default; accelerator auto-selection requires opt-in."""

    def __init__(self, *, config: QwenRuntimeConfig | None = None):
        selected = QwenRuntimeConfig() if config is None else config
        if not isinstance(selected, QwenRuntimeConfig):
            raise ValueError('config must be QwenRuntimeConfig')
        super().__init__()
        # Reuse v2's local-only opener, which disables proxies and redirects.
        self.provider = _ConfiguredOllamaProvider(selected, opener=self.provider._opener)

    @property
    def runtime_config(self):
        return self.provider._runtime_config
