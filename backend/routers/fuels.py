"""
Four Fuels: a week of entries read as the four drives behind mood and motivation, with one
small act per fuel that ran low. The maths lives in fuels.py; this file buckets entries by local
day, remembers which challenges were done, and lets a done challenge count towards Mind Fitness.
"""
from datetime import date as date_type, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

import models
from database import get_db
from fuels import CHALLENGE_BY_ID, build_fuels, evidence_from_feedback, merge_evidence
from routers.focus import WEEK_TARGETS

from .auth import verify_session

router = APIRouter()

WINDOW_DAYS = 7
KEEP_DAYS = 28          # how long done challenges are remembered in the preferences blob
PREF_KEY = "fuel_challenges"


def _local_today(tz_offset: int) -> date_type:
    return (datetime.utcnow() + timedelta(minutes=tz_offset)).date()


def _days(user_id: str, db: Session, tz_offset: int, start_day: date_type, end_day: date_type, done: dict) -> list[dict]:
    """Per local day, oldest first: the union of the evidence in that day's analysed entries, plus challenges done that day."""
    offset = timedelta(minutes=tz_offset)
    window_start = datetime.combine(start_day, datetime.min.time()) - offset
    window_end = datetime.combine(end_day + timedelta(days=1), datetime.min.time()) - offset
    entries = (
        db.query(models.JournalEntry)
        .options(joinedload(models.JournalEntry.feedback))
        .filter(
            models.JournalEntry.user_id == user_id,
            models.JournalEntry.is_deleted == False,  # noqa: E712
            models.JournalEntry.date >= window_start,
            models.JournalEntry.date < window_end,
        )
        .all()
    )
    by_day: dict[str, list[dict]] = {}
    for e in entries:
        if e.feedback is None:
            continue
        local = (e.date + offset).date().isoformat()
        by_day.setdefault(local, []).append(evidence_from_feedback(e.feedback))

    days = []
    day = start_day
    while day <= end_day:
        key = day.isoformat()
        evidence = merge_evidence(by_day.get(key, []))
        for cid in done.get(key, []):
            c = CHALLENGE_BY_ID.get(cid)
            if c:
                evidence[c["fuel"]]["fed"].append(("challenge", f"did the challenge: {c['text'].rstrip('.')}"))
        analysed = key in by_day or bool(done.get(key))
        days.append({"date": key, "analysed": analysed, "evidence": evidence})
        day += timedelta(days=1)
    return days


def _done_challenges(user: models.User) -> dict[str, list[str]]:
    raw = (user.preferences or {}).get(PREF_KEY) or {}
    return {d: [c for c in ids if c in CHALLENGE_BY_ID] for d, ids in raw.items() if isinstance(ids, list)}


@router.get("/api/insights/fuels")
def get_fuels(
    tz_offset: int = Query(default=0, ge=-840, le=840, description="Minutes east of UTC, so days are the person's days"),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    """The last seven local days read as four fuels, with the seven before them for the trend."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    done = _done_challenges(user) if user else {}
    today = _local_today(tz_offset)
    days = _days(user_id, db, tz_offset, today - timedelta(days=WINDOW_DAYS - 1), today, done)
    previous = _days(user_id, db, tz_offset, today - timedelta(days=2 * WINDOW_DAYS - 1), today - timedelta(days=WINDOW_DAYS), done)
    return build_fuels(days, previous, set(done.get(today.isoformat(), [])), today.isoformat())


class ChallengeToggle(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    done: bool


@router.post("/api/insights/fuels/challenge")
def toggle_challenge(
    data: ChallengeToggle,
    tz_offset: int = Query(default=0, ge=-840, le=840),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    """Tick or untick a challenge for a day. A done challenge feeds its fuel on that day and, when it
    matches a Mind Fitness activity, counts there too."""
    challenge = CHALLENGE_BY_ID.get(data.id)
    if challenge is None:
        raise HTTPException(status_code=422, detail=f"unknown challenge {data.id!r}")
    try:
        day = date_type.fromisoformat(data.date)
    except ValueError:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")
    today = _local_today(tz_offset)
    if day > today or day < today - timedelta(days=KEEP_DAYS - 1):
        raise HTTPException(status_code=422, detail="date must be within the last four weeks and not in the future")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    prefs = dict(user.preferences or {})
    done = {d: list(ids) for d, ids in (prefs.get(PREF_KEY) or {}).items() if isinstance(ids, list)}
    ids = [c for c in done.get(data.date, []) if c != data.id]
    if data.done:
        ids.append(data.id)
    done[data.date] = ids
    cutoff = (today - timedelta(days=KEEP_DAYS - 1)).isoformat()
    prefs[PREF_KEY] = {d: v for d, v in done.items() if v and d >= cutoff}
    user.preferences = prefs
    flag_modified(user, "preferences")

    builder = challenge["builder"]
    if builder in WEEK_TARGETS:
        rows = db.query(models.MindLog).filter(
            models.MindLog.user_id == user_id, models.MindLog.date == data.date, models.MindLog.builder == builder,
        ).all()
        manual = [r for r in rows if r.source != "exclude"]
        if data.done and not manual:
            db.add(models.MindLog(user_id=user_id, date=data.date, builder=builder, source="challenge"))
        if not data.done:
            for r in manual:
                if r.source == "challenge":
                    db.delete(r)
    db.commit()
    return {"success": True, "id": data.id, "date": data.date, "done": data.done, "fuel": challenge["fuel"], "builder": builder}
