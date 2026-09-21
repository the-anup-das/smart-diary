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
from data_pipeline.agents.diversity_controller import EDGE_CASE_TYPES, generate_diversity_profile
from data_pipeline.agents.llm_client import LLMCallError, acall_llm
from data_pipeline.contracts import PROMPT_VERSION, FeedbackReportSchema
from data_pipeline.endpoints import Endpoint, EndpointPool
from data_pipeline.graph import PipelineRuntime, build_pipeline_graph
from data_pipeline.keys import KeyReader
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
                 edge_case_rate: float | None = None, persona_rate: float | None = None, dry_run: bool = False, raw_path: Path | None = None,
                 edge_case_types: list[str] | None = None):
        self.target_count = target_count   # approved samples to add in this run
        self.runtime = runtime
        self.graph = graph
        self.seed = seed
        self.force_edge_cases = force_edge_cases
        self.edge_case_rate = config.EDGE_CASE_RATE if edge_case_rate is None else edge_case_rate
        self.persona_rate = config.PERSONA_PROMPT_RATE if persona_rate is None else persona_rate
        self.edge_case_types = edge_case_types
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
        return generate_diversity_profile(rng, force_edge_case=self.force_edge_cases, edge_case_rate=self.edge_case_rate,
                                          persona_rate=self.persona_rate, edge_case_types=self.edge_case_types)

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
                    fatal = fatal_reason(e)
                    if fatal and not self.aborted:
                        self.aborted = fatal
                    elif self.consecutive_crashes >= config.MAX_CONSECUTIVE_CRASHES and not self.aborted:
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


PERMANENT_STATUSES = (401, 402, 403, 404)   # a key, a bill or a model id: retrying cannot help


def fatal_reason(error: Exception) -> str | None:
    """A reason to stop the whole run after one crash: the host rejects the model or the key, so every sample would fail the same way."""
    if isinstance(error, LLMCallError) and not error.retryable and error.status in PERMANENT_STATUSES:
        ep = error.endpoint
        where = f"{ep.model} on {ep.host}" if ep else "an endpoint"
        what = {404: "does not serve this model", 402: "wants payment for it"}.get(error.status, "rejects the API key")
        return f"{where}: the host {what} ({str(error)[:160]}). Check the model id and the key, then run the same command again"
    return None


async def preflight(runtime: PipelineRuntime, console: Console) -> bool:
    """One-token request to every model a run depends on. A host can list a model and still not serve it."""
    roles: list[tuple[str, Endpoint, bool]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(role: str, ep: Endpoint | None, required: bool) -> None:
        if ep is None or (ep.host, ep.model, ep.api_key) in seen:
            return
        seen.add((ep.host, ep.model, ep.api_key))
        roles.append((role, ep, required))

    for ep in runtime.writers:
        add("writer", ep, True)
    add("editor", runtime.editor, True)
    add("reviewer", runtime.reviewer, True)
    add("analyzer", runtime.analyzer, True)
    for ep in runtime.judge_pool.endpoints:
        add("judge", ep, False)
    add("second judge", runtime.judge2, False)

    async def probe(role: str, ep: Endpoint):
        started = time.monotonic()
        try:
            await acall_llm(ep, [{"role": "user", "content": "Reply with the single word: ok"}], temperature=0.0, max_tokens=4, max_retries=1)
            return role, ep, None, time.monotonic() - started
        except LLMCallError as e:
            permanent = not e.retryable and e.status in PERMANENT_STATUSES
            if role in ("judge", "second judge"):
                pool = runtime.judge2_pool if role == "second judge" and runtime.judge2_pool else runtime.judge_pool
                pool.penalise(ep, 10 * 3600 if permanent else None)   # sidelined for the run, or for one cooldown
            return role, ep, str(e)[:140], time.monotonic() - started
        except Exception as e:  # noqa: BLE001
            return role, ep, f"{type(e).__name__}: {e}"[:140], time.monotonic() - started

    results = await asyncio.gather(*(probe(role, ep) for role, ep, _ in roles))
    table = Table(title="[bold]Preflight: does every model answer?[/bold]", border_style="bright_blue", box=box.SIMPLE_HEAD)
    table.add_column("role", style="bold cyan")
    table.add_column("model @ host")
    table.add_column("result")
    ok = True
    judges_ok = 0
    for (role, ep, required), (_, _, error, seconds) in zip(roles, results):
        if error is None:
            table.add_row(role, ep.label, f"[green]ok[/green] {seconds:.1f}s")
            judges_ok += role == "judge"
        else:
            table.add_row(role, ep.label, f"[red]{'FAIL' if required else 'unavailable'}[/red] {escape(error)}")
            ok = ok and not required
    if not any(role == "judge" for role, _, _ in roles) or judges_ok == 0:
        ok = False
        table.add_row("judge", "-", "[red]FAIL[/red] no judge host answered")
    for (role, ep, _), (_, _, error, _) in zip(roles, results):
        if role == "second judge" and error and runtime.judge2 is not None:
            runtime.judge2, runtime.judge2_pool = None, None
            table.add_row("second judge", "another host from the judge list", "[yellow]fallback[/yellow] the dedicated second judge is unavailable")
    console.print(table)
    return ok


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

    def __init__(self, manager: PipelineManager, *, to_add: int, existing: int, console: Console, plain: bool = False):
        self.manager = manager
        self.console = console
        # A live region repaints in place: the terminal cannot scroll while it runs and the output
        # is unreadable in a file. --plain, and anything that is not a terminal, prints lines instead.
        self.plain = plain or not console.is_terminal
        self.progress = Progress(
            SpinnerColumn(spinner_name="dots", style="bright_cyan"), TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(bar_width=30), MofNCompleteColumn(), TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(), TimeRemainingColumn(), TextColumn("{task.fields[stats]}"), console=console,
        )
        self.task_id = self.progress.add_task(f"Adding {to_add} (dataset has {existing})", total=to_add, completed=0, stats="")
        self.live = None if self.plain else Live(self, console=console, refresh_per_second=4)
        self.heartbeat_every = float(os.getenv("BOARD_HEARTBEAT_S", "30"))
        self._last_heartbeat = 0.0
        self.scroll = 0                 # first sample row shown; the arrows move this window
        self.follow = True              # stay on the oldest samples unless the reader scrolled away
        self.stop_requested = False     # q: let the samples in flight finish, spawn no more
        self.keys = KeyReader()

    def __enter__(self) -> "RunBoard":
        TRACKER.note_listeners.append(self._on_note)
        if self.live is not None:
            if not self.keys.start():
                self.console.print(
                    f"[dim]Keys are off ({self.keys.reason or 'no terminal'}), so the table cannot be scrolled. "
                    f"Run in a console window, or use --plain for lines the terminal scrolls itself.[/dim]"
                )
            self.live.start()
        return self

    def __exit__(self, *exc) -> None:
        if self.live is not None:
            self.live.stop()
        self.keys.stop()
        if self._on_note in TRACKER.note_listeners:
            TRACKER.note_listeners.remove(self._on_note)

    def handle_keys(self) -> None:
        """Apply whatever was typed since the last tick."""
        for key in self.keys.drain():
            self.handle_key(key)

    def handle_key(self, key: str) -> None:
        page = max(1, self.visible_rows() - 1)
        rows = len(TRACKER)
        if key == "up":
            self.scroll, self.follow = max(0, self.scroll - 1), False
        elif key == "down":
            self.scroll, self.follow = self.scroll + 1, False
        elif key == "pgup":
            self.scroll, self.follow = max(0, self.scroll - page), False
        elif key == "pgdn":
            self.scroll, self.follow = self.scroll + page, False
        elif key == "home":
            self.scroll, self.follow = 0, True
        elif key == "end":
            self.scroll, self.follow = max(0, rows - self.visible_rows()), False
        elif key == "quit" and not self.stop_requested:
            self.stop_requested = True
            self.log("[bold yellow]Finishing the samples in flight, then stopping. Approved samples are already saved.[/bold yellow]")
        self.scroll = max(0, min(self.scroll, max(0, rows - self.visible_rows())))
        if self.scroll == 0:
            self.follow = True

    def heartbeat(self, force: bool = False) -> None:
        """In plain mode, print where every sample is every BOARD_HEARTBEAT_S seconds."""
        if not self.plain:
            return
        now = time.monotonic()
        if not force and now - self._last_heartbeat < self.heartbeat_every:
            return
        self._last_heartbeat = now
        m = self.manager
        rows = sorted(TRACKER.rows(), key=lambda s: s.started)
        where = "; ".join(f"#{s.attempt} {s.stage} {fmt_seconds(s.elapsed(now))}" for s in rows[:8])
        more = f" (+{len(rows) - 8} more)" if len(rows) > 8 else ""
        self.console.print(
            f"[dim]--- approved {m.session_approved}/{m.target_count}, started {m.total_attempts}, discarded {m.discard_count}, "
            f"{m.total_tokens / 1000:.0f}k tokens | {where}{more}[/dim]"
        )

    def _on_note(self, attempt: int, text: str) -> None:
        self.log(f"[dim]#{attempt} {escape(text)}[/dim]")

    def log(self, text: str) -> None:
        self.console.print(text)

    def advance(self) -> None:
        self.progress.advance(self.task_id)

    def stats(self, text: str) -> None:
        self.progress.update(self.task_id, stats=text)
        if self.plain:
            self.heartbeat()

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

    def tally(self) -> Text:
        """Every sample in flight counted by agent, so nothing is hidden when the table does not fit."""
        counts: dict[str, int] = {}
        for s in TRACKER.rows():
            counts[s.stage] = counts.get(s.stage, 0) + 1
        if not counts:
            return Text.from_markup("[dim]Nothing in flight.[/dim]")
        order = list(self.STAGE_STYLES) + [k for k in counts if k not in self.STAGE_STYLES]
        parts = [f"[{self.STAGE_STYLES.get(k, 'white')}]{k} {counts[k]}[/{self.STAGE_STYLES.get(k, 'white')}]" for k in order if counts.get(k)]
        return Text.from_markup("[bold]Now on:[/bold] " + "   ".join(parts))

    def visible_rows(self) -> int:
        """How many sample rows fit under the progress bar, counters, tally, table header and the key hint."""
        height = self.console.size.height or 24
        return max(3, height - 10)

    def hint(self, shown: int, total: int) -> Text:
        if self.plain:
            return Text("")
        window = f"showing {self.scroll + 1} to {self.scroll + shown} of {total}" if total > shown else f"showing all {total}"
        if not self.keys.active:
            return Text.from_markup(f"[dim]{window}   keys are off, so this window cannot be moved[/dim]")
        state = " [yellow]stopping after these[/yellow]" if self.stop_requested else ""
        return Text.from_markup(f"[dim]{window}   up and down scroll, page up and page down jump, home follows the oldest, q finishes and stops[/dim]{state}")

    def table(self, max_rows: int | None = None) -> Table:
        table = Table(box=box.SIMPLE_HEAD, show_edge=False, pad_edge=False, expand=False)
        table.add_column("#", justify="right", style="bold")
        table.add_column("agent")
        table.add_column("doing", no_wrap=True, overflow="ellipsis", max_width=62)
        table.add_column("on this step", justify="right")
        table.add_column("sample total", justify="right")
        table.add_column("note", style="dim", no_wrap=True, overflow="ellipsis", max_width=60)
        now = time.monotonic()
        rows = sorted(TRACKER.rows(), key=lambda s: s.started)   # oldest first: the ones nearest a timeout
        limit = self.visible_rows() if max_rows is None else max_rows
        start = 0 if self.follow else max(0, min(self.scroll, max(0, len(rows) - limit)))
        self.window = (start, min(len(rows), start + limit))
        for s in rows[start:start + limit]:
            style = self.STAGE_STYLES.get(s.stage, "white")
            table.add_row(str(s.attempt), f"[{style}]{s.stage}[/{style}]", escape(s.detail), fmt_seconds(s.stage_elapsed(now)), fmt_seconds(s.elapsed(now)), escape(s.note))
        hidden = len(rows) - (self.window[1] - self.window[0])
        if hidden and not self.keys.active:
            table.add_row("", f"[dim]and {hidden} more, newest first; the tally above counts them all[/dim]", "", "", "", "")
        if not rows:
            table.add_row("-", "[dim]nothing in flight[/dim]", "", "", "", "")
        return table

    def __rich__(self):
        table = self.table()
        start, end = getattr(self, "window", (0, 0))
        return Group(self.progress, self.counters(), self.tally(), table, self.hint(end - start, len(TRACKER)))


def _host_limits_line(runtime: PipelineRuntime) -> str:
    """The cap each server gets, so an overloaded endpoint is visible before the run starts."""
    endpoints = [runtime.analyzer, runtime.editor, runtime.reviewer, *runtime.writers, *runtime.judge_pool.endpoints] + ([runtime.judge2] if runtime.judge2 else [])
    parts: list[str] = []
    seen: set[str] = set()
    for ep in endpoints:
        if ep is None:
            continue
        mode = config.host_model_mode(ep.host)
        if mode == "separate":
            key = f"{ep.host}#{ep.model}"
            label = f"{ep.model} on {ep.host} {config.host_limit(ep.host, ep.model)} at a time"
        else:
            key = ep.host
            label = f"{ep.host} {config.host_limit(ep.host)} at a time" + (" in total, one model at a time" if mode == "shared" else " in total")
        if key not in seen:
            seen.add(key)
            parts.append(label)
    return ", ".join(parts) + (f", {config.HOST_PACING_S:g}s between starts" if config.HOST_PACING_S else "")


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
        f"[bold cyan]Per host:[/bold cyan] {_host_limits_line(runtime)}",
        f"[bold cyan]Edge cases:[/bold cyan] {', '.join(manager.edge_case_types) if manager.edge_case_types else 'all'}"
        f"{' on every sample' if args.force_edge_cases else f', {manager.edge_case_rate:.0%} of samples'}",
        f"[bold cyan]Prompt version:[/bold cyan] {PROMPT_VERSION}",
    ]
    console.print(Panel("\n".join(lines), title="[bold green]Distillation run[/bold green]", border_style="bright_blue"))


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Generate approved (entry, analysis) samples with the multi-agent pipeline")
    parser.add_argument("--count", type=int, default=10, help="approved samples to add in this run (the dataset keeps growing)")
    parser.add_argument("--total", type=int, default=None, help="instead of --count: stop when dataset_raw.jsonl holds this many samples")
    parser.add_argument("--concurrency", type=str, default="5", help="parallel pipelines, an integer or 'auto'")
    parser.add_argument("--force-edge-cases", action="store_true", help="every sample gets an edge case")
    parser.add_argument("--edge-cases", default=None, help=f"draw edge cases only from these types, comma separated: {', '.join(EDGE_CASE_TYPES)}")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--edge-rate", type=float, default=None, help=f"share of samples with an edge case (default {config.EDGE_CASE_RATE})")
    parser.add_argument("--persona-rate", type=float, default=None, help=f"share of samples with custom instructions (default {config.PERSONA_PROMPT_RATE})")
    parser.add_argument("--no-lessons", action="store_true", help="disable the rejection-lessons loop (for A/B comparison)")
    parser.add_argument("--no-judge2", action="store_true", help="disable the second-opinion judge")
    parser.add_argument("--dry-run", action="store_true", help="run one sample, print the record, write nothing")
    parser.add_argument("--plain", action="store_true", help="no live table, just printed lines, so the terminal scrolls and the output can be piped to a file")
    parser.add_argument("--check", action="store_true", help="only run the preflight: one tiny request per model, then exit")
    parser.add_argument("--skip-preflight", action="store_true", help="start without checking that every model answers")
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
    edge_case_types = [t.strip() for t in args.edge_cases.split(",") if t.strip()] if args.edge_cases else None
    unknown = sorted(set(edge_case_types or []) - set(EDGE_CASE_TYPES))
    if unknown:
        raise SystemExit(f"unknown edge case(s) {unknown}; choose from: {', '.join(EDGE_CASE_TYPES)}")
    manager = PipelineManager(
        to_add, runtime, graph, seed=args.seed, force_edge_cases=args.force_edge_cases,
        edge_case_rate=args.edge_rate, persona_rate=args.persona_rate, dry_run=args.dry_run,
        edge_case_types=edge_case_types,
    )
    if args.check or not args.skip_preflight:
        healthy = await preflight(runtime, console)
        if args.check:
            console.print("[bold green]Every required model answers.[/bold green]" if healthy else "[bold red]A required model does not answer; fix the endpoint or the env before running.[/bold red]")
            raise SystemExit(0 if healthy else 1)
        if not healthy:
            console.print("[bold red]Not starting: a required model does not answer. Fix the endpoint or the env, or pass --skip-preflight.[/bold red]")
            raise SystemExit(1)
    _print_banner(args, manager, runtime, concurrency)

    if args.dry_run:
        with RunBoard(manager, to_add=1, existing=existing, console=console, plain=args.plain) as board:
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
    with RunBoard(manager, to_add=to_add, existing=existing, console=console, plain=args.plain) as board:
        board.log(
            "[dim]Each sample runs writer -> reviewer (-> editor, up to 3 rounds) -> analyzer -> validator -> judge -> second judge. "
            "Every line below is an agent's decision"
            + ("; a status line follows every few samples.[/dim]" if board.plain else ", and the table under them shows where each sample is right now.[/dim]")
        )
        pending: set[asyncio.Task] = set()
        while manager.session_approved < to_add and not manager.aborted and not board.stop_requested:
            limit = config.CONCURRENCY_CONTROLLER.current
            while len(pending) < limit and manager.session_approved + len(pending) < to_add:
                pending.add(asyncio.create_task(manager.run_single_pipeline(board)))
            if not pending:
                break
            _done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=0.2)
            board.handle_keys()
            board.heartbeat()
        if pending and board.stop_requested:
            board.log(f"[yellow]Waiting for {len(pending)} samples in flight.[/yellow]")
        while pending:
            _done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=0.2)
            board.handle_keys()

    if board.stop_requested:
        console.print("[bold yellow]Stopped on request; every approved sample is in the dataset. Run the same command to add more.[/bold yellow]")
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
