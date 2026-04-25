import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import get_db
from models import Decision
from routers.auth import verify_session
from skills.decision_agent import run_decision_agent
from memory_service import search_memories

router = APIRouter(tags=["decisions"])

# Pydantic Schemas
class DecisionCreate(BaseModel):
    topic: str
    framework: Optional[str] = None
    factors: Optional[list] = None
    options: Optional[list] = None

class DecisionUpdate(BaseModel):
    status: Optional[str] = None
    framework: Optional[str] = None
    factors: Optional[list] = None
    options: Optional[list] = None
    primary_option_id: Optional[str] = None
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    review_date: Optional[datetime] = None

class AgentSimulationRequest(BaseModel):
    context: str

# Endpoints
@router.post("/api/decisions")
def create_decision(decision: DecisionCreate, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    db_decision = Decision(
        user_id=user_id,
        topic=decision.topic,
        framework=decision.framework,
        factors=decision.factors,
        options=decision.options,
    )
    db.add(db_decision)
    db.commit()
    db.refresh(db_decision)
    return db_decision

@router.get("/api/decisions")
def get_decisions(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    return db.query(Decision).filter(Decision.user_id == user_id).order_by(Decision.created_at.desc()).all()

@router.get("/api/decisions/{decision_id}")
def get_decision(decision_id: str, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    decision = db.query(Decision).filter(Decision.id == decision_id, Decision.user_id == user_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision

@router.patch("/api/decisions/{decision_id}")
def update_decision(decision_id: str, updates: DecisionUpdate, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    decision = db.query(Decision).filter(Decision.id == decision_id, Decision.user_id == user_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
        
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(decision, key, value)
        
    db.commit()
    db.refresh(decision)
    return decision

@router.post("/api/decisions/{decision_id}/simulate")
def run_agent_simulation(decision_id: str, request: AgentSimulationRequest, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    """Triggers the LangGraph Agent to analyze the decision."""
    decision = db.query(Decision).filter(Decision.id == decision_id, Decision.user_id == user_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
        
    # Search mem0 for long-term memories relevant to this decision topic
    memories = search_memories(user_id=user_id, query=decision.topic, limit=10)
    if memories:
        print(f"[Decisions] Injecting {len(memories.splitlines())} memory lines for user {user_id}", flush=True)
    
    # Run the LangGraph agent with grounded memory context
    result = run_decision_agent(
        detected_decision=decision.topic,
        context=request.context,
        user_input=f"I need help with this decision. Current options: {decision.options}",
        memories=memories
    )
    
    # Parse the clean JSON string into a dict for DB storage
    import json as _json
    parsed_result = None
    try:
        parsed_result = _json.loads(result["analysis_result"])
    except Exception:
        parsed_result = {"raw": result["analysis_result"]}
    
    # Persist framework + analysis_result to DB so it loads on next visit
    decision.framework = result.get("framework_used", decision.framework)
    decision.analysis_result = parsed_result
    db.commit()
    db.refresh(decision)
        
    return {
        "analysis_result": result["analysis_result"],
        "framework_used": decision.framework
    }
