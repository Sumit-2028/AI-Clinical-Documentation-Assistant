"""Small, side-effect-free environment configuration helpers."""

from __future__ import annotations

import os


def env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def env_float(name: str, default: float, *, minimum: float = 0.1) -> float:
    raw = env_value(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, minimum)


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = env_value(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)
