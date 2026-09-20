"""
Live status of the samples in flight.

The graph nodes and the LLM client report where a sample is ("reviewer, round 2", "judge on
127.0.0.1:1234", "retry 2/3 after APITimeoutError"); the runner renders the table. Which sample
a report belongs to comes from a context variable set by the runner's task, so the agents need
no extra arguments. Reports for a sample the runner never registered are ignored, which keeps
the tracker silent under tests and the dashboard.
"""
from __future__ import annotations

import contextvars
import time
from dataclasses import dataclass, field
from typing import Callable

CURRENT_SAMPLE: contextvars.ContextVar[int] = contextvars.ContextVar("current_sample", default=0)


@dataclass
class SampleStatus:
    attempt: int
    stage: str = "queued"
    detail: str = ""
    note: str = ""
    started: float = field(default_factory=time.monotonic)
    stage_started: float = field(default_factory=time.monotonic)

    def elapsed(self, now: float | None = None) -> float:
        return (now or time.monotonic()) - self.started

    def stage_elapsed(self, now: float | None = None) -> float:
        return (now or time.monotonic()) - self.stage_started


class StatusTracker:
    """One row per sample in flight, updated by whoever is working on it."""

    def __init__(self) -> None:
        self.samples: dict[int, SampleStatus] = {}
        self.note_listeners: list[Callable[[int, str], None]] = []

    def start(self, attempt: int) -> SampleStatus:
        status = SampleStatus(attempt)
        self.samples[attempt] = status
        CURRENT_SAMPLE.set(attempt)
        return status

    def finish(self, attempt: int) -> None:
        self.samples.pop(attempt, None)

    def stage(self, stage: str, detail: str = "", *, attempt: int | None = None) -> None:
        status = self.samples.get(CURRENT_SAMPLE.get() if attempt is None else attempt)
        if status is None:
            return
        if (stage, detail) != (status.stage, status.detail):
            status.stage_started = time.monotonic()
        status.stage, status.detail, status.note = stage, detail, ""

    def note(self, text: str, *, attempt: int | None = None) -> None:
        """A transient remark on the current stage, such as a retry, shown next to it and announced."""
        key = CURRENT_SAMPLE.get() if attempt is None else attempt
        status = self.samples.get(key)
        if status is None:
            return
        status.note = text
        for listener in self.note_listeners:
            listener(key, text)

    def rows(self) -> list[SampleStatus]:
        return [self.samples[k] for k in sorted(self.samples)]

    def __len__(self) -> int:
        return len(self.samples)


TRACKER = StatusTracker()


def fmt_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


__all__ = ["CURRENT_SAMPLE", "SampleStatus", "StatusTracker", "TRACKER", "fmt_seconds"]
