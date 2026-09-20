"""
Decision swarm: an orchestrator discovers paths and factors, one evaluator per path runs in
parallel, and a synthesis node writes the recommendation. Every call goes through the LLM
router resolved for the person, so the local model or the cloud model is used consistently and
structured output works on either.
"""
import json
import operator
from typing import Any, Dict, List, Annotated

from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from llm_router import LLMRouter, get_router


# --- 1. Structured outputs ---

class FactorModel(BaseModel):
    name: str = Field(description="The name of the factor, e.g. 'Financial Risk', 'Mental Health', 'Family Strain'")
    description: str = Field(description="Why this factor matters for this decision")


class OrchestratorOutput(BaseModel):
    paths: List[str] = Field(description="List of 2 to 4 distinct paths. If only one is implied, add 'Status Quo'.")
    factors: List[FactorModel] = Field(description="List of 3 to 5 dynamic factors to evaluate against.")


class FactorEvaluationModel(BaseModel):
    factor_name: str
    positive_impact: str = Field(description="Specific positive consequences or pros. Use 'None' if none.")
    negative_impact: str = Field(description="Specific negative consequences or cons. Use 'None' if none.")


class PathEvaluationModel(BaseModel):
    factors: List[FactorEvaluationModel]


class SynthesisOutputModel(BaseModel):
    summary: str = Field(description="A compassionate 2-sentence summary of the entire decision landscape.")
    blindspots: List[str] = Field(description="2-3 things the user might be romanticizing or ignoring.")
    recommendation: str = Field(description="A decisive recommendation based on the evaluation.")


# --- 2. Graph state ---

class PathEvaluationResult(TypedDict):
    path_name: str
    factors: List[Dict[str, str]]


class DecisionState(TypedDict):
    detected_decision: str
    context: str
    user_input: str
    memories: str
    router: Any
    paths: List[str]
    factors: List[Dict[str, str]]
    evaluations: Annotated[List[PathEvaluationResult], operator.add]
    synthesis: str
    blindspots: List[str]
    recommendation: str


class PathEvalState(TypedDict):
    path_name: str
    detected_decision: str
    context: str
    user_input: str
    memories: str
    factors: List[Dict[str, str]]
    router: Any


def _ask(router: LLMRouter, schema, prompt: str, max_tokens: int = 1200):
    return router.structured(schema, [{"role": "system", "content": prompt}], temperature=0.2, max_tokens=max_tokens).parsed


# --- 3. Nodes ---

def orchestrator_node(state: DecisionState):
    prompt = f"""
    You are a strategic decision orchestrator.
    DECISION: {state['detected_decision']}
    CONTEXT: {state['context']}
    USER REQUEST: {state['user_input']}
    MEMORIES: {state['memories']}

    Analyze the situation and output:
    1. A list of 2 to 4 distinct, realistic paths the user could take. Ensure they are mutually exclusive.
    2. A list of 3 to 5 dynamic factors that are critical for evaluating this decision (e.g., 'Startup Capital', 'Spouse Support', 'Burnout Risk').
    """
    response = _ask(state["router"], OrchestratorOutput, prompt)
    return {"paths": response.paths, "factors": [{"name": f.name, "description": f.description} for f in response.factors]}


def map_paths(state: DecisionState):
    return [
        Send("evaluator_node", {
            "path_name": path, "detected_decision": state["detected_decision"], "context": state["context"],
            "user_input": state["user_input"], "memories": state["memories"], "factors": state["factors"], "router": state["router"],
        })
        for path in state["paths"]
    ]


def evaluator_node(state: PathEvalState):
    factors_str = "\n".join(f"- {f['name']}: {f['description']}" for f in state["factors"])
    prompt = f"""
    You are a rigorous Path Evaluator.
    You are evaluating ONE specific path: "{state['path_name']}"

    DECISION: {state['detected_decision']}
    MEMORIES: {state['memories']}

    You must evaluate this path against these specific factors:
    {factors_str}

    For each factor, strictly define the POSITIVE impacts and NEGATIVE impacts of taking this path.
    Ground your analysis in the provided memories. Be specific.
    """
    response = _ask(state["router"], PathEvaluationModel, prompt)
    return {"evaluations": [{
        "path_name": state["path_name"],
        "factors": [{"factor_name": f.factor_name, "positive_impact": f.positive_impact, "negative_impact": f.negative_impact} for f in response.factors],
    }]}


def synthesis_node(state: DecisionState):
    prompt = f"""
    You are a Synthesis Agent. You have received the evaluations of multiple paths.

    EVALUATIONS:
    {json.dumps(state["evaluations"], indent=2)}

    DECISION: {state['detected_decision']}
    MEMORIES: {state['memories']}

    Provide a compassionate summary, identify blindspots across the evaluations, and give a decisive recommendation.
    """
    response = _ask(state["router"], SynthesisOutputModel, prompt)
    return {"synthesis": response.summary, "blindspots": response.blindspots, "recommendation": response.recommendation}


# --- 4. Graph ---

builder = StateGraph(DecisionState)
builder.add_node("orchestrator_node", orchestrator_node)
builder.add_node("evaluator_node", evaluator_node)
builder.add_node("synthesis_node", synthesis_node)
builder.add_edge(START, "orchestrator_node")
builder.add_conditional_edges("orchestrator_node", map_paths, ["evaluator_node"])
builder.add_edge("evaluator_node", "synthesis_node")
builder.add_edge("synthesis_node", END)
decision_swarm = builder.compile()


# --- 5. Entry point ---

def run_decision_agent(detected_decision: str, context: str, user_input: str, memories: str = "", preferences: dict | None = None, router: LLMRouter | None = None) -> dict:
    router = router or get_router(preferences)
    final_state = decision_swarm.invoke({
        "detected_decision": detected_decision, "context": context, "user_input": user_input,
        "memories": memories, "router": router, "evaluations": [],
    })
    final_json = {
        "summary": final_state["synthesis"],
        "paths": final_state["evaluations"],
        "blindspots": final_state["blindspots"],
        "recommendation": final_state["recommendation"],
    }
    return {"analysis_result": json.dumps(final_json), "framework_used": "dynamic_swarm", "model": {"provider": router.route.provider, "name": router.route.model}}
