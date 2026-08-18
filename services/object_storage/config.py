"""Small, side-effect-free environment configuration helpers.

These mirror ``services/ai_adapters/config.py`` deliberately.  Object storage
is not an AI adapter, so it does not import from that package; the few
duplicated lines are cheaper than coupling two unrelated boundaries.
"""

from __future__ import annotations

import os


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = env_value(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def env_float(name: str, default: float, *, minimum: float = 0.1) -> float:
    raw = env_value(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, minimum)


def env_bool(name: str, default: bool) -> bool:
    raw = env_value(name)
    if raw is None:
        return default
    normalized = raw.casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def env_clamped_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = env_int(name, default, minimum=0)
    return min(max(value, minimum), maximum)


__all__ = [
    "env_bool",
    "env_clamped_int",
    "env_float",
    "env_int",
    "env_value",
]
