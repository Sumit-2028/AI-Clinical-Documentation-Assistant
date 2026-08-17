"""Bounded JSON HTTP transport for provider adapters.

Only request metadata is logged.  Payloads and responses can contain medical
content and are deliberately never included in log messages.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any

from .errors import (
    AIProviderConfigurationError,
    AIProviderRequestError,
    AIProviderResponseError,
    AIProviderTimeoutError,
)

try:  # Keep imports optional for services that only use deterministic mocks.
    import httpx
except ImportError:  # pragma: no cover - exercised only in minimal deployments.
    httpx = None


logger = logging.getLogger("clinical_memory.ai")


class JSONHTTPClient:
    """POST JSON with timeout, bounded retries, and injectable transport.

    ``client`` is intentionally duck-typed.  Production uses ``httpx.Client``;
    tests can inject a tiny fake with a ``post`` method and avoid all network
    access.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        backoff_seconds: float = 0.1,
    ) -> None:
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.max_retries = max(int(max_retries), 0)
        self._client = client
        self._sleep = sleep
        self._backoff_seconds = max(float(backoff_seconds), 0.0)

    @property
    def client(self) -> Any:
        if self._client is None:
            if httpx is None:
                raise AIProviderConfigurationError(
                    "httpx is required for configured AI HTTP providers."
                )
            self._client = httpx.Client()
        return self._client

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        *,
        provider: str,
        operation: str,
        api_key: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        if not url.strip():
            raise AIProviderConfigurationError(
                f"AI provider '{provider}' has no endpoint configured."
            )

        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        if api_key:
            request_headers.setdefault("Authorization", f"Bearer {api_key}")

        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                response = self.client.post(
                    url,
                    json=dict(payload),
                    headers=request_headers,
                    timeout=self.timeout_seconds,
                )
                status_code = int(getattr(response, "status_code", 0))
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                logger.info(
                    "ai_provider_request provider=%s operation=%s attempt=%s status=%s duration_ms=%s",
                    provider,
                    operation,
                    attempt,
                    status_code,
                    duration_ms,
                )

                if status_code >= 500:
                    if attempt < attempts:
                        self._retry(attempt)
                        continue
                    raise AIProviderRequestError(
                        f"AI provider '{provider}' returned server status {status_code}."
                    )
                if status_code >= 400 or status_code == 0:
                    raise AIProviderRequestError(
                        f"AI provider '{provider}' rejected the {operation} request "
                        f"with status {status_code}."
                    )
                try:
                    body = response.json()
                except Exception as exc:  # provider response is outside our control
                    raise AIProviderResponseError(
                        f"AI provider '{provider}' returned invalid JSON."
                    ) from exc
                if not isinstance(body, Mapping):
                    raise AIProviderResponseError(
                        f"AI provider '{provider}' returned a non-object response."
                    )
                return body
            except AIProviderRequestError:
                raise
            except AIProviderResponseError:
                raise
            except (TimeoutError, OSError) as exc:
                if attempt < attempts:
                    logger.warning(
                        "ai_provider_retry provider=%s operation=%s attempt=%s error_type=%s",
                        provider,
                        operation,
                        attempt,
                        type(exc).__name__,
                    )
                    self._retry(attempt)
                    continue
                raise AIProviderTimeoutError(
                    f"AI provider '{provider}' timed out during {operation}."
                ) from exc
            except Exception as exc:
                # httpx timeout/request exceptions are optional imports and are
                # normalized here without exposing provider response content.
                if httpx is not None and isinstance(exc, httpx.TimeoutException):
                    if attempt < attempts:
                        logger.warning(
                            "ai_provider_retry provider=%s operation=%s attempt=%s error_type=%s",
                            provider,
                            operation,
                            attempt,
                            type(exc).__name__,
                        )
                        self._retry(attempt)
                        continue
                    raise AIProviderTimeoutError(
                        f"AI provider '{provider}' timed out during {operation}."
                    ) from exc
                if httpx is not None and isinstance(exc, httpx.RequestError):
                    if attempt < attempts:
                        logger.warning(
                            "ai_provider_retry provider=%s operation=%s attempt=%s error_type=%s",
                            provider,
                            operation,
                            attempt,
                            type(exc).__name__,
                        )
                        self._retry(attempt)
                        continue
                    raise AIProviderRequestError(
                        f"AI provider '{provider}' could not complete {operation}."
                    ) from exc
                raise AIProviderRequestError(
                    f"AI provider '{provider}' could not complete {operation}."
                ) from exc

        raise AIProviderRequestError(
            f"AI provider '{provider}' could not complete {operation}."
        )

    def _retry(self, attempt: int) -> None:
        delay = self._backoff_seconds * (2 ** (attempt - 1))
        if delay:
            self._sleep(delay)


__all__ = ["JSONHTTPClient"]
