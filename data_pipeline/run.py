"""Runner entrypoint for the Multi-Agent Synthetic Data Distillation Pipeline (Async)."""

import argparse
import asyncio
import json
import random
import os
import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from data_pipeline import config
from data_pipeline.graph import build_pipeline_graph
from data_pipeline.agents.diversity_controller import generate_diversity_profile

console = Console()

ANALYZER_SYSTEM_PROMPT = """You are an empathetic AI psychologist and writing coach. Parse entries into strict JSON.
Use CBT to reframe negatives. Life areas must sum to 1.0 weight."""


def count_existing_samples() -> int:
    """Calculates how many samples have already been successfully generated across train/test splits."""
    count = 0
    for path in [config.TRAIN_DATASET_PATH, config.TEST_DATASET_PATH]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                count += sum(1 for _ in f)
    return count


def format_sharegpt_record(entry: str, thought_block: str, analysis_json: dict, custom_persona: str = None) -> dict:
    system_content = ANALYZER_SYSTEM_PROMPT
    if custom_persona:
        system_content += f"\n\nUSER'S CUSTOM INSTRUCTIONS: {custom_persona}"
    
    # Inject thought block directly into the JSON to support SGLang Guided JSON Decoding
    analysis_json = {"thought_reasoning": thought_block, **analysis_json}
    assistant_content = json.dumps(analysis_json, ensure_ascii=False)
    
    return {
        "conversations": [
            {"from": "system", "value": system_content},
            {"from": "human", "value": entry},
            {"from": "gpt", "value": assistant_content},
        ]
    }


class PipelineManager:
    def __init__(self, target_count, force_edge_cases):
        self.target_count = target_count
        self.force_edge_cases = force_edge_cases
        self.graph = build_pipeline_graph()
        
        # Resume Capability
        self.total_approved = count_existing_samples()
        self.session_approved = 0
        
        self.total_attempts = 0
        self.discard_count = 0
        self.qe_score = 0
        self.past_rejections = []
        self.total_tokens = 0
        self.total_cost = 0.0
        
        self.lock = asyncio.Lock()
        self.file_lock = asyncio.Lock()

    async def run_single_pipeline(self, progress, task_id):
        profile = generate_diversity_profile(force_edge_case=self.force_edge_cases)

        async with self.lock:
            self.total_attempts += 1
            current_qe_score = self.qe_score
            current_past_rejections = list(self.past_rejections)

        current_state = {
            "profile": profile,
            "entry": "",
            "editor_iteration": 0,
            "review": {},
            "thought_block": "",
            "analysis_json": {},
            "schema_retry_count": 0,
            "schema_error": None,
            "qe_report": {},
            "qe_score": current_qe_score,
            "past_rejections": current_past_rejections,
            "judge_verdict": {},
            "final_status": "PENDING",
            "total_tokens": 0,
            "total_cost": 0.0
        }

        try:
            async for output in self.graph.astream(current_state):
                for node_name, node_output in output.items():
                    current_state.update(node_output)
        except Exception as e:
            async with self.lock:
                self.discard_count += 1
                progress.console.print(f"[bold red]✖ Pipeline Crash:[/bold red] {e}")
            
            # Log crash telemetry
            async with self.file_lock:
                with open(config.TELEMETRY_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "status": "CRASH",
                        "error": str(e),
                    }) + "\n")
            return

        record = None
        reason = current_state.get("judge_verdict", {}).get("reason", "Failed quality check")
        final_status = current_state.get("final_status")

        async with self.lock:
            self.qe_score = current_state.get("qe_score", self.qe_score)
            self.past_rejections = current_state.get("past_rejections", self.past_rejections)
            self.total_tokens += current_state.get("total_tokens", 0)
            self.total_cost += current_state.get("total_cost", 0.0)

            if final_status == "PASSED":
                if self.total_approved >= self.target_count:
                    return

                record = format_sharegpt_record(
                    entry=current_state["entry"],
                    thought_block=current_state["thought_block"],
                    analysis_json=current_state["analysis_json"],
                    custom_persona=current_state["profile"].get("custom_persona_prompt"),
                )
                
                self.total_approved += 1
                self.session_approved += 1
                
                analysis = current_state["analysis_json"]
                distress = analysis.get("distressFlag", False)
                distress_badge = "[bold red]CRISIS[/bold red]" if distress else "[dim green]Safe[/dim green]"
                mood = analysis.get("moodScore", 5)
                sentiment = analysis.get("sentiment", "Neutral")
                word_count = len(current_state["entry"].split())

                progress.console.print(
                    f"  [bold green]✔ Sample #{self.total_approved:02d}[/bold green] "
                    f"| Mood: [bold yellow]{mood}/10[/bold yellow] ([cyan]{sentiment}[/cyan]) "
                    f"| Words: [bold white]{word_count}[/bold white] "
                    f"| Safety: {distress_badge} "
                    f"| QE Score: [bold green]+{self.qe_score}[/bold green]"
                )
                progress.advance(task_id)
            else:
                self.discard_count += 1
                progress.console.print(
                    f"  [bold red]✖ Discarded[/bold red] "
                    f"[dim]| Reason: {reason[:80]}...[/dim]"
                )
            
            pass_rate = (self.session_approved / self.total_attempts) * 100
            progress.update(
                task_id, 
                stats=f"[yellow]Pass: {pass_rate:.0f}%[/yellow] | [cyan]Cost: ${self.total_cost:.2f}[/cyan] | [magenta]Tokens: {self.total_tokens/1000:.1f}k[/magenta]"
            )

        # Write to disk OUTSIDE the main lock
        async with self.file_lock:
            # 1. Telemetry logging (for Dashboard)
            telemetry_event = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "status": final_status,
                "editor_iterations": current_state.get("editor_iteration", 0),
                "schema_retries": current_state.get("schema_retry_count", 0),
                "qe_score": self.qe_score,
                "tokens": current_state.get("total_tokens", 0),
                "cost": current_state.get("total_cost", 0.0),
                "discard_reason": reason if final_status != "PASSED" else None
            }
            with open(config.TELEMETRY_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(telemetry_event) + "\n")
                
            # 2. Detailed rejection logging
            if final_status != "PASSED":
                with open(config.REJECTIONS_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.datetime.utcnow().isoformat()}] REJECTED\n")
                    f.write(f"Reason: {reason}\n")
                    f.write("-" * 40 + "\n")

            # 3. Successful JSONL save
            if record is not None:
                is_test = random.random() < config.TEST_SPLIT_RATIO
                target_file = config.TEST_DATASET_PATH if is_test else config.TRAIN_DATASET_PATH
                with open(target_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def amain():
    parser = argparse.ArgumentParser(description="Run Async Multi-Agent Synthetic Data Distillation Pipeline")
    parser.add_argument("--count", type=int, default=10, help="Target total approved samples")
    parser.add_argument("--force-edge-cases", action="store_true", help="Force 100% of samples to be edge cases")
    parser.add_argument("--concurrency", type=str, default="5", help="Number of concurrent generation pipelines (int or 'auto')")
    args = parser.parse_args()

    # Determine concurrency limit
    if args.concurrency.lower() == "auto":
        # Smart heuristic for 'auto' concurrency
        is_local = "localhost" in config.LLM_BASE_URL or "127.0.0.1" in config.LLM_BASE_URL
        if is_local:
            # Local endpoints (vLLM, Ollama) can OOM with high concurrency. Keep it modest.
            concurrency_limit = 4
        else:
            # Remote APIs (OpenRouter, Together). Scale with CPU but cap at 15 to avoid instant 429 Rate Limits.
            concurrency_limit = min(15, (os.cpu_count() or 4) * 2)
    else:
        try:
            concurrency_limit = int(args.concurrency)
        except ValueError:
            console.print("[bold red]Invalid concurrency value. Must be an integer or 'auto'.[/bold red]")
            return

    manager = PipelineManager(args.count, args.force_edge_cases)

    banner_text = (
        f"[bold bright_white]Smart Diary - Async Distillation[/bold bright_white]\n\n"
        f"[bold cyan]Target Total Samples:[/bold cyan] [bold green]{args.count}[/bold green]\n"
        f"[bold cyan]Already Generated:[/bold cyan] [bold yellow]{manager.total_approved}[/bold yellow]\n"
        f"[bold cyan]Initial Concurrency:[/bold cyan] [bold yellow]{concurrency_limit}x parallel pipelines[/bold yellow] { '(Auto AIMD)' if args.concurrency.lower() == 'auto' else '(Fixed Start)'}\n"
    )
    console.print(Panel(banner_text, title="[bold green]Pipeline Config[/bold green]", border_style="bright_blue"))

    if manager.total_approved >= args.count:
        console.print("[bold green]✔ Target count already reached in dataset. Exiting.[/bold green]")
        return

    # Setup global AIMD controller
    config.CONCURRENCY_CONTROLLER.setup(concurrency_limit)

    async def bound_pipeline(progress, task_id):
        # We no longer use a semaphore block here because the spawn loop below acts as the concurrency limiter.
        await manager.run_single_pipeline(progress, task_id)

    with Progress(
        SpinnerColumn(spinner_name="dots", style="bright_cyan"),
        TextColumn("[bold bright_white]{task.description}[/bold bright_white]"),
        BarColumn(bar_width=30, complete_style="green", finished_style="bold green"),
        MofNCompleteColumn(),
        TextColumn("[bold green]{task.percentage:>3.0f}%[/bold green]"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        TextColumn("{task.fields[stats]}"),
        console=console,
        refresh_per_second=5,
    ) as progress:
        task_id = progress.add_task(
            "Distilling", 
            total=args.count, 
            completed=manager.total_approved,
            stats=f"[yellow]Pass: 100%[/yellow] | [cyan]Cost: $0.00[/cyan] | [magenta]Workers: {config.CONCURRENCY_CONTROLLER.current}[/magenta]"
        )

        pending = set()
        while manager.total_approved < args.count:
            # Poll dynamic concurrency limit continuously
            current_limit = config.CONCURRENCY_CONTROLLER.current
            
            # Update the progress bar to show the dynamic worker limit
            pass_rate = (manager.session_approved / manager.total_attempts * 100) if manager.total_attempts > 0 else 100
            progress.update(
                task_id, 
                stats=f"[yellow]Pass: {pass_rate:.0f}%[/yellow] | [cyan]Cost: ${manager.total_cost:.2f}[/cyan] | [magenta]Workers: {current_limit}[/magenta]"
            )

            # Spawn workers up to the current dynamic limit
            while len(pending) < current_limit and manager.total_approved < args.count:
                task = asyncio.create_task(bound_pipeline(progress, task_id))
                pending.add(task)

            # Wait for at least one worker to finish, or a short timeout to allow the limit to adjust if it shrank
            if pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=1.0)

        # Wait for any still-running workers to finish cleanly
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    # Print Summary Table
    table = Table(title="[bold green]Session Summary[/bold green]", border_style="bright_blue")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold bright_white")
    table.add_row("Total Approved (All Time)", f"[bold green]{manager.total_approved}[/bold green]")
    table.add_row("Approved This Session", f"[bold green]{manager.session_approved}[/bold green]")
    table.add_row("Discarded This Session", f"[bold red]{manager.discard_count}[/bold red]")
    table.add_row("Session Pass Rate", f"[bold yellow]{(manager.session_approved / max(1, manager.total_attempts)):.1%}[/bold yellow]")
    table.add_row("Tokens Used (Session)", f"[bold magenta]{manager.total_tokens:,}[/bold magenta]")
    table.add_row("API Cost (Session)", f"[bold cyan]${manager.total_cost:.2f}[/bold cyan]")
    table.add_row("Final QE Score", f"[bold cyan]{manager.qe_score}[/bold cyan]")
    console.print("\n", table)

if __name__ == "__main__":
    asyncio.run(amain())
