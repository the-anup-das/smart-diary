"""
Per-model inference speed.

Every chat completion the pipeline makes is timed and, when the server reports token counts,
turned into a tokens-per-second figure. The registry keeps the numbers for the run board and
appends one JSON line per call to `logs/calls.jsonl` for the dashboard, so speed can be compared
across models, roles and runs. It never blocks a call: recording is a dictionary update and one
buffered file write.
"""
from __future__ import annotations

import json
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from data_pipeline.status import CURRENT_SAMPLE

RECENT = 50   # calls kept per model for the rolling medians on the board


@dataclass
class ModelStats:
    label: str                       # model@host
    model: str
    host: str
    roles: set[str] = field(default_factory=set)
    calls: int = 0
    errors: int = 0
    timeouts: int = 0
    in_flight: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_latency: float = 0.0
    recent_latency: deque = field(default_factory=lambda: deque(maxlen=RECENT))
    recent_tps: deque = field(default_factory=lambda: deque(maxlen=RECENT))
    last_tps: Optional[float] = None
    last_latency: Optional[float] = None

    @property
    def avg_latency(self) -> Optional[float]:
        done = self.calls - self.errors
        return self.total_latency / done if done else None

    @property
    def median_latency(self) -> Optional[float]:
        return statistics.median(self.recent_latency) if self.recent_latency else None

    @property
    def median_tps(self) -> Optional[float]:
        return statistics.median(self.recent_tps) if self.recent_tps else None

    def snapshot(self) -> dict:
        return {
            "label": self.label, "model": self.model, "host": self.host, "roles": sorted(self.roles),
            "calls": self.calls, "errors": self.errors, "timeouts": self.timeouts, "inFlight": self.in_flight,
            "promptTokens": self.prompt_tokens, "completionTokens": self.completion_tokens,
            "avgLatency": self.avg_latency, "medianLatency": self.median_latency,
            "medianTps": self.median_tps, "lastTps": self.last_tps, "lastLatency": self.last_latency,
        }


class MetricsRegistry:
    """In-memory speed figures per model, plus an optional JSONL log of every call."""

    def __init__(self) -> None:
        self.models: dict[str, ModelStats] = {}
        self.log_path: Optional[Path] = None
        self._lock = threading.Lock()
        self._file = None

    def enable_log(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path = path

    def disable_log(self) -> None:
        self.log_path = None
        if self._file:
            try:
                self._file.close()
            except Exception:  # noqa: BLE001
                pass
            self._file = None

    def _stats(self, ep) -> ModelStats:
        label = f"{ep.model}@{ep.host}"
        stats = self.models.get(label)
        if stats is None:
            stats = self.models[label] = ModelStats(label=label, model=ep.model, host=ep.host)
        if getattr(ep, "name", ""):
            stats.roles.add(str(ep.name))
        return stats

    def start(self, ep) -> float:
        with self._lock:
            self._stats(ep).in_flight += 1
        return time.monotonic()

    def finish(self, ep, started: float, *, usage: Optional[dict] = None, error: Optional[str] = None, timeout: bool = False) -> dict:
        """Record one completed or failed call. Returns the record written."""
        latency = max(0.0, time.monotonic() - started)
        prompt = int((usage or {}).get("prompt_tokens") or 0)
        completion = int((usage or {}).get("completion_tokens") or 0)
        tps = (completion / latency) if (error is None and completion and latency > 0) else None
        with self._lock:
            stats = self._stats(ep)
            stats.in_flight = max(0, stats.in_flight - 1)
            stats.calls += 1
            stats.last_latency = latency
            if error is None:
                stats.total_latency += latency
                stats.prompt_tokens += prompt
                stats.completion_tokens += completion
                stats.recent_latency.append(latency)
                if tps is not None:
                    stats.recent_tps.append(tps)
                    stats.last_tps = tps
            else:
                stats.errors += 1
                if timeout:
                    stats.timeouts += 1
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": ep.model, "host": ep.host, "role": getattr(ep, "name", "") or "",
                "sample": CURRENT_SAMPLE.get() or None,
                "latency_s": round(latency, 3), "prompt_tokens": prompt, "completion_tokens": completion,
                "tokens_per_s": round(tps, 2) if tps is not None else None,
                "ok": error is None, "error": (error or "")[:160] or None, "timeout": timeout,
            }
            self._write(record)
        return record

    def _write(self, record: dict) -> None:
        if self.log_path is None:
            return
        try:
            if self._file is None:
                self._file = open(self.log_path, "a", encoding="utf-8")
            self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._file.flush()
        except Exception:  # noqa: BLE001  a speed log must never break a call
            pass

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [s.snapshot() for s in sorted(self.models.values(), key=lambda s: (-s.calls, s.label))]

    def reset(self) -> None:
        with self._lock:
            self.models.clear()
        self.disable_log()


METRICS = MetricsRegistry()


def fmt_tps(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.1f} tok/s"


def fmt_latency(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}s" if value < 100 else f"{value / 60:.1f}m"


__all__ = ["METRICS", "MetricsRegistry", "ModelStats", "fmt_tps", "fmt_latency"]
