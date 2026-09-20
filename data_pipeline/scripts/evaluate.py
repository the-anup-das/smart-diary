"""
Evaluate a model on the production analysis task.

Backends:
  endpoint  any OpenAI-compatible server, called through the same structured-output ladder as the
            pipeline, with the production prompt. This is how a served GGUF, a teacher candidate on
            the private endpoint, or a cloud model is scored.
  unsloth   local HF weights (base or fine-tuned adapter) with greedy decoding on a GPU.

Datasets:
  golden    eval/golden_set.jsonl, hand-written entries with expected key fields.
  test      output/test_dataset.jsonl, held out from training; the reference is the teacher's analysis.

    python scripts/evaluate.py --backend endpoint --base-url http://localhost:8080/v1 --model smart-diary-slm --dataset both --gate
    python scripts/evaluate.py --backend endpoint --base-url $LLM_BASE_URL --api-key-env LLM_API_KEY --model Ternary-Bonsai-2-27B --dataset golden --label teacher-bonsai
    python scripts/evaluate.py --backend unsloth --model qwen --dataset both --gate
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from data_pipeline import config  # noqa: E402
from data_pipeline.agents.llm_client import LLMCallError, acall_structured  # noqa: E402
from data_pipeline.contracts import PROMPT_VERSION, FeedbackReportSchema, analysis_messages  # noqa: E402
from data_pipeline.endpoints import Endpoint  # noqa: E402
from data_pipeline.eval.metrics import aggregate, expected_from_analysis, gate, load_thresholds, score_one  # noqa: E402

console = Console()
GOLDEN_PATH = HERE.parent / "eval" / "golden_set.jsonl"
RESULTS_PATH = config.OUTPUT_DIR / "eval_results.json"


# ---------------------------------------------------------------- datasets

def load_golden(path: Path = GOLDEN_PATH) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                rows.append({"id": r["id"], "group": r.get("group"), "entry": r["entry"], "persona": r.get("custom_persona") or "", "expected": r["expected"]})
    return rows


def load_test(path: Path | None = None) -> list[dict]:
    """The held-out split; the teacher's analysis becomes the reference."""
    path = path or config.TEST_DATASET_PATH
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            convo = {m["from"]: m["value"] for m in r["conversations"]}
            system = convo.get("system", "")
            persona = ""
            marker = "USER'S CUSTOM INSTRUCTIONS: "
            if marker in system:
                persona = system.split(marker, 1)[1].strip()
            analysis = json.loads(convo["gpt"])
            rows.append({"id": r.get("id"), "group": "test", "entry": convo["human"], "persona": persona, "expected": expected_from_analysis(analysis), "reference": analysis})
    return rows


def select(rows: list[dict], limit: int | None, seed: int) -> list[dict]:
    if not limit or limit >= len(rows):
        return rows
    rng = random.Random(seed)
    return rng.sample(rows, limit)


# ---------------------------------------------------------------- backends

async def run_endpoint(rows: list[dict], ep: Endpoint, concurrency: int, temperature: float = 0.2) -> list[dict]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def one(row: dict) -> dict:
        async with sem:
            started = time.monotonic()
            try:
                result = await acall_structured(ep, analysis_messages(row["entry"], row["persona"]), FeedbackReportSchema, temperature=temperature, max_tokens=config.MAX_TOKENS_ANALYSIS)
                latency = time.monotonic() - started
                return {"id": row["id"], "group": row["group"], "analysis": result.data, "error": result.error, "latency_s": latency, "tokens": result.usage.get("completion_tokens"), "mode": result.mode}
            except LLMCallError as e:
                return {"id": row["id"], "group": row["group"], "analysis": None, "error": str(e)[:200], "latency_s": time.monotonic() - started, "tokens": None, "mode": None}

    return await asyncio.gather(*(one(r) for r in rows))


def run_unsloth(rows: list[dict], family: str, adapter: str | None, use_base: bool, max_new_tokens: int = 2048) -> list[dict]:
    import torch
    from unsloth.chat_templates import get_chat_template

    from data_pipeline.agents.llm_client import extract_json_object
    from data_pipeline.scripts.finetune import BASE_MODELS, CHAT_TEMPLATES, MULTIMODAL, OUTPUT_DIR, load_student, render_chat

    model_name = BASE_MODELS[family] if use_base else (adapter or str(OUTPUT_DIR / f"lora_{family}"))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    loader, model, tokenizer = load_student(model_name, family, 4096)
    tokenizer = get_chat_template(tokenizer, chat_template=CHAT_TEMPLATES[family])
    loader.for_inference(model)
    out = []
    for row in rows:
        messages = analysis_messages(row["entry"], row["persona"])
        # Rendered the same way as training, thinking off for the families that have it, then tokenised with the model's own <bos>.
        prompt = render_chat(tokenizer, messages, family, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=family in MULTIMODAL).input_ids.to(device)   # the other templates already carry their own start token
        started = time.monotonic()
        with torch.no_grad():
            generated = model.generate(input_ids=inputs, max_new_tokens=max_new_tokens, do_sample=False, temperature=None, top_p=None, use_cache=True)
        latency = time.monotonic() - started
        text = tokenizer.decode(generated[0][inputs.shape[-1]:], skip_special_tokens=True)
        data = extract_json_object(text)
        out.append({"id": row["id"], "group": row["group"], "analysis": data, "error": None if data else "no JSON object", "latency_s": latency, "tokens": int(generated.shape[-1] - inputs.shape[-1]), "mode": "greedy"})
    return out


# ---------------------------------------------------------------- reporting

def score(rows: list[dict], outputs: list[dict]) -> list[dict]:
    by_id = {o["id"]: o for o in outputs}
    scored = []
    for row in rows:
        o = by_id.get(row["id"], {})
        s = score_one(o.get("analysis"), row["expected"], latency_s=o.get("latency_s"), tokens=o.get("tokens"), error=o.get("error"))
        s.update({"id": row["id"], "group": row["group"], "mode": o.get("mode")})
        scored.append(s)
    return scored


def _fmt(value, pct=False) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.0f}%" if pct else f"{value:.2f}"


def print_report(label: str, dataset: str, agg: dict, failures: list[str] | None) -> None:
    table = Table(title=f"{label} on {dataset} ({agg['count']} entries)", border_style="bright_blue")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold")
    pct = ("schema_valid_rate", "rules_ok_rate", "enum_valid_rate", "distress_recall", "distress_precision", "distress_accuracy", "rumination_accuracy",
           "top_topic_accuracy", "topics_in_vocab_rate", "stim_category_accuracy", "fog_accuracy", "short_form_accuracy", "minutes_in_range_rate",
           "builders_recall", "decision_accuracy", "grammar_in_range_rate", "grammar_fixes_enough_rate", "mood_in_range_rate")
    for key in ("schema_valid_rate", "rules_ok_rate", "distress_recall", "distress_precision", "mood_mae", "mood_in_range_rate", "rumination_accuracy",
                "top_topic_accuracy", "topics_in_vocab_rate", "stimulation_load_mae", "stim_category_accuracy", "brain_rot_load_mae", "fog_accuracy",
                "short_form_accuracy", "minutes_in_range_rate", "builders_recall", "decision_accuracy", "grammar_in_range_rate", "grammar_fixes_enough_rate",
                "avg_latency_s", "avg_tokens", "failures"):
        table.add_row(key, _fmt(agg.get(key), pct=key in pct) if key not in ("failures",) else str(agg.get(key)))
    table.add_row("distress confusion", json.dumps(agg["distress_confusion"]))
    console.print(table)
    if failures is not None:
        hard = [f for f in failures if not f.endswith("no data")]
        if hard:
            console.print("[bold red]Gate failed:[/bold red] " + "; ".join(hard))
        else:
            console.print("[bold green]Gate passed.[/bold green]" + (f" (no data for: {', '.join(f.split(':')[0] for f in failures)})" if failures else ""))


def save_results(record: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if RESULTS_PATH.exists():
        try:
            existing = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        except ValueError:
            existing = []
    existing.append(record)
    RESULTS_PATH.write_text(json.dumps(existing, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a model on the analysis task with the production prompt")
    parser.add_argument("--backend", choices=("endpoint", "unsloth"), default="endpoint")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env", default="LOCAL_LLM_API_KEY", help="env var holding the key for --base-url")
    parser.add_argument("--model", default="smart-diary-slm", help="served model name, or the family (qwen|llama|phi) for --backend unsloth")
    parser.add_argument("--adapter", help="unsloth: path to a LoRA adapter (default output/lora_<family>)")
    parser.add_argument("--base", action="store_true", help="unsloth: evaluate the zero-shot base model")
    parser.add_argument("--dataset", choices=("golden", "test", "both"), default="golden")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--label", default=None)
    parser.add_argument("--gate", action="store_true", help="exit 1 when thresholds are missed")
    parser.add_argument("--thresholds", type=Path, default=None)
    parser.add_argument("--dump", type=Path, default=None, help="write every analysis and score to this JSONL")
    args = parser.parse_args(argv)

    datasets = ["golden", "test"] if args.dataset == "both" else [args.dataset]
    label = args.label or (f"{args.model}@{args.base_url}" if args.backend == "endpoint" else f"{args.model}{'-base' if args.base else '-ft'}")
    thresholds = load_thresholds(args.thresholds)
    exit_code = 0
    for name in datasets:
        rows = load_golden() if name == "golden" else load_test()
        rows = select(rows, args.limit, args.seed)
        if args.backend == "endpoint":
            if not args.base_url:
                raise SystemExit("--base-url is required for --backend endpoint")
            key = os.getenv(args.api_key_env) or "empty"
            ep = Endpoint(base_url=args.base_url.rstrip("/"), api_key=key, model=args.model, name="eval")
            outputs = asyncio.run(run_endpoint(rows, ep, args.concurrency))
        else:
            outputs = run_unsloth(rows, args.model, args.adapter, args.base)
        scored = score(rows, outputs)
        agg = aggregate(scored)
        passed, failures = gate(agg, thresholds) if args.gate else (True, None)
        print_report(label, name, agg, failures)
        record = {
            "label": label, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "backend": args.backend, "model": args.model,
            "base_url": args.base_url, "dataset": name, "count": len(rows), "prompt_version": PROMPT_VERSION, "metrics": agg,
            "gate": {"passed": passed, "failures": failures} if args.gate else None,
            "worst": [s for s in scored if not s.get("schema_valid") or s.get("distress_correct") is False][:20],
        }
        save_results(record)
        if args.dump:
            args.dump.parent.mkdir(parents=True, exist_ok=True)
            with open(args.dump, "a", encoding="utf-8") as f:
                by_id = {o["id"]: o for o in outputs}
                for s in scored:
                    f.write(json.dumps({"label": label, "dataset": name, **s, "analysis": by_id.get(s["id"], {}).get("analysis")}, ensure_ascii=False) + "\n")
        if args.gate and not passed:
            exit_code = 1
    console.print(f"results appended to {RESULTS_PATH}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
