import json
import operator
from typing import Dict, Any, List, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

# --- 1. Define Pydantic Models for Structured Output ---

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


# --- 2. Define LangGraph State ---

class PathEvaluationResult(TypedDict):
    path_name: str
    factors: List[Dict[str, str]]

class DecisionState(TypedDict):
    detected_decision: str
    context: str
    user_input: str
    memories: str
    
    # State accumulated by Orchestrator
    paths: List[str]
    factors: List[Dict[str, str]]
    
    # State accumulated by Swarm (using annotated reduce for parallel array append)
    evaluations: Annotated[List[PathEvaluationResult], operator.add]
    
    # Final state
    synthesis: str
    blindspots: List[str]
    recommendation: str

class PathEvalState(TypedDict):
    # The state sent to each individual Path Evaluator node
    path_name: str
    detected_decision: str
    context: str
    user_input: str
    memories: str
    factors: List[Dict[str, str]]


# --- 3. Initialize LLM ---
llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
llm_json_orchestrator = llm.with_structured_output(OrchestratorOutput)
llm_json_evaluator = llm.with_structured_output(PathEvaluationModel)
llm_json_synthesis = llm.with_structured_output(SynthesisOutputModel)


# --- 4. Define Nodes ---

def orchestrator_node(state: DecisionState):
    """Discovers paths and dynamic factors."""
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
    
    response = llm_json_orchestrator.invoke([SystemMessage(content=prompt)])
    
    return {
        "paths": response.paths,
        "factors": [{"name": f.name, "description": f.description} for f in response.factors]
    }

def map_paths(state: DecisionState):
    """Maps the discovered paths to parallel evaluator nodes."""
    sends = []
    for path in state["paths"]:
        sends.append(Send("evaluator_node", {
            "path_name": path,
            "detected_decision": state["detected_decision"],
            "context": state["context"],
            "user_input": state["user_input"],
            "memories": state["memories"],
            "factors": state["factors"]
        }))
    return sends

def evaluator_node(state: PathEvalState):
    """Evaluates a single path against the factors (Runs in parallel)."""
    factors_str = "\n".join([f"- {f['name']}: {f['description']}" for f in state['factors']])
    
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
    
    response = llm_json_evaluator.invoke([SystemMessage(content=prompt)])
    
    eval_factors = []
    for f in response.factors:
        eval_factors.append({
            "factor_name": f.factor_name,
            "positive_impact": f.positive_impact,
            "negative_impact": f.negative_impact
        })
        
    return {
        "evaluations": [{
            "path_name": state["path_name"],
            "factors": eval_factors
        }]
    }

def synthesis_node(state: DecisionState):
    """Synthesizes all evaluations into a final recommendation."""
    evals_str = json.dumps(state["evaluations"], indent=2)
    
    prompt = f"""
    You are a Synthesis Agent. You have received the evaluations of multiple paths.
    
    EVALUATIONS:
    {evals_str}
    
    DECISION: {state['detected_decision']}
    MEMORIES: {state['memories']}
    
    Provide a compassionate summary, identify blindspots across the evaluations, and give a decisive recommendation.
    """
    
    response = llm_json_synthesis.invoke([SystemMessage(content=prompt)])
    
    return {
        "synthesis": response.summary,
        "blindspots": response.blindspots,
        "recommendation": response.recommendation
    }


# --- 5. Build Graph ---

builder = StateGraph(DecisionState)
builder.add_node("orchestrator_node", orchestrator_node)
builder.add_node("evaluator_node", evaluator_node)
builder.add_node("synthesis_node", synthesis_node)

builder.add_edge(START, "orchestrator_node")
builder.add_conditional_edges("orchestrator_node", map_paths, ["evaluator_node"])
builder.add_edge("evaluator_node", "synthesis_node")
builder.add_edge("synthesis_node", END)

decision_swarm = builder.compile()

# --- 6. Entry Point ---

def run_decision_agent(detected_decision: str, context: str, user_input: str, memories: str = "") -> dict:
    """Entry point to trigger the Decision Swarm."""
    
    initial_state = {
        "detected_decision": detected_decision,
        "context": context,
        "user_input": user_input,
        "memories": memories,
        "evaluations": []
    }
    
    final_state = decision_swarm.invoke(initial_state)
    
    # Format the output to match what the frontend expects
    final_json = {
        "summary": final_state["synthesis"],
        "paths": final_state["evaluations"],
        "blindspots": final_state["blindspots"],
        "recommendation": final_state["recommendation"]
    }
    
    return {
        "analysis_result": json.dumps(final_json),
        "framework_used": "dynamic_swarm"
    }

