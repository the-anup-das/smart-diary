"""
Endpoint descriptions, a pool that rotates through them when one is rate-limited or down,
and a client-side rate limiter for hosts with tight per-minute caps.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse


def is_local_host(base_url: str) -> bool:
    """LM Studio, llama-server, a compose service: loopback, a private range, or a bare hostname."""
    host = (urlparse(base_url).hostname or base_url).lower()
    if host in ("localhost", "host.docker.internal") or host.startswith(("127.", "10.", "192.168.", "0.0.0.0")):
        return True
    if host.startswith("172.") and host.split(".")[1].isdigit() and 16 <= int(host.split(".")[1]) <= 31:
        return True
    return "." not in host


# Model families that reason before answering. Sent by default so a reviewer or judge does not
# spend its token budget thinking; an explicit extra (or <ROLE>_EXTRA) always wins.
THINKING_SWITCH_FAMILIES = ("gemma-4", "gemma4", "qwen3", "nemotron", "glm-4", "deepseek", "magistral", "ministral", "phi-4-reasoning")


def default_extras(model: str, base_url: str = "") -> dict:
    """Request parameters a model family needs to behave in this pipeline.

    gpt-oss takes `reasoning_effort` (OpenAI, Cerebras, and as a chat-template variable on
    llama.cpp servers). Local thinking models get `enable_thinking: false` through
    `chat_template_kwargs`, which LM Studio and llama-server pass to the chat template; remote
    APIs are left alone because the parameter is server specific.
    """
    name = (model or "").lower()
    local = is_local_host(base_url) if base_url else False
    out: dict = {}
    if "gpt-oss" in name:
        out["reasoning_effort"] = "low"
        if local:
            out["chat_template_kwargs"] = {"reasoning_effort": "low"}
    elif local and any(family in name for family in THINKING_SWITCH_FAMILIES):
        out["chat_template_kwargs"] = {"enable_thinking": False}
    return out


@dataclass(frozen=True)
class Endpoint:
    base_url: str
    api_key: str
    model: str
    name: str = ""
    extra: dict = field(default_factory=dict, compare=False, hash=False)  # request params sent only to this host
    rpm: int | None = None                                                  # client-side requests-per-minute cap

    def __post_init__(self) -> None:
        merged = {**default_extras(self.model, self.base_url), **(self.extra or {})}
        object.__setattr__(self, "extra", merged)

    @property
    def host(self) -> str:
        return urlparse(self.base_url).netloc or self.base_url

    @property
    def label(self) -> str:
        return f"{self.model}@{self.host}"


def resolve_key(token: str) -> str | None:
    """`env:NAME` reads NAME from the environment (None when unset); anything else is a literal key."""
    token = (token or "").strip()
    if token.startswith("env:"):
        value = os.getenv(token[4:].strip(), "").strip()
        return value or None
    return token or "empty"


def parse_endpoint(spec: str, name: str = "") -> Endpoint | None:
    """Parse `base_url|key|model[|extra_json]`. Returns None when the key's env var is unset."""
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) < 3 or not parts[0] or not parts[2]:
        raise ValueError(f"endpoint spec needs base_url|key|model, got: {spec!r}")
    base_url, key_token, model = parts[0], parts[1], parts[2]
    extra = json.loads(parts[3]) if len(parts) > 3 and parts[3] else {}
    if not isinstance(extra, dict):
        raise ValueError(f"endpoint extra must be a JSON object, got: {parts[3]!r}")
    key = resolve_key(key_token)
    if key is None:
        return None
    rpm = extra.pop("rpm", None)
    return Endpoint(
        base_url=base_url.rstrip("/"), api_key=key, model=model, name=name,
        extra=extra, rpm=int(rpm) if rpm else None,
    )


def parse_endpoint_list(spec: str, name: str = "") -> list[Endpoint]:
    endpoints = []
    for i, part in enumerate(s for s in spec.split(";") if s.strip()):
        ep = parse_endpoint(part, name=f"{name}{i + 1}" if name else "")
        if ep is not None:
            endpoints.append(ep)
    return endpoints


class RateLimiter:
    """Spaces requests to at most `rpm` a minute across all workers."""

    def __init__(self, rpm: int):
        self.interval = 60.0 / max(1, rpm)
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
                now = time.monotonic()
            self._next = max(now, self._next) + self.interval


class HostLimiter:
    """
    How many requests a single server may be generating at once, plus a pause between starts.

    A model that fills most of the card can batch only a couple of generations; asking for more
    makes it shift context between them and throughput collapses, so every request slows down
    instead of any finishing. The pause lets the server release the last request's cache before
    the next one claims memory.
    """

    def __init__(self, limit: int, pacing_s: float = 0.0):
        self.limit = max(1, int(limit))
        self.pacing_s = max(0.0, float(pacing_s))
        self.semaphore = asyncio.Semaphore(self.limit)
        self.waiting = 0
        self._next_start = 0.0
        self._lock = asyncio.Lock()

    @property
    def in_flight(self) -> int:
        return self.limit - self.semaphore._value  # noqa: SLF001

    @contextlib.asynccontextmanager
    async def slot(self):
        """Hold a slot on the host for the length of one request."""
        self.waiting += 1
        try:
            await self.semaphore.acquire()
        finally:
            self.waiting -= 1
        try:
            if self.pacing_s:
                async with self._lock:
                    now = time.monotonic()
                    if self._next_start > now:
                        await asyncio.sleep(self._next_start - now)
                        now = time.monotonic()
                    self._next_start = max(now, self._next_start) + self.pacing_s
            yield self
        finally:
            self.semaphore.release()


# One limiter per host and event loop: a semaphore belongs to the loop that awaits it.
_host_limiters: dict[tuple[int, str], HostLimiter] = {}


def host_limiter(host: str, limit: int, pacing_s: float = 0.0) -> HostLimiter:
    try:
        loop_key = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_key = 0
    key = (loop_key, host)
    limiter = _host_limiters.get(key)
    if limiter is None or limiter.limit != max(1, int(limit)) or limiter.pacing_s != max(0.0, float(pacing_s)):
        limiter = HostLimiter(limit, pacing_s)
        _host_limiters[key] = limiter
    return limiter


def reset_host_limiters() -> None:
    _host_limiters.clear()


class EndpointPool:
    """
    Ordered endpoints. `pick()` returns the first one not cooling down; `penalise()` puts an
    endpoint on cooldown after a rate limit, quota error or outage, so the next call moves on.
    """

    def __init__(self, endpoints: list[Endpoint], cooldown_s: float = 90.0):
        self.endpoints = list(endpoints)
        self.cooldown_s = cooldown_s
        self._until: dict[Endpoint, float] = {}
        self._limiters: dict[Endpoint, RateLimiter] = {ep: RateLimiter(ep.rpm) for ep in endpoints if ep.rpm}

    def set_order(self, labels: list[str]) -> None:
        """Reorder the endpoints by a list of labels, best first; unknown labels keep their place."""
        rank = {label: i for i, label in enumerate(labels)}
        self.endpoints.sort(key=lambda ep: rank.get(ep.label, len(rank)))

    def pick(self, exclude: set[Endpoint] | None = None) -> Endpoint | None:
        now = time.monotonic()
        for ep in self.endpoints:
            if exclude and ep in exclude:
                continue
            if self._until.get(ep, 0.0) <= now:
                return ep
        return None

    def penalise(self, ep: Endpoint, seconds: float | None = None) -> None:
        self._until[ep] = time.monotonic() + (self.cooldown_s if seconds is None else seconds)

    def seconds_until_available(self) -> float:
        now = time.monotonic()
        waits = [max(0.0, self._until.get(ep, 0.0) - now) for ep in self.endpoints]
        return min(waits) if waits else 0.0

    async def throttle(self, ep: Endpoint) -> None:
        limiter = self._limiters.get(ep)
        if limiter:
            await limiter.wait()

    def __len__(self) -> int:
        return len(self.endpoints)
