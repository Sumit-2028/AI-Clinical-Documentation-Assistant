"""Small in-process rate limiter for gateway abuse protection.

This intentionally avoids introducing a new service or database. Deployments
with multiple gateway replicas should place a shared edge limiter in front of
the gateway and keep these local limits as defense in depth.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import RLock
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool = True,
        requests_per_minute: int = 120,
        auth_requests_per_minute: int = 20,
        window_seconds: float = 60.0,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.requests_per_minute = max(requests_per_minute, 1)
        self.auth_requests_per_minute = max(auth_requests_per_minute, 1)
        self.window_seconds = max(window_seconds, 1.0)
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = RLock()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled or request.url.path == "/health":
            return await call_next(request)

        bucket = "auth" if request.url.path in {
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
        } else "api"
        limit = (
            self.auth_requests_per_minute
            if bucket == "auth"
            else self.requests_per_minute
        )
        client_host = request.client.host if request.client else "unknown"
        key = (client_host, bucket)
        now = monotonic()

        with self._lock:
            timestamps = self._requests[key]
            cutoff = now - self.window_seconds
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= limit:
                retry_after = max(1, int(self.window_seconds - (now - timestamps[0])))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests."},
                    headers={"Retry-After": str(retry_after)},
                )
            timestamps.append(now)
            remaining = max(0, limit - len(timestamps))

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


__all__ = ["InMemoryRateLimitMiddleware"]
