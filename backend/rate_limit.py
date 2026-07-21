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
# X-Forwarded-For is client-controlled unless a trusted proxy sets it, so an
# attacker could mint a fresh rate-limit bucket per request. Only honor it when
# the operator explicitly says their proxy appends the real client address.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"

_MAX_TRACKED_KEYS = 1024

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)
_windows: dict[str, int] = {}


def _client_ip(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Rightmost hop was appended by our own proxy; earlier entries are
            # whatever the client claimed.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _sweep_locked(now: float) -> None:
    # Bound memory: drop keys whose newest hit is outside their window.
    if len(_hits) <= _MAX_TRACKED_KEYS:
        return
    for key in list(_hits):
        window = _hits[key]
        if not window or window[-1] <= now - _windows.get(key, 3600):
            _hits.pop(key, None)
            _windows.pop(key, None)


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
            _sweep_locked(now)
            _windows[key] = window_seconds
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
