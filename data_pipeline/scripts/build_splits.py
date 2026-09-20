"""
Turn output/dataset_raw.jsonl into training and test splits.

- Exact duplicates (normalised entry text) and near duplicates (5-word shingle Jaccard above a
  threshold, checked within the same edge-case bucket) are dropped.
- The split is stratified on (edge case, distressFlag) and seeded, so it is reproducible.
- Records become ShareGPT conversations whose system turn is the production prompt from the
  contract, with the analysis as compact JSON. A manifest records hashes, counts and settings.

    python -m data_pipeline.scripts.build_splits --seed 3407 --test-ratio 0.1
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from data_pipeline import config
from data_pipeline.contracts import PROMPT_VERSION, FeedbackReportSchema, build_analysis_system_prompt


def load_raw(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def shingles(text: str, n: int = 5) -> set[str]:
    words = normalise(text).split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def stratum(record: dict) -> str:
    meta = record.get("meta") or {}
    return f"{meta.get('edge_case') or 'none'}|{'distress' if record['analysis'].get('distressFlag') else 'ok'}"


def dedup(records: list[dict], threshold: float = 0.8) -> tuple[list[dict], dict]:
    """Keep the first occurrence; drop exact and near duplicates. Near-duplicate checks stay inside a stratum."""
    seen_exact: set[str] = set()
    kept: list[dict] = []
    kept_shingles: dict[str, list[set[str]]] = defaultdict(list)
    stats = {"exact": 0, "near": 0, "invalid": 0}
    for record in records:
        try:
            FeedbackReportSchema.model_validate(record["analysis"])
        except (ValidationError, KeyError, TypeError):
            stats["invalid"] += 1
            continue
        key = hashlib.sha256(normalise(record["entry"]).encode("utf-8")).hexdigest()
        if key in seen_exact:
            stats["exact"] += 1
            continue
        bucket = stratum(record)
        sh = shingles(record["entry"])
        if any(jaccard(sh, other) >= threshold for other in kept_shingles[bucket]):
            stats["near"] += 1
            continue
        seen_exact.add(key)
        kept_shingles[bucket].append(sh)
        kept.append(record)
    return kept, stats


def stratified_split(records: list[dict], test_ratio: float, seed: int) -> tuple[list[dict], list[dict]]:
    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_stratum[stratum(record)].append(record)
    rng = random.Random(seed)
    train, test = [], []
    for name in sorted(by_stratum):
        rows = sorted(by_stratum[name], key=lambda r: r.get("id", ""))
        rng.shuffle(rows)
        n_test = int(round(len(rows) * test_ratio))
        if len(rows) >= 4 and n_test == 0:
            n_test = 1  # every stratum with a few members is represented in the test set
        test.extend(rows[:n_test])
        train.extend(rows[n_test:])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def to_sharegpt(record: dict) -> dict:
    persona = (record.get("meta") or {}).get("custom_persona") or ""
    return {
        "id": record.get("id"),
        "conversations": [
            {"from": "system", "value": build_analysis_system_prompt(persona)},
            {"from": "human", "value": record["entry"]},
            {"from": "gpt", "value": json.dumps(record["analysis"], ensure_ascii=False, separators=(",", ":"))},
        ],
    }


def write_jsonl(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False) + "\n"
            f.write(line)
            digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def build(raw_path: Path, out_dir: Path, *, test_ratio: float, seed: int, near_threshold: float = 0.8) -> dict:
    records = load_raw(raw_path)
    kept, dedup_stats = dedup(records, near_threshold)
    train, test = stratified_split(kept, test_ratio, seed)
    train_path, test_path = out_dir / "training_dataset.jsonl", out_dir / "test_dataset.jsonl"
    train_sha = write_jsonl(train_path, [to_sharegpt(r) for r in train])
    test_sha = write_jsonl(test_path, [to_sharegpt(r) for r in test])
    strata = defaultdict(lambda: {"train": 0, "test": 0})
    for r in train:
        strata[stratum(r)]["train"] += 1
    for r in test:
        strata[stratum(r)]["test"] += 1
    manifest = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "seed": seed, "test_ratio": test_ratio, "near_duplicate_threshold": near_threshold,
        "raw_records": len(records), "dedup": dedup_stats, "kept": len(kept),
        "train": {"path": train_path.name, "rows": len(train), "sha256": train_sha},
        "test": {"path": test_path.name, "rows": len(test), "sha256": test_sha},
        "strata": dict(sorted(strata.items())),
        "teacher_models": sorted({(r.get("meta") or {}).get("teacher_model") or "?" for r in kept}),
        "writer_models": sorted({(r.get("meta") or {}).get("writer_model") or "?" for r in kept}),
    }
    (out_dir / "splits_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedup, stratify and split the raw dataset into ShareGPT files")
    parser.add_argument("--input", type=Path, default=config.RAW_DATASET_PATH)
    parser.add_argument("--out-dir", type=Path, default=config.OUTPUT_DIR)
    parser.add_argument("--test-ratio", type=float, default=config.TEST_SPLIT_RATIO)
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--near-threshold", type=float, default=0.8)
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"{args.input} does not exist; run the pipeline first")
    manifest = build(args.input, args.out_dir, test_ratio=args.test_ratio, seed=args.seed, near_threshold=args.near_threshold)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
