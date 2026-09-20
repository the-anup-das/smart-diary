"""
Judge reputation: a persisted score per judge host, moved by agreement with the second judge.

A model cannot be rewarded directly, so the score is made to matter in three ways: the judge
pool is reordered so the most reliable host is asked first, overturned verdicts become lessons
in the judge's own prompt, and a host whose score has fallen far enough must clear a higher
overall threshold to pass a sample. Penalties are larger than rewards: an overturned pass is the
mistake that would poison training data.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path


class JudgeReputation:
    def __init__(self, path: Path | None, *, agree: int = 1, overturned_pass: int = -3, overturned_fail: int = -1, strict_below: int = -5):
        self.path = Path(path) if path else None
        self.agree = agree
        self.overturned_pass = overturned_pass
        self.overturned_fail = overturned_fail
        self.strict_below = strict_below
        self._lock = asyncio.Lock()
        self._data: dict[str, dict] = {}
        if self.path and self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._data = {}

    def _slot(self, label: str) -> dict:
        return self._data.setdefault(label, {"score": 0, "agreed": 0, "overturned_pass": 0, "overturned_fail": 0, "updated": None})

    async def record(self, label: str, *, first_passed: bool, second_passed: bool) -> int:
        """Apply the reward or penalty for one second opinion and return the new score."""
        async with self._lock:
            slot = self._slot(label)
            if first_passed == second_passed:
                slot["score"] += self.agree
                slot["agreed"] += 1
            elif first_passed:
                slot["score"] += self.overturned_pass
                slot["overturned_pass"] += 1
            else:
                slot["score"] += self.overturned_fail
                slot["overturned_fail"] += 1
            slot["updated"] = time.time()
            self._persist()
            return slot["score"]

    def score(self, label: str) -> int:
        return int(self._data.get(label, {}).get("score", 0))

    def threshold_bump(self, label: str) -> int:
        """Extra overall points a slipping judge must award before a sample passes."""
        score = self.score(label)
        if score >= self.strict_below:
            return 0
        return min(2, 1 + (self.strict_below - score) // 5)

    def ordered(self, labels: list[str]) -> list[str]:
        """Labels sorted by score, best first; ties keep their configured order."""
        return sorted(labels, key=lambda label: -self.score(label))

    def snapshot(self) -> dict:
        return {label: dict(slot) for label, slot in self._data.items()}

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
        tmp.replace(self.path)
