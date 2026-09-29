"""
Pick the judge on evidence.

For a handful of golden entries, get a reference analysis from the analyzer (or reuse a saved
one), then create corrupted copies: the safety flag flipped, topic weights that do not sum to
one, invented passive minutes, a wrong rumination level, two micro-actions instead of three,
and a mood that contradicts the entry. Every judge candidate grades the correct analysis and
each corrupted copy. A good judge passes the correct ones and fails the corrupted ones.

    python -m data_pipeline.eval.judge_calibration --limit 10
    python -m data_pipeline.eval.judge_calibration --judges "http://localhost:1234/v1|lm-studio|google/gemma-4-26b-a4b;https://api.eolarityinnovations.com/v1|env:LLM_API_KEY|Ternary-Bonsai-2-27B"
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from data_pipeline import config  # noqa: E402
from data_pipeline.agents.analyzer import analyze_journal_entry  # noqa: E402
from data_pipeline.agents.judge import judge_candidate, judge_passes, judge_reason  # noqa: E402
from data_pipeline.agents.llm_client import LLMCallError  # noqa: E402
from data_pipeline.agents.schema_validator import validate_schema  # noqa: E402
from data_pipeline.endpoints import parse_endpoint_list  # noqa: E402
from data_pipeline.scripts.evaluate import load_golden  # noqa: E402

console = Console()
CACHE_PATH = config.OUTPUT_DIR / "golden_analyses.jsonl"


def corruptions(analysis: dict, entry: str) -> dict[str, dict]:
    """Named corrupted copies of a correct analysis. Each should be caught by a good judge."""
    out: dict[str, dict] = {}
    a = copy.deepcopy(analysis)
    a["distressFlag"] = not a["distressFlag"]
    out["flipped_distress"] = a

    a = copy.deepcopy(analysis)
    if a.get("topics"):
        a["topics"] = [{"topic": t["topic"], "weight": round(float(t["weight"]) * 0.5, 2)} for t in a["topics"]]
    out["topic_weights_half"] = a

    a = copy.deepcopy(analysis)
    a["cognition"]["passiveConsumptionMinutes"] = 240
    a["cognition"]["shortFormVideo"] = True
    a["cognition"]["brainRotLoad"] = max(2, int(a["cognition"].get("brainRotLoad", 0)))
    out["invented_minutes"] = a

    a = copy.deepcopy(analysis)
    level = a["energyAnalysis"].get("ruminationLevel", "low")
    a["energyAnalysis"]["ruminationLevel"] = "high" if level == "low" else "low"
    out["wrong_rumination"] = a

    a = copy.deepcopy(analysis)
    a["energyAnalysis"]["microActions"] = a["energyAnalysis"]["microActions"][:2]
    out["two_micro_actions"] = a

    a = copy.deepcopy(analysis)
    a["moodScore"] = 9 if int(a.get("moodScore", 5)) <= 5 else 2
    out["contradictory_mood"] = a
    return out


async def reference_analyses(rows: list[dict], analyzer) -> list[dict]:
    """Correct analyses for the golden entries, cached on disk between runs."""
    cached: dict[str, dict] = {}
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    cached[r["id"]] = r["analysis"]
    out = []
    for row in rows:
        analysis = cached.get(row["id"])
        if analysis is None:
            data, error, _usage = await analyze_journal_entry(row["entry"], row["persona"] or None, endpoint=analyzer)
            ok, err, _ = validate_schema(data or {})
            if not ok:
                console.print(f"[yellow]{row['id']}: analyzer output invalid ({err or error}); skipped[/yellow]")
                continue
            analysis = data
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": row["id"], "analysis": analysis}, ensure_ascii=False) + "\n")
        out.append({**row, "analysis": analysis})
    return out


async def calibrate(rows: list[dict], judges, concurrency: int = 3) -> dict:
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, dict] = {}

    async def grade(ep, index, row, name, analysis):
        async with sem:
            try:
                verdict, _usage = await judge_candidate(row["entry"], analysis, row["persona"] or None, endpoint=ep)
                return index, name, judge_passes(verdict), verdict
            except LLMCallError as e:
                return index, name, None, {"error": str(e)[:120]}

    # What the validator alone catches: business-rule breaks never reach a judge in a real run.
    cases: dict[tuple[int, str], dict] = {}
    for index, row in enumerate(rows):
        cases[(index, "correct")] = row["analysis"]
        for name, bad in corruptions(row["analysis"], row["entry"]).items():
            cases[(index, name)] = bad
    validator_ok = {key: validate_schema(analysis)[0] for key, analysis in cases.items()}
    verdicts: dict[tuple[int, str], list] = {key: [] for key in cases}
    explanations: dict[str, list[str]] = {}

    for ep in judges:
        tasks = [grade(ep, index, rows[index], name, analysis) for (index, name), analysis in cases.items()]
        graded = await asyncio.gather(*tasks)
        summary: dict[str, dict] = {}
        rejected: list[str] = []
        for index, name, passed, _verdict in graded:
            verdicts[(index, name)].append(passed)
            if name == "correct" and passed is False:
                rejected.append(judge_reason(_verdict))
            slot = summary.setdefault(name, {"passed": 0, "failed": 0, "errors": 0})
            if passed is None:
                slot["errors"] += 1
            elif passed:
                slot["passed"] += 1
            else:
                slot["failed"] += 1
        results[ep.label] = summary
        explanations[ep.label] = rejected

    # The pipeline: a sample passes only when the validator accepts it and every judge that answered passes it.
    pipeline: dict[str, dict] = {}
    for (index, name), answers in verdicts.items():
        slot = pipeline.setdefault(name, {"passed": 0, "failed": 0, "errors": 0})
        decided = [a for a in answers if a is not None]
        if not decided and validator_ok[(index, name)]:
            slot["errors"] += 1
        elif validator_ok[(index, name)] and all(decided):
            slot["passed"] += 1
        else:
            slot["failed"] += 1
    results["pipeline: validator + all judges"] = pipeline
    results["_rejected_correct"] = explanations
    return results


def print_results(results: dict) -> None:
    names = ["correct", "flipped_distress", "topic_weights_half", "invented_minutes", "wrong_rumination", "two_micro_actions", "contradictory_mood"]
    table = Table(title="Judge calibration: pass rate on correct analyses, fail rate on corrupted ones", border_style="bright_blue")
    table.add_column("Judge", style="bold cyan")
    for name in names:
        table.add_column(name.replace("_", " "), justify="right")
    table.add_column("score", justify="right", style="bold")
    for label, summary in results.items():
        if label.startswith("_"):
            continue
        cells, score_parts = [], []
        for name in names:
            slot = summary.get(name, {})
            total = slot.get("passed", 0) + slot.get("failed", 0)
            if not total:
                cells.append("-")
                continue
            if name == "correct":
                rate = slot["passed"] / total
                cells.append(f"pass {rate * 100:.0f}%")
            else:
                rate = slot["failed"] / total
                cells.append(f"fail {rate * 100:.0f}%")
            score_parts.append(rate)
        cells.append(f"{(sum(score_parts) / len(score_parts)) * 100:.0f}%" if score_parts else "-")
        table.add_row(label, *cells)
    console.print(table)
    console.print("A judge scores well when it passes correct analyses and fails every corruption. Errors mean the host could not be reached.")
    console.print("The pipeline row is what a real run does: the validator rejects rule breaks before any judge sees them, and a fail from any judge is a fail.")
    for label, reasons in (results.get("_rejected_correct") or {}).items():
        if reasons:
            console.print(f"\n[bold]{label}[/bold] rejected {len(reasons)} correct analyses:")
            for reason in reasons:
                console.print(f"  - {reason[:200]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate judge candidates on correct and corrupted analyses")
    parser.add_argument("--limit", type=int, default=8, help="golden entries to use")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--judges", default=None, help="endpoint list; default JUDGE_ENDPOINTS plus JUDGE2_ENDPOINT")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    config.require_api_key()
    config.ensure_dirs()

    judges = parse_endpoint_list(args.judges, name="judge") if args.judges else config.judge_endpoints()
    if not args.judges and config.judge2_endpoint():
        judges.append(config.judge2_endpoint())
    if not judges:
        raise SystemExit("no judge endpoints configured")
    rows = load_golden()
    random.Random(args.seed).shuffle(rows)
    rows = rows[: args.limit]
    analyzer = config.role_endpoint("analyzer", config.ANALYZER_MODEL)
    console.print(f"analyzer {analyzer.label}; judges: {', '.join(ep.label for ep in judges)}; {len(rows)} entries x 7 grades each")
    rows = asyncio.run(reference_analyses(rows, analyzer))
    results = asyncio.run(calibrate(rows, judges, args.concurrency))
    print_results(results)
    out = config.OUTPUT_DIR / "judge_calibration.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    console.print(f"saved to {out}")


if __name__ == "__main__":
    main()
