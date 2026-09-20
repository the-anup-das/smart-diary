"""LangGraph workflow definition for the Multi-Agent Synthetic Data Distillation Pipeline."""

from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, END

from data_pipeline import config
from data_pipeline.agents.diversity_controller import generate_diversity_profile
from data_pipeline.agents.writer import generate_journal_entry
from data_pipeline.agents.reviewer import review_journal_entry
from data_pipeline.agents.editor import edit_journal_entry
from data_pipeline.agents.analyzer import analyze_journal_entry
from data_pipeline.agents.schema_validator import validate_schema
from data_pipeline.agents.qe import evaluate_data_triplet
from data_pipeline.agents.judge import judge_candidate


class PipelineState(TypedDict):
    profile: Dict[str, Any]
    entry: str
    editor_iteration: int
    review: Dict[str, Any]
    thought_block: str
    analysis_json: Dict[str, Any]
    schema_retry_count: int
    schema_error: Optional[str]
    qe_report: Dict[str, Any]
    qe_score: int
    past_rejections: List[str]
    judge_verdict: Dict[str, Any]
    final_status: str
    
    # Telemetry
    total_tokens: int
    total_cost: float


# Node Implementations
async def diversity_node(state: PipelineState) -> Dict[str, Any]:
    if not state.get("profile"):
        profile = generate_diversity_profile()
        return {"profile": profile, "total_tokens": state.get("total_tokens", 0), "total_cost": state.get("total_cost", 0.0)}
    return {}


async def writer_node(state: PipelineState) -> Dict[str, Any]:
    entry, usage = await generate_journal_entry(state["profile"])
    return {
        "entry": entry,
        "editor_iteration": 0,
        "total_tokens": state.get("total_tokens", 0) + usage.get("tokens", 0),
        "total_cost": state.get("total_cost", 0.0) + usage.get("cost", 0.0),
    }


async def reviewer_node(state: PipelineState) -> Dict[str, Any]:
    review, usage = await review_journal_entry(state["entry"], state["profile"])
    return {
        "review": review,
        "total_tokens": state.get("total_tokens", 0) + usage.get("tokens", 0),
        "total_cost": state.get("total_cost", 0.0) + usage.get("cost", 0.0),
    }


async def editor_node(state: PipelineState) -> Dict[str, Any]:
    critique = state["review"].get("critique", "Improve authenticity and detail.")
    revised_entry, usage = await edit_journal_entry(state["entry"], critique, state["profile"])
    return {
        "entry": revised_entry,
        "editor_iteration": state["editor_iteration"] + 1,
        "total_tokens": state.get("total_tokens", 0) + usage.get("tokens", 0),
        "total_cost": state.get("total_cost", 0.0) + usage.get("cost", 0.0),
    }


async def analyzer_node(state: PipelineState) -> Dict[str, Any]:
    custom_persona = state["profile"].get("custom_persona_prompt")
    raw, thought_block, parsed_json, usage = await analyze_journal_entry(state["entry"], custom_persona)
    return {
        "thought_block": thought_block,
        "analysis_json": parsed_json,
        "schema_retry_count": state.get("schema_retry_count", 0),
        "total_tokens": state.get("total_tokens", 0) + usage.get("tokens", 0),
        "total_cost": state.get("total_cost", 0.0) + usage.get("cost", 0.0),
    }


async def schema_validator_node(state: PipelineState) -> Dict[str, Any]:
    is_valid, error, _ = validate_schema(state["analysis_json"])
    if is_valid:
        return {"schema_error": None}
    else:
        return {
            "schema_error": error,
            "schema_retry_count": state["schema_retry_count"] + 1,
        }


async def qe_node(state: PipelineState) -> Dict[str, Any]:
    qe_report, usage = await evaluate_data_triplet(
        entry=state["entry"],
        thought_block=state["thought_block"],
        analysis_json=state["analysis_json"],
        qe_score=state.get("qe_score", 0),
        past_rejections=state.get("past_rejections", []),
    )
    return {
        "qe_report": qe_report,
        "total_tokens": state.get("total_tokens", 0) + usage.get("tokens", 0),
        "total_cost": state.get("total_cost", 0.0) + usage.get("cost", 0.0),
    }


async def judge_node(state: PipelineState) -> Dict[str, Any]:
    verdict, usage = await judge_candidate(
        entry=state["entry"],
        thought_block=state["thought_block"],
        analysis_json=state["analysis_json"],
        qe_report=state["qe_report"],
    )
    new_qe_score = state.get("qe_score", 0) + verdict.get("score_delta", 0)
    past_rejections = list(state.get("past_rejections", []))
    
    if verdict.get("decision") == "FAIL":
        past_rejections.append(verdict.get("reason", "Unknown failure"))
        final_status = "FAILED_JUDGE"
    else:
        final_status = "PASSED"

    return {
        "judge_verdict": verdict,
        "qe_score": new_qe_score,
        "past_rejections": past_rejections,
        "final_status": final_status,
        "total_tokens": state.get("total_tokens", 0) + usage.get("tokens", 0),
        "total_cost": state.get("total_cost", 0.0) + usage.get("cost", 0.0),
    }


# Routing Conditionals
def route_after_review(state: PipelineState) -> str:
    if state["review"].get("approved"):
        return "analyzer"
    if state["editor_iteration"] < config.MAX_EDITOR_ITERATIONS:
        return "editor"
    return END


def route_after_validation(state: PipelineState) -> str:
    if not state.get("schema_error"):
        return "qe"
    if state["schema_retry_count"] < config.MAX_SCHEMA_RETRY:
        return "analyzer"
    return END


def build_pipeline_graph():
    """Builds and compiles the complete LangGraph state machine."""
    workflow = StateGraph(PipelineState)

    # Add Nodes
    workflow.add_node("diversity", diversity_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("schema_validator", schema_validator_node)
    workflow.add_node("qe", qe_node)
    workflow.add_node("judge", judge_node)

    # Set Entry Point
    workflow.set_entry_point("diversity")

    # Add Edges
    workflow.add_edge("diversity", "writer")
    workflow.add_edge("writer", "reviewer")

    # Reviewer loop
    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "analyzer": "analyzer",
            "editor": "editor",
            END: END,
        }
    )
    workflow.add_edge("editor", "reviewer")

    # Schema Validation loop
    workflow.add_edge("analyzer", "schema_validator")
    workflow.add_conditional_edges(
        "schema_validator",
        route_after_validation,
        {
            "qe": "qe",
            "analyzer": "analyzer",
            END: END,
        }
    )

    # QE to Judge to Finish
    workflow.add_edge("qe", "judge")
    workflow.add_edge("judge", END)

    return workflow.compile()
