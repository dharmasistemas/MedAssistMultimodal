import os
from dataclasses import dataclass
from pathlib import Path

from medassistmultimodal.application.llm import LLMProvider
from medassistmultimodal.application.resilience import RetryPolicy, RetryingLLMProvider
from medassistmultimodal.infrastructure.config import (
    ConfigurationError,
    load_env_file,
    nonnegative_float_from_env,
    nonnegative_int_from_env,
    positive_float_from_env,
)
from medassistmultimodal.providers.ollama import OllamaProvider


@dataclass(frozen=True, slots=True)
class LLMRuntime:
    provider: LLMProvider
    model: str
    language_rewrite_model: str | None = None


def create_llm_runtime(
    env_file: str | Path = '.env',
) -> LLMRuntime:
    load_env_file(env_file)
    provider_name = os.getenv('LLM_PROVIDER', 'ollama').strip().lower()
    timeout_seconds = positive_float_from_env('LLM_TIMEOUT_SECONDS', 60.0)
    retry_policy = RetryPolicy(
        max_retries=nonnegative_int_from_env('LLM_MAX_RETRIES', 2),
        initial_delay_seconds=nonnegative_float_from_env(
            'LLM_RETRY_DELAY_SECONDS',
            0.5,
        ),
        backoff_multiplier=positive_float_from_env(
            'LLM_RETRY_BACKOFF',
            2.0,
        ),
    )

    if provider_name == 'ollama':
        model = _required_setting('OLLAMA_MODEL', 'qwen2.5:7b-instruct')
        provider = OllamaProvider(
            base_url=os.getenv(
                'OLLAMA_BASE_URL',
                'http://localhost:11434',
            ),
            timeout_seconds=timeout_seconds,
        )
        return LLMRuntime(
            provider=RetryingLLMProvider(provider, retry_policy),
            model=model,
            language_rewrite_model=_required_setting(
                'OLLAMA_LANGUAGE_REWRITE_MODEL',
                model,
            ),
        )

    raise ConfigurationError(
        'LLM_PROVIDER deve ser ollama; providers remotos não estão habilitados'
    )


def create_llm_provider(
    env_file: str | Path = '.env',
) -> LLMProvider:
    return create_llm_runtime(env_file).provider


def _required_setting(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ConfigurationError(f'{name} nao pode estar vazio')
    return value
