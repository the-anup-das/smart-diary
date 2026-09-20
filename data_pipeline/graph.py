"""
LangGraph workflow for one sample.

    writer -> reviewer -(approved)-> analyzer -> validator -(valid)-> judge -(pass)-> [second opinion] -> END
                 |                       ^            |                 |
                 +-> editor (loop) ------+<-----------+ (schema retry)  +-> analyzer (one repair with the critique)

Terminal statuses: PASSED, FAILED_REVIEW, FAILED_SCHEMA, FAILED_JUDGE, FAILED_JUDGE2.
The judge's critique feeds one repair attempt and the shared lessons store, so later samples
improve; the lessons never enter the training records.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from data_pipeline import config
from data_pipeline.agents.analyzer import analyze_journal_entry
from data_pipeline.agents.editor import edit_journal_entry
from data_pipeline.agents.judge import judge_candidate, judge_passes, judge_reason
from data_pipeline.agents.llm_client import LLMCallError
from data_pipeline.agents.reviewer import review_journal_entry
from data_pipeline.agents.schema_validator import validate_schema
from data_pipeline.agents.writer import generate_journal_entry
from data_pipeline.endpoints import Endpoint, EndpointPool
from data_pipeline.lessons import LessonsStore

FINAL_STATUSES = ("PASSED", "FAILED_REVIEW", "FAILED_SCHEMA", "FAILED_JUDGE", "FAILED_JUDGE2")


class PipelineState(TypedDict, total=False):
    profile: dict
    batch_index: int
    writer_model: str
    reviewer_model: str
    entry: str
    editor_iteration: int
    review: dict
    analysis_json: dict
    analysis_error: Optional[str]
    schema_retry_count: int
    judge_verdict: dict
    judge_retry_count: int
    judge_host: str
    judge_model: str
    needs_judge2: bool
    judge2_verdict: dict
    judge2_host: str
    judge2_model: str
    final_status: str
    discard_reason: Optional[str]
    total_tokens: int
    total_cost: float
    calls: int


@dataclass
class PipelineRuntime:
    """Everything the nodes need that is not sample state: endpoints, judge pools, the lessons store."""
    analyzer: Endpoint
    editor: Endpoint
    reviewer: Endpoint
    writers: list[Endpoint]
    judge_pool: EndpointPool
    lessons: LessonsStore
    judge2: Optional[Endpoint] = None
    judge2_pool: Optional[EndpointPool] = None
    judge2_enabled: bool = True
    rng: random.Random = field(default_factory=lambda: random.Random(config.SEED))
    disagreements_path: Optional[Path] = None
    file_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def writer_endpoint(self, batch_index: int) -> Endpoint:
        return self.writers[batch_index % len(self.writers)]

    def reviewer_endpoint(self, writer_model: str) -> Endpoint:
        """With several writers, a batch is reviewed by a model other than the one that wrote it."""
        if len(self.writers) > 1:
            others = [w for w in self.writers if w.model != writer_model]
            if others:
                return others[0]
        return self.reviewer

    def wants_judge2(self, passed: bool) -> bool:
        if not (self.judge2 and self.judge2_enabled):
            return False
        rate = config.JUDGE2_SAMPLE_RATE if passed else config.JUDGE2_FAIL_SAMPLE_RATE
        return self.rng.random() < rate


def _acc(state: PipelineState, usage: dict) -> dict:
    return {
        "total_tokens": state.get("total_tokens", 0) + int(usage.get("tokens", 0)),
        "total_cost": state.get("total_cost", 0.0) + float(usage.get("cost", 0.0)),
        "calls": state.get("calls", 0) + 1,
    }


async def judge_with_pool(runtime: PipelineRuntime, entry: str, analysis_json: dict, persona: Optional[str]) -> tuple[dict, dict, Endpoint]:
    """Try judge endpoints in order; a failing host cools down and the next one is used."""
    tried: set[Endpoint] = set()
    for _round in range(2):
        while True:
            ep = runtime.judge_pool.pick(exclude=tried)
            if ep is None:
                break
            try:
                await runtime.judge_pool.throttle(ep)
                verdict, usage = await judge_candidate(entry, analysis_json, persona, endpoint=ep)
                return verdict, usage, ep
            except LLMCallError:
                runtime.judge_pool.penalise(ep)
                tried.add(ep)
        wait = runtime.judge_pool.seconds_until_available()
        if wait > config.ENDPOINT_COOLDOWN_S:
            break
        await asyncio.sleep(wait)
        tried = set()
    raise LLMCallError("all judge endpoints are unavailable", retryable=True)


def build_pipeline_graph(runtime: PipelineRuntime):
    async def writer_node(state: PipelineState) -> dict:
        ep = runtime.writer_endpoint(state.get("batch_index", 0))
        entry, usage = await generate_journal_entry(state["profile"], endpoint=ep, lessons=runtime.lessons.top("entry"))
        return {"entry": entry, "editor_iteration": 0, "writer_model": ep.model, "reviewer_model": runtime.reviewer_endpoint(ep.model).model, **_acc(state, usage)}

    async def reviewer_node(state: PipelineState) -> dict:
        ep = runtime.reviewer_endpoint(state.get("writer_model", ""))
        review, usage = await review_journal_entry(state["entry"], state["profile"], endpoint=ep)
        if not review.get("approved"):
            await runtime.lessons.add("entry", review.get("critique", ""))
        return {"review": review, **_acc(state, usage)}

    async def editor_node(state: PipelineState) -> dict:
        critique = state["review"].get("critique") or "Add concrete detail and remove generic phrasing."
        revised, usage = await edit_journal_entry(state["entry"], critique, state["profile"], endpoint=runtime.editor)
        return {"entry": revised, "editor_iteration": state.get("editor_iteration", 0) + 1, **_acc(state, usage)}

    async def analyzer_node(state: PipelineState) -> dict:
        persona = state["profile"].get("custom_persona_prompt")
        previous_error = state.get("analysis_error")
        previous_json = state.get("analysis_json") if previous_error and state.get("analysis_json") else None
        data, error, usage = await analyze_journal_entry(
            state["entry"], persona, endpoint=runtime.analyzer,
            previous_json=previous_json, previous_error=previous_error, lessons=runtime.lessons.top("labels"),
        )
        return {"analysis_json": data or {}, "analysis_error": error, "final_status": "PENDING", **_acc(state, usage)}

    async def schema_validator_node(state: PipelineState) -> dict:
        is_valid, error, _ = validate_schema(state.get("analysis_json") or {})
        if is_valid:
            return {"analysis_error": None}
        return {"analysis_error": error, "schema_retry_count": state.get("schema_retry_count", 0) + 1}

    async def failed_review_node(state: PipelineState) -> dict:
        return {"final_status": "FAILED_REVIEW", "discard_reason": state.get("review", {}).get("critique") or "entry rejected by the reviewer"}

    async def failed_schema_node(state: PipelineState) -> dict:
        return {"final_status": "FAILED_SCHEMA", "discard_reason": state.get("analysis_error") or "analysis failed validation"}

    async def judge_node(state: PipelineState) -> dict:
        persona = state["profile"].get("custom_persona_prompt")
        verdict, usage, ep = await judge_with_pool(runtime, state["entry"], state["analysis_json"], persona)
        passed = judge_passes(verdict)
        updates: dict[str, Any] = {"judge_verdict": verdict, "judge_host": ep.host, "judge_model": ep.model, "needs_judge2": False, **_acc(state, usage)}
        if passed:
            updates.update({"final_status": "PASSED", "discard_reason": None, "needs_judge2": runtime.wants_judge2(True)})
            return updates
        reason = judge_reason(verdict)
        await runtime.lessons.add("labels", verdict.get("label_notes") or reason)
        if verdict.get("entry_notes"):
            await runtime.lessons.add("entry", verdict["entry_notes"])
        if state.get("judge_retry_count", 0) < config.MAX_JUDGE_RETRY and not verdict.get("unparseable"):
            updates.update({
                "judge_retry_count": state.get("judge_retry_count", 0) + 1,
                "analysis_error": f"the quality judge rejected it: {reason}",
                "final_status": "REPAIRING",
            })
            return updates
        updates.update({"final_status": "FAILED_JUDGE", "discard_reason": reason, "needs_judge2": runtime.wants_judge2(False)})
        return updates

    async def judge2_node(state: PipelineState) -> dict:
        ep = runtime.judge2
        assert ep is not None
        persona = state["profile"].get("custom_persona_prompt")
        try:
            if runtime.judge2_pool:
                await runtime.judge2_pool.throttle(ep)
            verdict, usage = await judge_candidate(state["entry"], state["analysis_json"], persona, endpoint=ep)
        except LLMCallError as e:
            return {"judge2_verdict": {"skipped": str(e)[:200]}, "judge2_host": ep.host, "judge2_model": ep.model}
        updates: dict[str, Any] = {"judge2_verdict": verdict, "judge2_host": ep.host, "judge2_model": ep.model, **_acc(state, usage)}
        first_passed = state.get("final_status") == "PASSED"
        second_passed = judge_passes(verdict)
        if first_passed and not second_passed:
            reason = judge_reason(verdict)
            updates.update({"final_status": "FAILED_JUDGE2", "discard_reason": f"second opinion: {reason}"})
            await runtime.lessons.add("labels", verdict.get("label_notes") or reason)
        if first_passed != second_passed and runtime.disagreements_path:
            row = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "first": {"model": state.get("judge_model"), "host": state.get("judge_host"), "passed": first_passed, "verdict": state.get("judge_verdict")},
                "second": {"model": ep.model, "host": ep.host, "passed": second_passed, "verdict": verdict},
                "entry": state["entry"], "analysis": state["analysis_json"],
            }
            async with runtime.file_lock:
                runtime.disagreements_path.parent.mkdir(parents=True, exist_ok=True)
                with open(runtime.disagreements_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return updates

    def route_after_review(state: PipelineState) -> str:
        if state.get("review", {}).get("approved"):
            return "analyzer"
        if state.get("editor_iteration", 0) < config.MAX_EDITOR_ITERATIONS:
            return "editor"
        return "failed_review"

    def route_after_validation(state: PipelineState) -> str:
        if not state.get("analysis_error"):
            return "judge"
        if state.get("schema_retry_count", 0) < config.MAX_SCHEMA_RETRY:
            return "analyzer"
        return "failed_schema"

    def route_after_judge(state: PipelineState) -> str:
        if state.get("final_status") == "REPAIRING":
            return "analyzer"
        if state.get("needs_judge2"):
            return "judge2"
        return END

    workflow = StateGraph(PipelineState)
    for name, node in (
        ("writer", writer_node), ("reviewer", reviewer_node), ("editor", editor_node), ("analyzer", analyzer_node),
        ("schema_validator", schema_validator_node), ("judge", judge_node), ("judge2", judge2_node),
        ("failed_review", failed_review_node), ("failed_schema", failed_schema_node),
    ):
        workflow.add_node(name, node)
    workflow.set_entry_point("writer")
    workflow.add_edge("writer", "reviewer")
    workflow.add_conditional_edges("reviewer", route_after_review, {"analyzer": "analyzer", "editor": "editor", "failed_review": "failed_review"})
    workflow.add_edge("editor", "reviewer")
    workflow.add_edge("analyzer", "schema_validator")
    workflow.add_conditional_edges("schema_validator", route_after_validation, {"judge": "judge", "analyzer": "analyzer", "failed_schema": "failed_schema"})
    workflow.add_conditional_edges("judge", route_after_judge, {"analyzer": "analyzer", "judge2": "judge2", END: END})
    workflow.add_edge("judge2", END)
    workflow.add_edge("failed_review", END)
    workflow.add_edge("failed_schema", END)
    return workflow.compile()


__all__ = ["PipelineState", "PipelineRuntime", "build_pipeline_graph", "judge_with_pool", "FINAL_STATUSES"]
