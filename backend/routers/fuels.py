"""
Four Fuels: a week of entries read as the four drives behind mood and motivation, with one
small act per fuel that ran low.

The model does the judging. Once a day, or when a new entry lands, it reads the week's entries
and returns observations in a fixed vocabulary: which fuel, fed or drained, which kind of
thing, and the words in the entry that show it. Those observations are cached in the user's
preferences and become the gauges. When no model is reachable, or AI is paused, the gauges are
built from the analysis signals already stored per entry (builders, stimulation, mood, rumination,
emotion labels), and the card says so. The maths lives in fuels.py; this file buckets entries by
local day, calls the model, remembers challenges, and lets a done challenge count towards Mind
Fitness.
"""
import os
import re
from datetime import date as date_type, datetime, timedelta
from typing import Literal, Optional

import openai
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

import models
from database import get_db
from fuels import CHALLENGE_BY_ID, FUELS, TAGS, build_fuels, evidence_from_feedback, evidence_from_observations, merge_evidence
from routers.focus import WEEK_TARGETS

from .auth import verify_session

router = APIRouter()

WINDOW_DAYS = 7
KEEP_DAYS = 28          # how long done challenges are remembered in the preferences blob
PREF_KEY = "fuel_challenges"
CACHE_KEY = "fuels_judgement"
MAX_ENTRY_CHARS = 1600  # per entry, into the judging prompt

_client: Optional[openai.OpenAI] = None


def _get_client() -> openai.OpenAI:
    """Lazy client so importing this module never requires an API key (tests, evals)."""
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL", None))
    return _client


# ---------------------------------------------------------------- the model's judgement

_ALL_TAGS = sorted({tag for fuel in TAGS.values() for side in fuel.values() for tag in side})


class FuelObservation(BaseModel):
    date: str = Field(description="The entry's date exactly as given in the heading, YYYY-MM-DD.")
    fuel: Literal["drive", "bond", "calm", "spark"]
    effect: Literal["fed", "drained"]
    tag: Literal[tuple(_ALL_TAGS)]  # type: ignore[valid-type]
    reason: str = Field(description="What in the entry shows it, in the writer's own terms, under 20 words.")


class FuelJudgement(BaseModel):
    observations: list[FuelObservation] = Field(description="Only what the entries actually say. Skip a fuel on a day when the entry says nothing about it.")
    headline: str = Field(description="One sentence, under 20 words, on the week's fuel balance, written to the writer as 'you'.")


def _judging_prompt() -> str:
    lines = [
        "You read a week of someone's diary entries and judge four fuels, the drives behind mood and motivation:",
    ]
    for f in FUELS:
        lines.append(f"- {f['label']} ({f['chemical']}): fed by {f['fedBy']}; drained by {f['drainedBy']}.")
    lines.append("")
    lines.append("For every entry, record what fed or drained each fuel, using only these tags:")
    for fuel, sides in TAGS.items():
        for side, tags in sides.items():
            for tag, meaning in tags.items():
                lines.append(f"- {fuel} {side} `{tag}`: {meaning}")
    lines += [
        "",
        "Rules: report only what the entry says or clearly describes, never what you infer about the person.",
        "One observation per tag per entry at most. A day with nothing about a fuel gets no observation for it.",
        "'reason' quotes or closely paraphrases the entry. Copy the date from the heading exactly.",
    ]
    return "\n".join(lines)


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>?", " ", html or "")).strip()


def judge_week(day_texts: list[tuple[str, str]]) -> Optional[FuelJudgement]:
    """Ask the model for its observations on the week. None when it cannot answer, so the caller falls back."""
    if not day_texts:
        return None
    digest = "\n\n".join(f"### {date}\n{text[:MAX_ENTRY_CHARS]}" for date, text in day_texts)
    try:
        response = _get_client().beta.chat.completions.parse(
            model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": _judging_prompt()},
                {"role": "user", "content": "The entries, one heading per day:\n\n" + digest},
            ],
            response_format=FuelJudgement,
            temperature=0.1,
        )
        return response.choices[0].message.parsed
    except Exception:  # noqa: BLE001  any failure means "no judgement", never a broken card
        return None


# ---------------------------------------------------------------- days

def _local_today(tz_offset: int) -> date_type:
    return (datetime.utcnow() + timedelta(minutes=tz_offset)).date()


def _entries_by_day(user_id: str, db: Session, tz_offset: int, start_day: date_type, end_day: date_type) -> dict[str, list]:
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
        .order_by(models.JournalEntry.date.asc())
        .all()
    )
    by_day: dict[str, list] = {}
    for e in entries:
        by_day.setdefault((e.date + offset).date().isoformat(), []).append(e)
    return by_day


def _days_from_signals(by_day: dict[str, list], start_day: date_type, end_day: date_type, done: dict) -> list[dict]:
    """The fallback: per local day, the union of the stored analysis signals of that day's entries."""
    days = []
    day = start_day
    while day <= end_day:
        key = day.isoformat()
        analysed = [e for e in by_day.get(key, []) if e.feedback is not None]
        evidence = merge_evidence(evidence_from_feedback(e.feedback) for e in analysed)
        days.append(_with_challenges({"date": key, "analysed": bool(analysed), "evidence": evidence}, done))
        day += timedelta(days=1)
    return days


def _days_from_observations(observations, by_day: dict[str, list], start_day: date_type, end_day: date_type, done: dict) -> list[dict]:
    """The model's observations, one record per local day with an entry."""
    dates = []
    day = start_day
    while day <= end_day:
        dates.append(day.isoformat())
        day += timedelta(days=1)
    per_date = evidence_from_observations(observations, dates)
    return [_with_challenges({"date": d, "analysed": bool(by_day.get(d)), "evidence": per_date[d]}, done) for d in dates]


def _with_challenges(day: dict, done: dict) -> dict:
    for cid in done.get(day["date"], []):
        c = CHALLENGE_BY_ID.get(cid)
        if c:
            day["evidence"][c["fuel"]]["fed"].append(("challenge", f"did the challenge: {c['text'].rstrip('.')}"))
            day["analysed"] = True
    return day


def _done_challenges(user: models.User) -> dict[str, list[str]]:
    raw = (user.preferences or {}).get(PREF_KEY) or {}
    return {d: [c for c in ids if c in CHALLENGE_BY_ID] for d, ids in raw.items() if isinstance(ids, list)}


def _judgement_for(user: models.User, db: Session, by_day: dict[str, list], today: date_type, refresh: bool) -> tuple[Optional[list], Optional[str], bool]:
    """(observations, headline, cached) from the cache or the model; (None, None, False) when the rules must do it."""
    prefs = user.preferences or {}
    if prefs.get("pause_ai"):
        return None, None, False
    day_texts = [(d, " ".join(_strip(e.content) for e in entries)) for d, entries in sorted(by_day.items())]
    day_texts = [(d, t) for d, t in day_texts if t]
    if not day_texts:
        return None, None, False
    cache_key = f"{today.isoformat()}:{sum(len(v) for v in by_day.values())}"
    cached = prefs.get(CACHE_KEY)
    if cached and cached.get("key") == cache_key and not refresh:
        return cached.get("observations") or [], cached.get("headline"), True
    judgement = judge_week(day_texts)
    if judgement is None:
        return None, None, False
    observations = [o.model_dump() for o in judgement.observations]
    prefs = dict(prefs)
    prefs[CACHE_KEY] = {"key": cache_key, "observations": observations, "headline": judgement.headline, "model": os.getenv("CHAT_MODEL", "gpt-4o-mini")}
    user.preferences = prefs
    flag_modified(user, "preferences")
    db.commit()
    return observations, judgement.headline, False


@router.get("/api/insights/fuels")
def get_fuels(
    tz_offset: int = Query(default=0, ge=-840, le=840, description="Minutes east of UTC, so days are the person's days"),
    refresh: bool = Query(default=False, description="Ask the model again instead of using today's cached judgement"),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db),
):
    """The last seven local days read as four fuels, judged by the model, with the seven before for the trend."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    done = _done_challenges(user)
    today = _local_today(tz_offset)
    start, prev_start, prev_end = today - timedelta(days=WINDOW_DAYS - 1), today - timedelta(days=2 * WINDOW_DAYS - 1), today - timedelta(days=WINDOW_DAYS)
    by_day = _entries_by_day(user_id, db, tz_offset, start, today)
    prev_by_day = _entries_by_day(user_id, db, tz_offset, prev_start, prev_end)

    observations, model_headline, cached = _judgement_for(user, db, by_day, today, refresh)
    if observations is not None:
        # The model's observations may include last week's days too when they were in an earlier cache;
        # the previous week is always read from the stored signals, which is enough for a trend arrow.
        days = _days_from_observations(observations, by_day, start, today, done)
        source = {"kind": "model", "model": ((user.preferences or {}).get(CACHE_KEY) or {}).get("model"), "cached": cached}
    else:
        days = _days_from_signals(by_day, start, today, done)
        source = {"kind": "signals", "model": None, "cached": False}
    previous = _days_from_signals(prev_by_day, prev_start, prev_end, done)

    body = build_fuels(days, previous, set(done.get(today.isoformat(), [])), today.isoformat())
    if model_headline:
        body["headline"] = model_headline
    body["source"] = source
    return body


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
