"""Lightweight helpfulness votes on AI output.

The long-game answer to "is this tool actually helping?" — every reflection,
chat answer, and weekly review can be voted 👍/👎, giving a real signal to
tune prompts against instead of guessing.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
import models
from .auth import verify_session

router = APIRouter()

VALID_KINDS = {"reflection", "chat", "weekly_review"}


class FeedbackVote(BaseModel):
    kind: str
    ref_id: str | None = None
    vote: int


@router.post("/api/ai-feedback")
def submit_feedback(payload: FeedbackVote, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    if payload.kind not in VALID_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(VALID_KINDS)}")
    if payload.vote not in (1, -1):
        raise HTTPException(status_code=422, detail="vote must be 1 or -1")

    db.add(models.AIFeedback(
        user_id=user_id,
        kind=payload.kind,
        ref_id=payload.ref_id,
        vote=payload.vote,
    ))
    db.commit()
    return {"success": True}


@router.get("/api/ai-feedback/summary")
def feedback_summary(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    rows = db.query(models.AIFeedback).filter(models.AIFeedback.user_id == user_id).all()
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = summary.setdefault(row.kind, {"helpful": 0, "not_helpful": 0})
        bucket["helpful" if row.vote > 0 else "not_helpful"] += 1
    return {"summary": summary, "total_votes": len(rows)}
