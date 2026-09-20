"""
calm.py - the 3-Minute Reset for overthinking.

When the diary analysis flags rumination (energy_data.rumination_level is
"moderate" or "high") the feedback view offers a guided three-minute reset,
the editor nudges while a looping entry is being written, and the Energy page
offers it as a daily practice. The practice follows the 1-1-1 structure from
Dr. Saloni Singh's "How to Stop Overthinking in 3 Minutes" (chapter 8):

    minute 1  affectionate breathing
    minute 2  complete stillness
    minute 3  visualisation, closed with affirmations

Minutes one and two need no AI. Minute three is personalised with a single
structured LLM call so the writer pictures themselves moving calmly through
the *specific* situation they were circling. If the call fails, AI is paused,
or there is no entry today, a generic script is used and the practice still
works.

Every session is stored (see models.CalmSession) so the practice can be
tracked like a habit. The book recommends journaling how you feel after each
practice, which is why a session carries a before/after "how busy is your
mind" rating and an optional note.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Literal, Optional
from pydantic import BaseModel, Field
from database import get_db
import models
from .auth import verify_session
import openai
import hashlib
import os
import re

router = APIRouter(tags=["calm"])

PRACTICE_NAME = "3-Minute Reset"
STEP_SECONDS = 60
CALM_ENERGY_BONUS = 5  # battery points credited on the Energy page for a completed reset today
RUMINATION_TYPES = ("past_regret", "future_worry", "social_comparison", "self_judgment", "information_overload", "mixed")

# --------------------------------------------------------------------------
# Minute-three planner (one structured LLM call)
# --------------------------------------------------------------------------

class ResetPlanSchema(BaseModel):
    loopThought: str = Field(description=(
        "The single thought the writer keeps circling, paraphrased gently in the second person "
        "in at most 20 words, e.g. 'You keep replaying how the meeting with your manager went.'"
    ))
    ruminationType: Literal["past_regret", "future_worry", "social_comparison", "self_judgment", "information_overload", "mixed"] = Field(description=(
        "past_regret: replaying or rewriting something that already happened. "
        "future_worry: rehearsing what might go wrong. "
        "social_comparison: measuring themselves against other people. "
        "self_judgment: harsh verdicts about their own worth or ability. "
        "information_overload: carrying noise, news or other people's opinions. "
        "mixed: more than one of the above."
    ))
    acknowledgement: str = Field(description=(
        "One warm, non-judgmental sentence that names the loop without arguing with it. "
        "Never tell the writer to stop thinking."
    ))
    letGo: str = Field(description=(
        "One sentence naming what can be set down right now, matched to the rumination type: "
        "an alternate past that does not exist, a future that has not happened, someone else's scoreboard, "
        "a harsh self-verdict, or noise that is not theirs to carry."
    ))
    whatMatters: str = Field(description=(
        "One sentence naming the one thing in this situation that truly matters and that the writer can actually influence."
    ))
    visualisation: list[str] = Field(description=(
        "Exactly 4 short present-tense, second-person lines (max 18 words each) that walk the writer through "
        "the specific situation from the entry: seeing themselves with a gentle smile, moving unhurried, "
        "responding to the trigger with calm, and finishing the day well. Use concrete details from the entry."
    ))
    affirmations: list[str] = Field(description=(
        "Exactly 3 first-person, present-tense affirmations (max 12 words each) tailored to this loop. "
        "Calm, believable and grounded. No toxic positivity, no promises about outcomes."
    ))
    lessonQuestion: str = Field(description=(
        "One reflective question for the writer's journal, in the spirit of 'what is this situation trying to "
        "teach me' or 'what quality do I need to get through this well', made specific to the entry."
    ))


GENERIC_PLAN: dict = {
    "loopThought": None,
    "ruminationType": "mixed",
    "acknowledgement": "Your mind has been busy. That is allowed. Nothing needs to be solved in the next three minutes.",
    "letGo": "For now, set down the version of events that only exists in your head.",
    "whatMatters": "Only what is in front of you today, and only the part of it you can actually influence.",
    "visualisation": [
        "Picture yourself moving through the rest of today with a gentle smile.",
        "See yourself doing each task unhurried, one at a time, with room to breathe.",
        "When the familiar worry shows up, watch yourself notice it and stay steady.",
        "See the day end well, your mind quiet and your body at ease.",
    ],
    "affirmations": [
        "My mind is settling. It is clear and calm.",
        "I give space only to what truly matters.",
        "I can meet whatever comes with a steady mind.",
    ],
    "lessonQuestion": "What is this situation trying to teach me?",
}

SYSTEM_PROMPT = (
    "You are a calm, warm mindfulness coach helping someone who has just written a diary entry while overthinking. "
    "They are about to do a three-minute reset practice: one minute of affectionate breathing, one minute of complete "
    "stillness, then one minute of guided visualisation closed with affirmations. You write only the third minute.\n\n"
    "Principles you must follow:\n"
    "- Do not judge the thoughts and never tell the writer to stop thinking. Thoughts are allowed; they are neither "
    "resisted nor indulged, only observed.\n"
    "- Name the loop gently and specifically, using the writer's own situation. Never invent facts that are not in the "
    "entry or the provided context.\n"
    "- Separate what truly matters and can be influenced from noise, comparison, alternate pasts and imagined futures. "
    "The writer gives space only to what matters and what they can make a difference to.\n"
    "- The visualisation shows the writer moving through their actual day and their actual trigger with a gentle "
    "smile, unhurried, responding with calm and finishing well. Present tense, second person, concrete.\n"
    "- Affirmations are first person, present tense, believable and grounded. No toxic positivity and no promises "
    "about outcomes.\n"
    "- Keep every line short enough to be read slowly in a few seconds. Plain words. No emojis, no exclamation marks, "
    "no medical or diagnostic language.\n"
    "- If the entry mentions self-harm or a crisis, keep the tone especially gentle and make whatMatters point to "
    "reaching out to a person they trust."
)

from llm_client import get_llm_client, get_model_name

_client: Optional[openai.OpenAI] = None

def _get_client() -> openai.OpenAI:
    """Lazy client so importing this module never requires an API key (tests, evals)."""
    global _client
    if _client is None:
        _client = get_llm_client()
    return _client


def _strip_html(html: str) -> str:
    return re.sub(r'<[^>]*>?', '', html or "")


def build_reset_plan(entry_text: str, energy: Optional[dict] = None, memories: str = "", preferences: Optional[dict] = None) -> tuple[dict, dict]:
    """
    Generate the personalised minute-three script for an entry.
    Pure function (no DB) so it can be evaluated and mocked. Returns (plan, usage).
    """
    energy = energy or {}
    preferences = preferences or {}

    context_lines = []
    if energy.get("rumination_level"):
        context_lines.append(f"Rumination level from today's analysis: {energy['rumination_level']}.")
    if energy.get("rumination_coaching"):
        context_lines.append(f"Coaching line already shown to the writer: {energy['rumination_coaching']}")
    controllables = [c.get("item") for c in energy.get("controllables", []) if isinstance(c, dict) and c.get("item")]
    uncontrollables = [u.get("item") for u in energy.get("uncontrollables", []) if isinstance(u, dict) and u.get("item")]
    if controllables:
        context_lines.append("Within the writer's control: " + "; ".join(controllables[:5]))
    if uncontrollables:
        context_lines.append("Outside the writer's control: " + "; ".join(uncontrollables[:5]))

    system_prompt = SYSTEM_PROMPT
    if context_lines:
        system_prompt += "\n\nCONTEXT FROM TODAY'S ANALYSIS:\n" + "\n".join(context_lines)
    if memories:
        system_prompt += "\n\n" + memories
    custom_persona = preferences.get("custom_persona_prompt", "")
    if custom_persona:
        system_prompt += f"\n\nUSER'S CUSTOM INSTRUCTIONS: {custom_persona}"

    response = _get_client().beta.chat.completions.parse(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": entry_text},
        ],
        response_format=ResetPlanSchema,
        temperature=0.4,
    )
    parsed = response.choices[0].message.parsed
    plan = parsed.model_dump()
    # The UI paces exactly four visualisation lines and three affirmations; pad or trim defensively.
    plan["visualisation"] = ([l for l in plan.get("visualisation", []) if l] + GENERIC_PLAN["visualisation"])[:4]
    plan["affirmations"] = ([a for a in plan.get("affirmations", []) if a] + GENERIC_PLAN["affirmations"])[:3]
    if plan.get("ruminationType") not in RUMINATION_TYPES:
        plan["ruminationType"] = "mixed"

    usage = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        "total_tokens": response.usage.total_tokens if response.usage else 0,
    }
    return plan, usage


def _safe_memories(user_id: str, text: str) -> str:
    """Long-term memories relevant to the entry, or an empty string if the memory store is unavailable."""
    try:
        from memory_service import search_memories
        return search_memories(user_id=user_id, query=text[:400], limit=5)
    except Exception as e:
        print(f"[Calm] Memory lookup skipped: {e}", flush=True)
        return ""

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _today_bounds():
    """UTC day bounds, matching how entries are looked up everywhere else in the app."""
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0), now.replace(hour=23, minute=59, second=59, microsecond=999999)


def _today_entry_and_feedback(user_id: str, db: Session):
    today_start, today_end = _today_bounds()
    entry = db.query(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.date >= today_start,
        models.JournalEntry.date <= today_end,
        models.JournalEntry.is_deleted == False
    ).first()
    if not entry:
        return None, None
    feedback = db.query(models.FeedbackReport).filter(models.FeedbackReport.journal_entry_id == entry.id).first()
    return entry, feedback


def completed_resets_today(user_id: str, db: Session) -> int:
    """Number of resets completed today (UTC). Used by the Energy page to credit the battery."""
    today_start, today_end = _today_bounds()
    return db.query(func.count(models.CalmSession.id)).filter(
        models.CalmSession.user_id == user_id,
        models.CalmSession.completed_at.isnot(None),
        models.CalmSession.started_at >= today_start,
        models.CalmSession.started_at <= today_end,
    ).scalar() or 0


def _serialize(s: models.CalmSession) -> dict:
    return {
        "id": s.id,
        "entryId": s.entry_id,
        "source": s.source,
        "ruminationLevel": s.rumination_level,
        "ruminationType": s.rumination_type,
        "loopThought": s.loop_thought,
        "plan": s.plan or GENERIC_PLAN,
        "personalized": bool(s.personalized),
        "mindBefore": s.mind_before,
        "mindAfter": s.mind_after,
        "stepsCompleted": s.steps_completed or 0,
        "durationSeconds": s.duration_seconds or 0,
        "note": s.note,
        "startedAt": s.started_at.isoformat() if s.started_at else None,
        "completedAt": s.completed_at.isoformat() if s.completed_at else None,
        "completed": s.completed_at is not None,
    }

# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

class SessionCreate(BaseModel):
    source: Literal["entry", "manual"] = "manual"


class SessionUpdate(BaseModel):
    mind_before: Optional[int] = Field(default=None, ge=1, le=5)
    mind_after: Optional[int] = Field(default=None, ge=1, le=5)
    steps_completed: Optional[int] = Field(default=None, ge=0, le=3)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=24 * 3600)
    note: Optional[str] = Field(default=None, max_length=1000)
    completed: Optional[bool] = None


@router.post("/api/calm/sessions")
def create_calm_session(data: SessionCreate, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    """
    Start a reset. Personalises minute three from today's entry when one exists, even before it has
    been analysed (reusing a plan already built for the same entry text), otherwise uses the generic script.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    prefs = user.preferences or {}

    entry, feedback = _today_entry_and_feedback(user_id, db)
    energy = dict(feedback.energy_data) if (feedback and feedback.energy_data) else {}
    level = energy.get("rumination_level")

    plan = dict(GENERIC_PLAN)
    personalized = False
    usage: dict = {}
    source_hash = None

    if entry and not prefs.get("pause_ai", False):
        raw_text = _strip_html(entry.content).strip()
        if len(raw_text) >= 10:
            # Same key the analysis uses for its cache, so a plan built before or after Save & Reflect is shared.
            source_hash = (feedback.content_hash if feedback and feedback.content_hash
                           else hashlib.sha256(raw_text.encode("utf-8")).hexdigest())
            prior = (
                db.query(models.CalmSession)
                .filter(
                    models.CalmSession.user_id == user_id,
                    models.CalmSession.source_hash == source_hash,
                    models.CalmSession.personalized == True,
                )
                .order_by(models.CalmSession.started_at.desc())
                .first()
            )
            if prior and prior.plan:
                plan, personalized = dict(prior.plan), True
            else:
                memories = _safe_memories(user_id, raw_text)
                try:
                    plan, usage = build_reset_plan(raw_text, energy, memories, prefs)
                    personalized = True
                except Exception as e:
                    print(f"[Calm] Plan generation failed, using the generic script: {e}", flush=True)
                    plan, personalized = dict(GENERIC_PLAN), False

    session = models.CalmSession(
        user_id=user_id,
        entry_id=entry.id if entry else None,
        source=data.source,
        rumination_level=level,
        rumination_type=plan.get("ruminationType"),
        loop_thought=plan.get("loopThought"),
        plan=plan,
        personalized=personalized,
        source_hash=source_hash if personalized else None,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"success": True, "session": _serialize(session)}


@router.patch("/api/calm/sessions/{session_id}")
def update_calm_session(session_id: str, data: SessionUpdate, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    """Record progress. Steps and duration only move forward; completion is sticky."""
    session = db.query(models.CalmSession).filter(
        models.CalmSession.id == session_id,
        models.CalmSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if data.mind_before is not None:
        session.mind_before = data.mind_before
    if data.mind_after is not None:
        session.mind_after = data.mind_after
    if data.steps_completed is not None:
        session.steps_completed = max(session.steps_completed or 0, data.steps_completed)
    if data.duration_seconds is not None:
        session.duration_seconds = max(session.duration_seconds or 0, data.duration_seconds)
    if data.note is not None:
        session.note = data.note.strip()[:500] or None
    if data.completed and session.completed_at is None:
        session.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return {"success": True, "session": _serialize(session)}


@router.get("/api/calm/summary")
def get_calm_summary(
    tz_offset: int = Query(default=0, ge=-840, le=840, description="Minutes east of UTC for the viewer, e.g. 330 for IST"),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    """
    Habit-style view of the practice: current streak, 28-day strip, average
    before/after change, today's session and a few recent reflections.
    Days are bucketed in the viewer's local time (tz_offset) so a late-night
    reset counts for the right day.
    """
    offset = timedelta(minutes=tz_offset)
    today = (datetime.utcnow() + offset).date()
    # Local midnight 27 days ago, expressed in UTC for the query.
    window_start = datetime.combine(today - timedelta(days=27), datetime.min.time()) - offset

    completed = (
        db.query(models.CalmSession)
        .filter(models.CalmSession.user_id == user_id, models.CalmSession.completed_at.isnot(None))
        .order_by(models.CalmSession.started_at.desc())
        .all()
    )
    local_day = lambda s: (s.started_at + offset).date()
    completed_days = {local_day(s) for s in completed if s.started_at}

    # A streak survives until a whole day is missed, so it counts from yesterday if today is not done yet.
    streak = 0
    cursor = today if today in completed_days else today - timedelta(days=1)
    while cursor in completed_days:
        streak += 1
        cursor -= timedelta(days=1)

    window_sessions = (
        db.query(models.CalmSession)
        .filter(models.CalmSession.user_id == user_id, models.CalmSession.started_at >= window_start)
        .order_by(models.CalmSession.started_at.asc())
        .all()
    )
    by_day: dict = {}
    for s in window_sessions:
        if not s.started_at:
            continue
        info = by_day.setdefault(local_day(s), {"completed": False, "delta": None, "sessions": 0})
        info["sessions"] += 1
        if s.completed_at is not None:
            info["completed"] = True
        if s.mind_before is not None and s.mind_after is not None:
            delta = s.mind_before - s.mind_after
            info["delta"] = delta if info["delta"] is None else max(info["delta"], delta)

    last28 = []
    for i in range(27, -1, -1):
        d = today - timedelta(days=i)
        info = by_day.get(d, {"completed": False, "delta": None, "sessions": 0})
        last28.append({"date": d.strftime("%Y-%m-%d"), "completed": info["completed"], "delta": info["delta"], "sessions": info["sessions"]})

    deltas = [s.mind_before - s.mind_after for s in completed if s.mind_before is not None and s.mind_after is not None]
    avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else None

    total_sessions = db.query(func.count(models.CalmSession.id)).filter(models.CalmSession.user_id == user_id).scalar() or 0

    today_session = next((s for s in reversed(window_sessions) if s.started_at and local_day(s) == today), None)

    recent = [
        {
            "id": s.id,
            "date": local_day(s).strftime("%Y-%m-%d") if s.started_at else None,
            "delta": (s.mind_before - s.mind_after) if (s.mind_before is not None and s.mind_after is not None) else None,
            "mindBefore": s.mind_before,
            "mindAfter": s.mind_after,
            "note": s.note,
            "loopThought": s.loop_thought,
            "ruminationType": s.rumination_type,
            "personalized": bool(s.personalized),
        }
        for s in completed[:5]
    ]

    return {
        "success": True,
        "practice": PRACTICE_NAME,
        "stepSeconds": STEP_SECONDS,
        "energyBonus": CALM_ENERGY_BONUS,
        "streak": streak,
        "totalSessions": total_sessions,
        "completedSessions": len(completed),
        "avgDelta": avg_delta,
        "last28": last28,
        "today": _serialize(today_session) if today_session else None,
        "recent": recent,
    }
