"""Prompt-boundary controls for untrusted clinical text and instructions."""

from __future__ import annotations

import re


class PromptInjectionError(ValueError):
    """Raised when physician-provided instructions attempt prompt control."""


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b", re.I),
    re.compile(r"\b(?:system|developer)\s+(?:message|prompt|instruction)\b", re.I),
    re.compile(r"\b(?:reveal|expose|print|leak)\s+(?:the\s+)?(?:prompt|secret|token|api\s*key)\b", re.I),
    re.compile(r"\bexecute\s+(?:this|the)\s+(?:command|code|tool)\b", re.I),
)


def sanitize_prompt_data(value: str | None, *, max_length: int = 12000) -> str:
    if not value:
        return ""
    clean = _CONTROL_CHARS.sub(" ", str(value)).strip()
    return clean[:max_length]


def validate_physician_instructions(value: str | None) -> str:
    clean = sanitize_prompt_data(value, max_length=4000)
    if not clean:
        return ""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(clean):
            raise PromptInjectionError(
                "Physician instructions contain disallowed prompt-control content."
            )
    return clean


def untrusted_prompt_block(value: str | None) -> str:
    clean = sanitize_prompt_data(value)
    return f"<<<UNTRUSTED_CLINICAL_DATA>>>\n{clean}\n<<<END_UNTRUSTED_CLINICAL_DATA>>>"


__all__ = [
    "PromptInjectionError",
    "sanitize_prompt_data",
    "untrusted_prompt_block",
    "validate_physician_instructions",
]
