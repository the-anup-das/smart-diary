"""
Lessons store: rejection reasons that steer later samples.

Four buckets: `entry` (what reviewers and judges disliked about the prose, for the writer),
`reviewer` (entries the reviewer approved that the judge later rejected), `labels` (what the
judge disliked about the analysis, for the analyzer) and `judge` (verdicts the second judge
overturned, for the judge). Entries are deduplicated on a normalised form, counted,
persisted on every change, loaded on resume, and merged under a lock so concurrent workers
never overwrite each other. They are a generation-time aid only: training records always carry
the production prompt, never these lessons.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

BUCKETS = ("entry", "reviewer", "labels", "judge")
_MAX_TEXT = 220


def normalise(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()[:160]


class LessonsStore:
    def __init__(self, path: Path | None, max_items: int = 8, enabled: bool = True):
        self.path = Path(path) if path else None
        self.max_items = max_items
        self.enabled = enabled
        self._lock = asyncio.Lock()
        self._data: dict[str, dict[str, dict]] = {b: {} for b in BUCKETS}
        if self.path and self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                for bucket in BUCKETS:
                    self._data[bucket] = dict(loaded.get(bucket, {}))
            except (OSError, ValueError):
                pass

    async def add(self, bucket: str, text: str) -> None:
        if not self.enabled or bucket not in BUCKETS:
            return
        text = (text or "").strip()
        key = normalise(text)
        if len(key) < 12:
            return
        async with self._lock:
            slot = self._data[bucket].get(key)
            if slot:
                slot["count"] += 1
                slot["last_seen"] = time.time()
            else:
                self._data[bucket][key] = {"text": text[:_MAX_TEXT], "count": 1, "last_seen": time.time()}
            self._persist()

    def top(self, bucket: str) -> list[str]:
        if not self.enabled:
            return []
        rows = sorted(self._data.get(bucket, {}).values(), key=lambda r: (-r["count"], -r["last_seen"]))
        return [r["text"] for r in rows[: self.max_items]]

    def counts(self) -> dict[str, int]:
        return {bucket: len(rows) for bucket, rows in self._data.items()}

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)
