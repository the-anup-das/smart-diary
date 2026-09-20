"""
Runner for the synthetic-data pipeline.

Spawns sample pipelines up to the AIMD concurrency limit, writes every approved sample to
output/dataset_raw.jsonl with its meta (profile, models, judge scores, prompt version), logs
telemetry rows with a fixed set of keys, and keeps the lessons store that steers later samples.
Splits are built afterwards by scripts/build_splits.py.

    python -m data_pipeline.run --count 5 --dry-run
    python -m data_pipeline.run --count 200 --concurrency 3      # adds 200 approved samples to the dataset
    python -m data_pipeline.run --total 1500 --concurrency 3     # keeps going until the dataset holds 1500

Every run appends to output/dataset_raw.jsonl; nothing is overwritten. Split files are rebuilt
from it by scripts/build_splits.py.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import hashlib
import json
import os
import random
import sys
import time
import uuid
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text

from data_pipeline import config
from data_pipeline.agents.diversity_controller import generate_diversity_profile
from data_pipeline.contracts import PROMPT_VERSION, FeedbackReportSchema
from data_pipeline.endpoints import EndpointPool
from data_pipeline.graph import PipelineRuntime, build_pipeline_graph
from data_pipeline.lessons import LessonsStore
from data_pipeline.reputation import JudgeReputation
from data_pipeline.status import TRACKER, fmt_seconds
from data_pipeline.status import TRACKER, fmt_seconds

def _utf8_console() -> Console:
    """Windows consoles default to a legacy code page; the entries and analyses carry real punctuation."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    return Console()


console = _utf8_console()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def count_existing_samples(path: Path | None = None) -> int:
    path = path or config.RAW_DATASET_PATH
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def format_record(entry: str, analysis: dict, profile: dict, *, models: dict, judge_verdict: dict, judge2_verdict: dict | None = None, judge_retries: int = 0, editor_iterations: int = 0, entry_repairs: int = 0, judge2_passed: bool | None = None) -> dict:
    """The raw dataset row. `analysis` must already validate against the contract."""
    edge = profile.get("edge_case") or {}
    scores = {k: judge_verdict.get(k) for k in ("grounding", "safety", "cbt_quality", "schema_semantics", "persona_adherence", "overall")}
    return {
        "id": uuid.uuid4().hex,
        "entry": entry,
        "analysis": analysis,
        "meta": {
            "profile": {
                "persona": profile["persona"], "emotion": profile["emotion"], "topic": profile["topic"],
                "style": profile["style"], "length": profile["length"]["category"],
            },
            "edge_case": edge.get("type"),
            "custom_persona": profile.get("custom_persona_prompt"),
            "writer_model": models.get("writer"), "reviewer_model": models.get("reviewer"),
            "teacher_model": models.get("teacher"), "judge_model": models.get("judge"), "judge_host": models.get("judge_host"),
            "judge2_model": models.get("judge2"),
            "prompt_version": PROMPT_VERSION,
            "judge_scores": scores,
            "judge2_scores": {k: judge2_verdict.get(k) for k in ("overall", "safety")} if judge2_verdict and "overall" in judge2_verdict else None,
            "judge_retries": judge_retries,
            "entry_repairs": entry_repairs,
            "editor_iterations": editor_iterations,
            "judge2_passed": judge2_passed,
            "entry_sha256": hashlib.sha256(entry.strip().encode("utf-8")).hexdigest(),
            "created_at": _now(),
        },
    }


def build_runtime(*, lessons_enabled: bool = True, judge2_enabled: bool = True, seed: int | None = None) -> PipelineRuntime:
    judges = config.judge_endpoints()
    if not judges:
        raise SystemExit("No judge endpoint is configured. Set JUDGE_ENDPOINTS, or LMSTUDIO_MODEL and a GOOGLE_API_KEY.")
    judge2 = config.judge2_endpoint() if judge2_enabled else None
    return PipelineRuntime(
        analyzer=config.role_endpoint("analyzer", config.ANALYZER_MODEL),
        editor=config.role_endpoint("editor", config.EDITOR_MODEL),
        reviewer=config.role_endpoint("reviewer", config.REVIEWER_MODEL),
        writers=[config.role_endpoint("writer", m) for m in config.WRITER_MODELS],
        judge_pool=EndpointPool(judges, cooldown_s=config.ENDPOINT_COOLDOWN_S),
        judge2=judge2,
        judge2_pool=EndpointPool([judge2], cooldown_s=config.ENDPOINT_COOLDOWN_S) if judge2 else None,
        judge2_enabled=judge2_enabled,   # an explicit second judge, or another host from the judge list
        lessons=LessonsStore(config.LESSONS_PATH, max_items=config.LESSONS_MAX, enabled=lessons_enabled),
        reputation=JudgeReputation(
            config.JUDGE_REPUTATION_PATH, agree=config.JUDGE_REP_AGREE, overturned_pass=config.JUDGE_REP_OVERTURNED_PASS,
            overturned_fail=config.JUDGE_REP_OVERTURNED_FAIL, strict_below=config.JUDGE_REP_STRICT_BELOW,
        ),
        rng=random.Random((seed if seed is not None else config.SEED) + 7),
        disagreements_path=config.JUDGE_DISAGREEMENTS_PATH,
    )


def initial_state(profile: dict, batch_index: int) -> dict:
    return {
        "profile": profile, "batch_index": batch_index, "entry": "", "editor_iteration": 0, "review": {},
        "analysis_json": {}, "analysis_error": None, "schema_retry_count": 0,
        "judge_verdict": {}, "judge_retry_count": 0, "entry_repair_count": 0, "needs_judge2": False, "judge2_verdict": {}, "judge2_passed": None,
        "final_status": "PENDING", "discard_reason": None, "total_tokens": 0, "total_cost": 0.0, "calls": 0,
    }


def telemetry_row(state: dict, final_status: str, reason: str | None) -> dict:
    """Every row carries the same keys, so the dashboard never meets a missing column."""
    verdict = state.get("judge_verdict") or {}
    return {
        "timestamp": _now(),
        "status": final_status,
        "editor_iterations": state.get("editor_iteration", 0),
        "entry_repairs": state.get("entry_repair_count", 0),
        "schema_retries": state.get("schema_retry_count", 0),
        "judge_retries": state.get("judge_retry_count", 0),
        "judge_overall": verdict.get("overall"),
        "judge_safety": verdict.get("safety"),
        "judge_model": state.get("judge_model"),
        "judge_host": state.get("judge_host"),
        "judge_label": state.get("judge_label"),
        "first_judge_passed": state.get("first_judge_passed"),
        "judge2_model": state.get("judge2_model"),
        "judge2_host": state.get("judge2_host"),
        "judge2_passed": state.get("judge2_passed"),
        "judge2_overall": (state.get("judge2_verdict") or {}).get("overall"),
        "writer_model": state.get("writer_model"),
        "reviewer_model": state.get("reviewer_model"),
        "reviewer_approved_first": (state.get("editor_iteration", 0) == 0 and state.get("entry_repair_count", 0) == 0) if state.get("entry") else None,
        "edge_case": (state.get("profile") or {}).get("edge_case", {}).get("type") if (state.get("profile") or {}).get("edge_case") else None,
        "tokens": state.get("total_tokens", 0),
        "calls": state.get("calls", 0),
        "cost": state.get("total_cost", 0.0),
        "discard_reason": reason if final_status != "PASSED" else None,
        "error": state.get("crash_error"),
    }


class PipelineManager:
    def __init__(self, target_count: int, runtime: PipelineRuntime, graph, *, seed: int, force_edge_cases: bool = False,
                 edge_case_rate: float | None = None, persona_rate: float | None = None, dry_run: bool = False, raw_path: Path | None = None):
        self.target_count = target_count   # approved samples to add in this run
        self.runtime = runtime
        self.graph = graph
        self.seed = seed
        self.force_edge_cases = force_edge_cases
        self.edge_case_rate = config.EDGE_CASE_RATE if edge_case_rate is None else edge_case_rate
        self.persona_rate = config.PERSONA_PROMPT_RATE if persona_rate is None else persona_rate
        self.dry_run = dry_run
        self.raw_path = raw_path or config.RAW_DATASET_PATH
        self.total_approved = count_existing_samples(self.raw_path)
        self.start_offset = self.total_approved
        self.session_approved = 0
        self.total_attempts = 0
        self.discard_count = 0
        self.crash_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.status_counts: dict[str, int] = {}
        self.judge_hosts: dict[str, int] = {}
        self.consecutive_crashes = 0
        self.aborted: str | None = None
        self.lock = asyncio.Lock()
        self.file_lock = asyncio.Lock()

    def _profile_for(self, attempt: int) -> dict:
        rng = random.Random(self.seed * 1_000_003 + self.start_offset * 7919 + attempt)
        return generate_diversity_profile(rng, force_edge_case=self.force_edge_cases, edge_case_rate=self.edge_case_rate, persona_rate=self.persona_rate)

    async def run_single_pipeline(self, board: "RunBoard | None" = None) -> dict | None:
        async with self.lock:
            self.total_attempts += 1
            attempt = self.total_attempts
        profile = self._profile_for(attempt)
        state = initial_state(profile, batch_index=(self.start_offset + attempt - 1) // config.WRITER_BATCH_SIZE)
        TRACKER.start(attempt)
        tag = f"[dim]#{attempt}[/dim]"
        if board:
            board.log(f"{tag} new sample: {describe_profile(profile)}")

        try:
            try:
                async for output in self.graph.astream(state, {"recursion_limit": 80}):
                    for node, node_output in output.items():
                        if isinstance(node_output, dict):
                            if board:
                                event = stage_event(node, node_output, state)
                                if event:
                                    board.log(f"{tag} {event}")
                            state.update(node_output)
            except Exception as e:  # noqa: BLE001
                state["crash_error"] = f"{type(e).__name__}: {e}"[:300]
                async with self.lock:
                    self.crash_count += 1
                    self.discard_count += 1
                    self.consecutive_crashes += 1
                    self.status_counts["CRASH"] = self.status_counts.get("CRASH", 0) + 1
                    if self.consecutive_crashes >= config.MAX_CONSECUTIVE_CRASHES and not self.aborted:
                        self.aborted = f"{self.consecutive_crashes} pipelines crashed in a row; the endpoint looks down or overloaded"
                if board:
                    board.log(f"{tag} [bold red]x pipeline crash:[/bold red] {escape(state['crash_error'])}")
                await self._write_outputs(state, None, "CRASH", state["crash_error"])
                return None

            final_status = state.get("final_status", "PENDING")
            if final_status not in ("PASSED",) and not final_status.startswith("FAILED"):
                final_status = "FAILED_UNKNOWN"
            reason = state.get("discard_reason")
            record = None
            if final_status == "PASSED":
                record = format_record(
                    state["entry"], state["analysis_json"], profile,
                    models={
                        "writer": state.get("writer_model"), "reviewer": state.get("reviewer_model"), "teacher": self.runtime.analyzer.model,
                        "judge": state.get("judge_model"), "judge_host": state.get("judge_host"), "judge2": state.get("judge2_model") if state.get("judge2_verdict") else None,
                    },
                    judge_verdict=state.get("judge_verdict") or {}, judge2_verdict=state.get("judge2_verdict") or None,
                    judge_retries=state.get("judge_retry_count", 0), editor_iterations=state.get("editor_iteration", 0),
                    entry_repairs=state.get("entry_repair_count", 0), judge2_passed=state.get("judge2_passed"),
                )

            async with self.lock:
                self.consecutive_crashes = 0
                self.total_tokens += state.get("total_tokens", 0)
                self.total_cost += state.get("total_cost", 0.0)
                self.status_counts[final_status] = self.status_counts.get(final_status, 0) + 1
                if state.get("judge_host"):
                    self.judge_hosts[state["judge_host"]] = self.judge_hosts.get(state["judge_host"], 0) + 1
                if record is not None:
                    # Every approved sample is written, even past the target: the spawn loop is what stops.
                    self.total_approved += 1
                    self.session_approved += 1
                    if board:
                        analysis = state["analysis_json"]
                        badge = "[bold red]CRISIS[/bold red]" if analysis.get("distressFlag") else "[dim green]safe[/dim green]"
                        verdict = state.get("judge_verdict") or {}
                        board.log(
                            f"{tag} [bold green]+ Sample #{self.total_approved:04d} approved[/bold green] | mood {analysis.get('moodScore')}/10 ({escape(str(analysis.get('sentiment')))}) "
                            f"| {len(state['entry'].split())} words | {badge} | judge {verdict.get('overall')}/10 via {state.get('judge_host')}"
                            f"{' | label repaired' if state.get('judge_retry_count') else ''}{' | entry rewritten' if state.get('entry_repair_count') else ''}"
                            f"{' | 2nd judge ' + str(state.get('judge2_verdict', {}).get('overall')) + '/10 via ' + str(state.get('judge2_host')) if state.get('judge2_passed') is not None else ''}"
                            f" | {fmt_seconds(TRACKER.samples[attempt].elapsed()) if attempt in TRACKER.samples else ''}"
                        )
                        board.advance()
                else:
                    self.discard_count += 1
                    if board:
                        board.log(f"{tag} [bold red]- {final_status}[/bold red] [dim]| {escape(str(reason)[:140])}[/dim]")
                if board:
                    pass_rate = (self.session_approved / self.total_attempts) * 100
                    board.stats(f"[yellow]pass {pass_rate:.0f}%[/yellow] | [magenta]{self.total_tokens / 1000:.0f}k tokens[/magenta] | [cyan]${self.total_cost:.2f}[/cyan]")

            await self._write_outputs(state, record, final_status, reason)
            return record
        finally:
            TRACKER.finish(attempt)

    async def _write_outputs(self, state: dict, record: dict | None, final_status: str, reason: str | None) -> None:
        if self.dry_run:
            return
        async with self.file_lock:
            config.ensure_dirs()
            with open(config.TELEMETRY_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(telemetry_row(state, final_status, reason), ensure_ascii=False) + "\n")
            if final_status != "PASSED":
                with open(config.REJECTIONS_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"[{_now()}] {final_status}\nReason: {reason}\n" + "-" * 40 + "\n")
            if record is not None:
                self.raw_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.raw_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")


def describe_profile(profile: dict) -> str:
    """One line on what the sample is meant to be: who writes, how they feel, about what, in which style."""
    def short(value, limit: int = 42) -> str:
        text = str(value or "").split(" (")[0].strip()
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

    persona = profile.get("persona") or {}
    who = f"{short(persona.get('role'))}, {short(persona.get('age_group'))}" if isinstance(persona, dict) else short(persona)
    parts = [who, short(profile.get("emotion")), short(profile.get("topic")), short(profile.get("style"), 30), short((profile.get("length") or {}).get("category"))]
    text = escape(" / ".join(p for p in parts if p))
    edge = (profile.get("edge_case") or {}).get("type")
    if edge:
        text += f" / edge case [bold]{escape(str(edge))}[/bold]"
    if profile.get("custom_persona_prompt"):
        text += " / custom instructions"
    return text


def stage_event(node: str, out: dict, state: dict) -> str | None:
    """One line for a decision the sample just passed through; None for steps with nothing to say.
    `state` is the state before this node's update, so rounds are numbered as the agent saw them."""
    clip = lambda s, n=110: escape(" ".join(str(s or "").split())[:n])  # noqa: E731
    if node == "writer":
        return f"writer drafted {len(out.get('entry', '').split())} words"
    if node == "editor":
        return f"editor revised the entry, now {len(out.get('entry', '').split())} words"
    if node == "reviewer":
        review = out.get("review") or {}
        rounds = state.get("editor_iteration", 0)
        if review.get("approved"):
            return f"[magenta]reviewer approved[/magenta] on round {rounds + 1}"
        nxt = "to the editor" if rounds < config.MAX_EDITOR_ITERATIONS else "no rounds left, discarding"
        return f"[magenta]reviewer wants changes[/magenta] on round {rounds + 1}, {nxt}: {clip(review.get('critique'))}"
    if node == "analyzer":
        if out.get("analysis_error"):
            return f"[blue]analyzer[/blue] returned no usable JSON: {clip(out['analysis_error'])}"
        return "[blue]analyzer[/blue] produced labels"
    if node == "schema_validator":
        err = out.get("analysis_error")
        if not err:
            return "validator: schema and business rules ok"
        retries = out.get("schema_retry_count", 0)
        nxt = f"back to the analyzer (retry {retries})" if retries < config.MAX_SCHEMA_RETRY else "no retries left, discarding"
        return f"validator rejected the labels, {nxt}: {clip(err)}"
    if node == "judge":
        v = out.get("judge_verdict") or {}
        head = f"[green]judge[/green] {out.get('judge_host')}: overall {v.get('overall')}/10, safety {v.get('safety')}/10"
        if v.get("hard_fail"):
            head += f", hard fail ({clip(v.get('hard_fail_reason'), 60)})"
        status = out.get("final_status")
        if status == "PASSED":
            return head + " -> [bold green]pass[/bold green]"
        if status == "REPAIRING_ENTRY":
            return head + f" -> entry back to the editor: {clip(v.get('entry_notes'))}"
        if status == "REPAIRING":
            return head + f" -> labels back to the analyzer: {clip(v.get('label_notes') or out.get('analysis_error'))}"
        return head + f" -> [red]discard[/red]: {clip(out.get('discard_reason'))}"
    if node == "judge2":
        v = out.get("judge2_verdict") or {}
        if out.get("judge2_passed") is None:
            return f"[bright_green]second judge[/bright_green] skipped: {clip(v.get('skipped', 'no other host available'))}" if v else None
        head = f"[bright_green]second judge[/bright_green] {out.get('judge2_host')}: overall {v.get('overall')}/10"
        if out.get("judge2_passed") == state.get("first_judge_passed"):
            return head + " -> agrees with the first judge"
        if state.get("first_judge_passed"):
            return head + f" -> [red]overturned the pass[/red]: {clip(out.get('discard_reason'))}"
        return head + " -> would have passed it; the first judge's fail stands and its reputation drops"
    return None


class RunBoard:
    """What the terminal shows during a run: the progress bar, counters, one row per sample in flight
    with its current agent and how long it has been there. Event lines print above the board."""

    STAGE_STYLES = {
        "queued": "dim", "writer": "cyan", "reviewer": "magenta", "editor": "yellow", "analyzer": "blue",
        "validator": "white", "judge": "green", "second judge": "bright_green",
    }

    def __init__(self, manager: PipelineManager, *, to_add: int, existing: int, console: Console):
        self.manager = manager
        self.console = console
        self.progress = Progress(
            SpinnerColumn(spinner_name="dots", style="bright_cyan"), TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(bar_width=30), MofNCompleteColumn(), TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(), TimeRemainingColumn(), TextColumn("{task.fields[stats]}"), console=console,
        )
        self.task_id = self.progress.add_task(f"Adding {to_add} (dataset has {existing})", total=to_add, completed=0, stats="")
        self.live = Live(self, console=console, refresh_per_second=4)

    def __enter__(self) -> "RunBoard":
        TRACKER.note_listeners.append(self._on_note)
        self.live.start()
        return self

    def __exit__(self, *exc) -> None:
        self.live.stop()
        if self._on_note in TRACKER.note_listeners:
            TRACKER.note_listeners.remove(self._on_note)

    def _on_note(self, attempt: int, text: str) -> None:
        self.log(f"[dim]#{attempt} {escape(text)}[/dim]")

    def log(self, text: str) -> None:
        self.console.print(text)

    def advance(self) -> None:
        self.progress.advance(self.task_id)

    def stats(self, text: str) -> None:
        self.progress.update(self.task_id, stats=text)

    def counters(self) -> Text:
        m = self.manager
        outcomes = ", ".join(f"{k} {v}" for k, v in sorted(m.status_counts.items()) if k != "PASSED") or "none"
        pass_rate = (m.session_approved / m.total_attempts * 100) if m.total_attempts else 0.0
        return Text.from_markup(
            f"[bold]In flight:[/bold] {len(TRACKER)} (limit {config.CONCURRENCY_CONTROLLER.current})   "
            f"[bold]Started:[/bold] {m.total_attempts}   [bold]Approved:[/bold] {m.session_approved}/{m.target_count} (dataset {m.total_approved})   "
            f"[bold]Discarded:[/bold] {m.discard_count} ({outcomes})   [bold]Pass rate:[/bold] {pass_rate:.0f}%   "
            f"[bold]Tokens:[/bold] {m.total_tokens / 1000:.0f}k   [bold]Judge hosts:[/bold] "
            + (", ".join(f"{k} {v}" for k, v in sorted(m.judge_hosts.items())) or "-")
        )

    def table(self) -> Table:
        table = Table(box=box.SIMPLE_HEAD, show_edge=False, pad_edge=False, expand=False)
        table.add_column("#", justify="right", style="bold")
        table.add_column("agent")
        table.add_column("doing", no_wrap=True, overflow="ellipsis", max_width=72)
        table.add_column("on this step", justify="right")
        table.add_column("sample total", justify="right")
        table.add_column("note", style="dim", no_wrap=True, overflow="ellipsis", max_width=70)
        now = time.monotonic()
        rows = TRACKER.rows()
        for s in rows:
            style = self.STAGE_STYLES.get(s.stage, "white")
            table.add_row(str(s.attempt), f"[{style}]{s.stage}[/{style}]", escape(s.detail), fmt_seconds(s.stage_elapsed(now)), fmt_seconds(s.elapsed(now)), escape(s.note))
        if not rows:
            table.add_row("-", "[dim]nothing in flight[/dim]", "", "", "", "")
        return table

    def __rich__(self):
        return Group(self.progress, self.counters(), self.table())


def _print_banner(args, manager: PipelineManager, runtime: PipelineRuntime, concurrency: int) -> None:
    judges = ", ".join(ep.label for ep in runtime.judge_pool.endpoints)
    reputation_line = ", ".join(f"{k}: {v['score']}" for k, v in runtime.reputation.snapshot().items()) or "no history yet"
    if runtime.judge2 is not None:
        second = runtime.judge2.label
    elif runtime.judge2_enabled and len(runtime.judge_pool) > 1:
        second = "another host from the judge list"
    else:
        second = "off"
    lines = [
        f"[bold cyan]Adding this run:[/bold cyan] {manager.target_count}   [bold cyan]Already in dataset:[/bold cyan] {manager.total_approved}",
        f"[bold cyan]Writers:[/bold cyan] {', '.join(ep.label for ep in runtime.writers)}",
        f"[bold cyan]Reviewer:[/bold cyan] {runtime.reviewer.label}   [bold cyan]Editor:[/bold cyan] {runtime.editor.label}",
        f"[bold cyan]Analyzer (teacher):[/bold cyan] {runtime.analyzer.label}",
        f"[bold cyan]Judges:[/bold cyan] {judges}",
        f"[bold cyan]Second judge:[/bold cyan] {second}",
        f"[bold cyan]Judge reputation:[/bold cyan] {reputation_line}",
        f"[bold cyan]Lessons:[/bold cyan] {'on' if runtime.lessons.enabled else 'off'} ({runtime.lessons.counts()})   "
        f"[bold cyan]Seed:[/bold cyan] {args.seed}   [bold cyan]Concurrency:[/bold cyan] {concurrency}{' (auto)' if args.concurrency == 'auto' else ''}",
        f"[bold cyan]Prompt version:[/bold cyan] {PROMPT_VERSION}",
    ]
    console.print(Panel("\n".join(lines), title="[bold green]Distillation run[/bold green]", border_style="bright_blue"))


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Generate approved (entry, analysis) samples with the multi-agent pipeline")
    parser.add_argument("--count", type=int, default=10, help="approved samples to add in this run (the dataset keeps growing)")
    parser.add_argument("--total", type=int, default=None, help="instead of --count: stop when dataset_raw.jsonl holds this many samples")
    parser.add_argument("--concurrency", type=str, default="5", help="parallel pipelines, an integer or 'auto'")
    parser.add_argument("--force-edge-cases", action="store_true", help="every sample gets an edge case")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--edge-rate", type=float, default=None, help=f"share of samples with an edge case (default {config.EDGE_CASE_RATE})")
    parser.add_argument("--persona-rate", type=float, default=None, help=f"share of samples with custom instructions (default {config.PERSONA_PROMPT_RATE})")
    parser.add_argument("--no-lessons", action="store_true", help="disable the rejection-lessons loop (for A/B comparison)")
    parser.add_argument("--no-judge2", action="store_true", help="disable the second-opinion judge")
    parser.add_argument("--dry-run", action="store_true", help="run one sample, print the record, write nothing")
    args = parser.parse_args()

    config.require_api_key()
    config.ensure_dirs()
    runtime = build_runtime(lessons_enabled=not args.no_lessons, judge2_enabled=not args.no_judge2, seed=args.seed)
    graph = build_pipeline_graph(runtime)

    if args.concurrency.lower() == "auto":
        local = any(h in config.LLM_BASE_URL for h in ("localhost", "127.0.0.1"))
        concurrency = 4 if local else min(15, (os.cpu_count() or 4) * 2)
    else:
        concurrency = max(1, int(args.concurrency))

    existing = count_existing_samples()
    to_add = max(0, args.total - existing) if args.total is not None else args.count
    manager = PipelineManager(
        to_add, runtime, graph, seed=args.seed, force_edge_cases=args.force_edge_cases,
        edge_case_rate=args.edge_rate, persona_rate=args.persona_rate, dry_run=args.dry_run,
    )
    _print_banner(args, manager, runtime, concurrency)

    if args.dry_run:
        with RunBoard(manager, to_add=1, existing=existing, console=console) as board:
            record = await manager.run_single_pipeline(board)
        if record is None:
            console.print("[bold red]The sample did not pass; see the reasons above.[/bold red]")
            return
        FeedbackReportSchema.model_validate(record["analysis"])
        console.print(Panel(record["entry"], title="entry", border_style="green"))
        console.print(Panel(json.dumps(record["analysis"], ensure_ascii=False, indent=1), title="analysis (validates against the contract)", border_style="green"))
        console.print(Panel(json.dumps(record["meta"], ensure_ascii=False, indent=1), title="meta", border_style="cyan"))
        console.print("[bold green]Dry run complete; nothing was written.[/bold green]")
        return

    if to_add <= 0:
        console.print(f"[bold green]The dataset already holds {existing} samples, at or above --total {args.total}. Nothing to do.[/bold green]")
        return

    config.CONCURRENCY_CONTROLLER.setup(concurrency)
    with RunBoard(manager, to_add=to_add, existing=existing, console=console) as board:
        board.log(
            "[dim]Each sample runs writer -> reviewer (-> editor, up to 3 rounds) -> analyzer -> validator -> judge -> second judge. "
            "The table shows where every sample is right now and how long it has been there; the lines above it are the agents' decisions.[/dim]"
        )
        pending: set[asyncio.Task] = set()
        while manager.session_approved < to_add and not manager.aborted:
            limit = config.CONCURRENCY_CONTROLLER.current
            while len(pending) < limit and manager.session_approved + len(pending) < to_add:
                pending.add(asyncio.create_task(manager.run_single_pipeline(board)))
            if not pending:
                break
            _done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=1.0)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    if manager.aborted:
        console.print(f"[bold red]Run stopped: {manager.aborted}. Fix the endpoint and run the same command to resume.[/bold red]")
    table = Table(title="[bold green]Session summary[/bold green]", border_style="bright_blue")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold")
    table.add_row("Approved, all time", str(manager.total_approved))
    table.add_row("Approved this session", str(manager.session_approved))
    table.add_row("Discarded this session", str(manager.discard_count))
    table.add_row("Outcomes", ", ".join(f"{k}: {v}" for k, v in sorted(manager.status_counts.items())))
    table.add_row("Judge hosts", ", ".join(f"{k}: {v}" for k, v in sorted(manager.judge_hosts.items())) or "-")
    table.add_row("Pass rate", f"{manager.session_approved / max(1, manager.total_attempts):.1%}")
    table.add_row("Tokens", f"{manager.total_tokens:,}")
    table.add_row("Cost", f"${manager.total_cost:.2f}")
    table.add_row("Lessons stored", str(runtime.lessons.counts()))
    table.add_row("Judge reputation", ", ".join(f"{k}: {v['score']} ({v['agreed']} agreed, {v['overturned_pass']} passes and {v['overturned_fail']} fails overturned)" for k, v in runtime.reputation.snapshot().items()) or "-")
    console.print("\n", table)
    console.print("Next: [bold]python -m data_pipeline.scripts.build_splits[/bold] to dedup and split.")


if __name__ == "__main__":
    asyncio.run(amain())
