"""
focus.py - the Focus Reset: help with compulsive, high-stimulation habits.

Nothing here is shown unless the person's own entries carry a signal. The analysis
(routers/analyze.py) records reward-seeking behaviours an entry mentions: what, the
trigger, time of day, loss of control, the after-state and what was displaced. This
router turns those per-entry records into a 28-day picture and runs a guided programme
modelled on Anna Lembke's "DOPAMINE" structure (Data, Objectives, Problems, Abstinence,
Mindfulness, Insight, Next steps, Experiment) and Cameron Sepah's stimulus-control
"dopamine fasting": pick one behaviour, an abstinence window, self-binding rules and
replacement activities, then track urges and daily check-ins.

The app measures behaviour described in writing, never dopamine itself; the popular
name is used only because it is what people search for.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, date as date_type
from typing import Literal, Optional
from pydantic import BaseModel, Field
from database import get_db
import models
from .auth import verify_session
import builtins

router = APIRouter(tags=["focus"])

WINDOW_DAYS = 28
RECENT_DAYS = 14
ABSTINENCE_OPTIONS = (7, 14, 30)


def _local_today(tz_offset: int) -> date_type:
    return (datetime.utcnow() + timedelta(minutes=tz_offset)).date()


def _parse_day(value: str) -> date_type:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")


# --------------------------------------------------------------------------
# Signals from entries
# --------------------------------------------------------------------------

def _signal_days(user_id: str, db: Session, tz_offset: int) -> list[dict]:
    """Per local day in the window: the stimulation record of that day's entry, if any."""
    offset = timedelta(minutes=tz_offset)
    today = _local_today(tz_offset)
    window_start_utc = datetime.combine(today - timedelta(days=WINDOW_DAYS - 1), datetime.min.time()) - offset
    entries = (
        db.query(models.JournalEntry)
        .options(joinedload(models.JournalEntry.feedback))
        .filter(
            models.JournalEntry.user_id == user_id,
            models.JournalEntry.is_deleted == False,
            models.JournalEntry.date >= window_start_utc,
        )
        .all()
    )
    by_day: dict = {}
    for e in entries:
        fb = e.feedback
        if not fb or not e.date:
            continue
        d = (e.date + offset).date()
        s = fb.stimulation_data or {}
        by_day[d] = {
            "analysed": True,
            "load": int(s.get("load") or 0),
            "behaviours": s.get("behaviours") or [],
            "afterState": s.get("afterState") or "none",
            "lowMotivation": bool(s.get("lowMotivation")),
            "sleepDisrupted": bool(s.get("sleepDisrupted")),
            "craving": bool(s.get("cravingLanguage")),
            "displaced": s.get("displaced") or [],
        }
    days = []
    for i in builtins.range(WINDOW_DAYS - 1, -1, -1):
        d = today - timedelta(days=i)
        info = by_day.get(d)
        days.append({"date": d.isoformat(), **(info or {"analysed": False, "load": 0, "behaviours": [], "afterState": "none", "lowMotivation": False, "sleepDisrupted": False, "craving": False, "displaced": []})})
    return days


def _summarise(days: list[dict]) -> dict:
    signal = [d for d in days if d["load"] >= 1]
    recent = [d for d in days[-RECENT_DAYS:] if d["load"] >= 1]
    behaviours: dict = {}
    triggers: dict = {}
    time_of_day: dict = {}
    after: dict = {}
    displaced: list[str] = []
    lost_control_days = 0
    for d in signal:
        lost = False
        for b in d["behaviours"]:
            label = str(b.get("behaviour") or "").strip().lower()
            if not label:
                continue
            key = label
            entry = behaviours.setdefault(key, {"label": label, "category": b.get("category") or "other", "count": 0})
            entry["count"] += 1
            trig = str(b.get("trigger") or "").strip().lower()
            if trig and trig != "unclear":
                triggers[trig] = triggers.get(trig, 0) + 1
            tod = b.get("timeOfDay") or "unknown"
            time_of_day[tod] = time_of_day.get(tod, 0) + 1
            if b.get("lostControl"):
                lost = True
        if lost:
            lost_control_days += 1
        if d["afterState"] and d["afterState"] != "none":
            after[d["afterState"]] = after.get(d["afterState"], 0) + 1
        for item in d["displaced"]:
            if item and item not in displaced:
                displaced.append(item)
    top_behaviours = sorted(behaviours.values(), key=lambda b: -b["count"])[:6]
    top_triggers = [{"label": k, "count": v} for k, v in sorted(triggers.items(), key=lambda kv: -kv[1])[:5]]
    return {
        "analysedDays": sum(1 for d in days if d["analysed"]),
        "signalDays": len(signal),
        "recentSignalDays": len(recent),
        "heavyDays": sum(1 for d in signal if d["load"] >= 3),
        "lostControlDays": lost_control_days,
        "lowMotivationDays": sum(1 for d in days if d["lowMotivation"]),
        "sleepDisruptedDays": sum(1 for d in days if d["sleepDisrupted"]),
        "topBehaviours": top_behaviours,
        "topTriggers": top_triggers,
        "timeOfDay": time_of_day,
        "afterStates": after,
        "displaced": displaced[-8:],
    }


# --------------------------------------------------------------------------
# Plans, urges, check-ins
# --------------------------------------------------------------------------

class PlanCreate(BaseModel):
    behaviour: str = Field(min_length=2, max_length=120)
    category: Optional[str] = "other"
    objectives: Optional[str] = Field(default=None, max_length=2000)
    problems: Optional[str] = Field(default=None, max_length=2000)
    abstinenceDays: int = 7
    startDate: Optional[str] = None  # YYYY-MM-DD local; defaults to today in tz_offset
    rules: list[str] = Field(default_factory=list)
    replacements: list[str] = Field(default_factory=list)


class PlanUpdate(BaseModel):
    status: Optional[Literal["active", "completed", "abandoned"]] = None
    abstinenceDays: Optional[int] = None
    objectives: Optional[str] = Field(default=None, max_length=2000)
    problems: Optional[str] = Field(default=None, max_length=2000)
    rules: Optional[list[str]] = None
    replacements: Optional[list[str]] = None


class UrgeCreate(BaseModel):
    intensity: Optional[int] = Field(default=None, ge=1, le=5)
    acted: bool = False
    trigger: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)


class CheckinUpsert(BaseModel):
    date: str
    urges: int = Field(default=0, ge=0, le=99)
    gaveIn: bool = False
    sleepOk: Optional[bool] = None
    note: Optional[str] = Field(default=None, max_length=1000)


def _active_plan(user_id: str, db: Session) -> Optional[models.FocusPlan]:
    return (
        db.query(models.FocusPlan)
        .filter(models.FocusPlan.user_id == user_id, models.FocusPlan.status == "active")
        .order_by(models.FocusPlan.created_at.desc())
        .first()
    )


def _serialize_plan(plan: models.FocusPlan, db: Session, tz_offset: int) -> dict:
    today = _local_today(tz_offset)
    start = _parse_day(plan.start_date)
    checkins = (
        db.query(models.FocusCheckin)
        .filter(models.FocusCheckin.plan_id == plan.id)
        .order_by(models.FocusCheckin.date.asc())
        .all()
    )
    urges = (
        db.query(models.FocusUrge)
        .filter(models.FocusUrge.plan_id == plan.id)
        .order_by(models.FocusUrge.logged_at.desc())
        .all()
    )
    by_date = {c.date: c for c in checkins}
    # Clean streak: consecutive checked-in days without giving in, counting back from today (or yesterday if today is unchecked).
    streak = 0
    cursor = today if today.isoformat() in by_date else today - timedelta(days=1)
    while cursor.isoformat() in by_date and not by_date[cursor.isoformat()].gave_in:
        streak += 1
        cursor -= timedelta(days=1)
    clean_days = sum(1 for c in checkins if not c.gave_in)
    day_number = (today - start).days + 1
    length = plan.abstinence_days or 7
    return {
        "id": plan.id,
        "behaviour": plan.behaviour,
        "category": plan.category,
        "objectives": plan.objectives,
        "problems": plan.problems,
        "abstinenceDays": length,
        "startDate": plan.start_date,
        "status": plan.status,
        "rules": plan.rules or [],
        "replacements": plan.replacements or [],
        "dayNumber": max(1, day_number),
        "daysLeft": max(0, length - day_number + 1),
        "finished": day_number > length,
        "cleanStreak": streak,
        "cleanDays": clean_days,
        "checkedInDays": len(checkins),
        "checkins": [
            {"date": c.date, "urges": c.urges or 0, "gaveIn": bool(c.gave_in), "sleepOk": c.sleep_ok, "note": c.note}
            for c in checkins
        ],
        "urges": {
            "total": len(urges),
            "surfed": sum(1 for u in urges if not u.acted),
            "recent": [
                {"id": u.id, "loggedAt": u.logged_at.isoformat() if u.logged_at else None, "intensity": u.intensity, "acted": bool(u.acted), "trigger": u.trigger, "note": u.note}
                for u in urges[:10]
            ],
        },
        "completedAt": plan.completed_at.isoformat() if plan.completed_at else None,
    }


@router.get("/api/focus/overview")
def get_overview(
    tz_offset: int = Query(default=0, ge=-840, le=840),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    """
    Everything the Focus pages need. `active` is false when the last two weeks of entries
    carry no stimulation signal and no plan is running, in which case the UI shows nothing.
    """
    days = _signal_days(user_id, db, tz_offset)
    summary = _summarise(days)
    plan = _active_plan(user_id, db)
    last_plan = None
    if not plan:
        previous = (
            db.query(models.FocusPlan)
            .filter(models.FocusPlan.user_id == user_id)
            .order_by(models.FocusPlan.created_at.desc())
            .first()
        )
        if previous:
            last_plan = {"behaviour": previous.behaviour, "status": previous.status, "completedAt": previous.completed_at.isoformat() if previous.completed_at else None}
    return {
        "success": True,
        "active": summary["recentSignalDays"] >= 1 or plan is not None,
        "windowDays": WINDOW_DAYS,
        "days": days,
        **summary,
        "plan": _serialize_plan(plan, db, tz_offset) if plan else None,
        "lastPlan": last_plan,
    }


@router.post("/api/focus/plans")
def create_plan(
    data: PlanCreate,
    tz_offset: int = Query(default=0, ge=-840, le=840),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    if data.abstinenceDays not in ABSTINENCE_OPTIONS:
        raise HTTPException(status_code=422, detail=f"abstinenceDays must be one of {ABSTINENCE_OPTIONS}")
    start = _parse_day(data.startDate) if data.startDate else _local_today(tz_offset)
    # One plan at a time: starting a new one closes the previous.
    for old in db.query(models.FocusPlan).filter(models.FocusPlan.user_id == user_id, models.FocusPlan.status == "active").all():
        old.status = "abandoned"
        old.completed_at = datetime.utcnow()
    plan = models.FocusPlan(
        user_id=user_id,
        behaviour=data.behaviour.strip(),
        category=data.category or "other",
        objectives=(data.objectives or "").strip() or None,
        problems=(data.problems or "").strip() or None,
        abstinence_days=data.abstinenceDays,
        start_date=start.isoformat(),
        status="active",
        rules=[r.strip() for r in data.rules if r.strip()][:12],
        replacements=[r.strip() for r in data.replacements if r.strip()][:12],
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"success": True, "plan": _serialize_plan(plan, db, tz_offset)}


@router.patch("/api/focus/plans/{plan_id}")
def update_plan(
    plan_id: str,
    data: PlanUpdate,
    tz_offset: int = Query(default=0, ge=-840, le=840),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    plan = db.query(models.FocusPlan).filter(models.FocusPlan.id == plan_id, models.FocusPlan.user_id == user_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if data.abstinenceDays is not None:
        if data.abstinenceDays not in ABSTINENCE_OPTIONS or data.abstinenceDays < (plan.abstinence_days or 0):
            raise HTTPException(status_code=422, detail="abstinenceDays can only extend the plan to 7, 14 or 30 days")
        plan.abstinence_days = data.abstinenceDays
    if data.objectives is not None:
        plan.objectives = data.objectives.strip() or None
    if data.problems is not None:
        plan.problems = data.problems.strip() or None
    if data.rules is not None:
        plan.rules = [r.strip() for r in data.rules if r.strip()][:12]
    if data.replacements is not None:
        plan.replacements = [r.strip() for r in data.replacements if r.strip()][:12]
    if data.status is not None and data.status != plan.status:
        plan.status = data.status
        plan.completed_at = datetime.utcnow() if data.status in ("completed", "abandoned") else None
    db.commit()
    db.refresh(plan)
    return {"success": True, "plan": _serialize_plan(plan, db, tz_offset)}


@router.post("/api/focus/urges")
def log_urge(data: UrgeCreate, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    plan = _active_plan(user_id, db)
    urge = models.FocusUrge(
        user_id=user_id,
        plan_id=plan.id if plan else None,
        intensity=data.intensity,
        acted=data.acted,
        trigger=(data.trigger or "").strip() or None,
        note=(data.note or "").strip() or None,
    )
    db.add(urge)
    db.commit()
    db.refresh(urge)
    return {"success": True, "urge": {"id": urge.id, "acted": urge.acted, "intensity": urge.intensity, "loggedAt": urge.logged_at.isoformat() if urge.logged_at else None, "planId": urge.plan_id}}


@router.post("/api/focus/checkins")
def upsert_checkin(
    data: CheckinUpsert,
    tz_offset: int = Query(default=0, ge=-840, le=840),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    plan = _active_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=409, detail="No active plan")
    day = _parse_day(data.date)
    if day < _parse_day(plan.start_date) or day > _local_today(tz_offset):
        raise HTTPException(status_code=422, detail="date must be within the plan and not in the future")
    checkin = db.query(models.FocusCheckin).filter(models.FocusCheckin.plan_id == plan.id, models.FocusCheckin.date == data.date).first()
    if not checkin:
        checkin = models.FocusCheckin(user_id=user_id, plan_id=plan.id, date=data.date)
        db.add(checkin)
    checkin.urges = data.urges
    checkin.gave_in = data.gaveIn
    checkin.sleep_ok = data.sleepOk
    checkin.note = (data.note or "").strip() or None
    db.commit()
    db.refresh(plan)
    return {"success": True, "plan": _serialize_plan(plan, db, tz_offset)}
