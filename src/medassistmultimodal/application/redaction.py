"""
Remove segredos de textos antes de registrá-los em logs ou auditoria.

A redação é determinística e conserva o restante do conteúdo para que a
execução continue rastreável sem persistir credenciais acidentalmente coladas.
"""

from __future__ import annotations

import re


REDACTED = "[REDACTED]"

_SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|secret|password)"
        r"\s*[:=]\s*(['\"]?)[^\s,;]+\2"
    ),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?"
        r"-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def redact_secrets(value: str | None) -> str | None:
    """Substitui formatos comuns de credencial por um marcador seguro."""
    if value is None:
        return None

    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_audit_events(
    events: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    """Redige campos textuais dos eventos antes da persistência."""
    def redact_value(value: object) -> object:
        if isinstance(value, str):
            return redact_secrets(value)
        if isinstance(value, dict):
            return {key: redact_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(redact_value(item) for item in value)
        return value

    return tuple(
        {key: redact_value(value) for key, value in event.items()}
        for event in events
    )
