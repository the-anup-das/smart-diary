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
    How many requests a single server may be generating at once, which model they may be for, and
    a pause between starts.

    A model that fills most of the card can batch only a couple of generations; asking for more
    makes it shift context between them and throughput collapses, so every request slows down
    instead of any finishing. The pause lets the server release the last request's cache before
    the next one claims memory.

    `exclusive_model` is for a host that serves several models from one GPU that cannot hold two
    of them: requests for the model already running are batched together, a request for a second
    model waits until the host is idle, and once one is waiting no further request for the current
    model is admitted, so the host drains and switches instead of starving the newcomer.
    """

    def __init__(self, limit: int, pacing_s: float = 0.0, exclusive_model: bool = False):
        self.limit = max(1, int(limit))
        self.pacing_s = max(0.0, float(pacing_s))
        self.exclusive_model = bool(exclusive_model)
        self.waiting = 0
        self.in_flight = 0
        self.current_model: str | None = None
        self.last_model: str | None = None      # survives the drain, so a switch is counted once
        self.switches = 0
        self._pending_model: str | None = None      # a different model is waiting; drain for it
        self._waiters: list[tuple[tuple, str]] = []  # ((-priority, arrival), model) for everyone queued
        self._seq = 0
        self._condition = asyncio.Condition()
        self._next_start = 0.0
        self._pacing_lock = asyncio.Lock()

    def _may_start(self, model: str) -> bool:
        if self.in_flight >= self.limit:
            return False
        if not self.exclusive_model or self.current_model is None or self.current_model == model:
            # Hold the door for a model that is waiting to take over, so it is not starved.
            return not (self.exclusive_model and self._pending_model not in (None, model))
        return self.in_flight == 0

    def blocked_by_model(self, model: str) -> bool:
        return self.exclusive_model and self.current_model not in (None, model) and self.in_flight > 0

    def _is_next(self, token: tuple, model: str) -> bool:
        """This waiter may go when its model may start and no waiter ahead of it (higher priority, then earlier) can also start."""
        if not self._may_start(model):
            return False
        return token == min(t for t, m in self._waiters if self._may_start(m))

    @contextlib.asynccontextmanager
    async def slot(self, model: str = "", priority: int = 0):
        """Hold a slot on the host for the length of one request.

        `priority` orders the queue: a higher value goes first when a slot frees. The pipeline
        gives later stages a higher priority, so a sample that is nearly done is finished before
        a new one is started, work in progress drains to the next host, and the hosts overlap
        instead of taking turns.
        """
        token = (-int(priority), self._seq)
        self._seq += 1
        async with self._condition:
            self._waiters.append((token, model))
            self.waiting += 1
            try:
                while not self._is_next(token, model):
                    if self.exclusive_model and self.current_model not in (None, model) and self._pending_model is None:
                        self._pending_model = model
                    await self._condition.wait()
            finally:
                self._waiters.remove((token, model))
                self.waiting -= 1
            if self.exclusive_model and self.last_model not in (None, model):
                self.switches += 1
            self.current_model = self.last_model = model
            if self._pending_model == model:
                self._pending_model = None
            self.in_flight += 1
        try:
            if self.pacing_s:
                async with self._pacing_lock:
                    now = time.monotonic()
                    if self._next_start > now:
                        await asyncio.sleep(self._next_start - now)
                        now = time.monotonic()
                    self._next_start = max(now, self._next_start) + self.pacing_s
            yield self
        finally:
            async with self._condition:
                self.in_flight -= 1
                if self.in_flight == 0 and self._pending_model is not None:
                    self.current_model = None       # drained: whoever is waiting may take the host
                self._condition.notify_all()


# One limiter per host and event loop: a semaphore belongs to the loop that awaits it.
_host_limiters: dict[tuple[int, str], HostLimiter] = {}


def host_limiter(host: str, limit: int, pacing_s: float = 0.0, exclusive_model: bool = False) -> HostLimiter:
    try:
        loop_key = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_key = 0
    key = (loop_key, host)
    limiter = _host_limiters.get(key)
    settings = (max(1, int(limit)), max(0.0, float(pacing_s)), bool(exclusive_model))
    if limiter is None or (limiter.limit, limiter.pacing_s, limiter.exclusive_model) != settings:
        limiter = HostLimiter(limit, pacing_s, exclusive_model)
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
