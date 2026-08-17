"""Shared infrastructure for replaceable production AI providers.

The service layers depend on their local adapter protocols.  This package only
provides transport, configuration, and failure handling that provider
implementations can reuse; it does not contain clinical business logic.
"""

from .config import env_float, env_int, env_value
from .errors import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderRequestError,
    AIProviderResponseError,
    AIProviderTimeoutError,
)
from .http import JSONHTTPClient

__all__ = [
    "AIProviderConfigurationError",
    "AIProviderError",
    "AIProviderRequestError",
    "AIProviderResponseError",
    "AIProviderTimeoutError",
    "JSONHTTPClient",
    "env_float",
    "env_int",
    "env_value",
]
