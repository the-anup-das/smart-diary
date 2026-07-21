"""Lightweight in-memory rate limiting for a single-instance, self-hosted deployment.

No external dependencies (Redis, slowapi) — a sliding-window counter keyed by
client IP + scope is plenty for protecting auth and AI endpoints on a home server.
"""
import os
import time
import threading
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# Allow operators to disable limits entirely (e.g. behind an authenticating proxy)
RATE_LIMIT_DISABLED = os.getenv("RATE_LIMIT_DISABLED", "false").lower() == "true"

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # The Next.js rewrite proxy sits in front of the backend, so the direct
    # peer address is usually the proxy. Prefer the first hop it forwards.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, max_requests: int, window_seconds: int):
    """Build a FastAPI dependency enforcing `max_requests` per `window_seconds`.

    Usage: Depends(rate_limit("login", 10, 300))
    """

    def dependency(request: Request):
        if RATE_LIMIT_DISABLED:
            return
        key = f"{scope}:{_client_ip(request)}"
        now = time.monotonic()
        with _lock:
            window = _hits[key]
            while window and window[0] <= now - window_seconds:
                window.popleft()
            if len(window) >= max_requests:
                retry_after = int(window[0] + window_seconds - now) + 1
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            window.append(now)

    return dependency
