"""Offline tests for the Focus Reset router (routers/focus.py): signals, plans, urges, check-ins."""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import get_db
from routers import focus
from routers.auth import verify_session

TEST_USER = "user-1"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    session.add(models.User(id=TEST_USER, email="t@example.com", password="x", name="Test", preferences={}))
    session.add(models.User(id="user-2", email="o@example.com", password="x", name="Other", preferences={}))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(focus.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    return TestClient(app)


def _entry(db, days_ago, stimulation=None, user_id=TEST_USER):
    entry = models.JournalEntry(user_id=user_id, content="<p>day</p>", date=datetime.utcnow() - timedelta(days=days_ago))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.add(models.FeedbackReport(journal_entry_id=entry.id, mood_score=6, grammar_score=8, stimulation_data=stimulation))
    db.commit()


def _scroll(load=2, tod="night", lost=True, after="guilt", displaced=("the gym",)):
    return {
        "behaviours": [{"behaviour": "late-night scrolling", "category": "social_media", "trigger": "boredom", "timeOfDay": tod, "lostControl": lost}],
        "cravingLanguage": True, "afterState": after, "lowMotivation": False, "sleepDisrupted": tod == "night", "displaced": list(displaced), "load": load,
    }


NONE = {"behaviours": [], "cravingLanguage": False, "afterState": "none", "lowMotivation": False, "sleepDisrupted": False, "displaced": [], "load": 0}


def test_overview_is_inactive_without_signals(client, db_session):
    _entry(db_session, 0, NONE)
    _entry(db_session, 1, None)  # analysed before the field existed
    _entry(db_session, 20, _scroll())  # old signal, outside the recent window
    _entry(db_session, 0, _scroll(load=3), user_id="user-2")  # someone else's
    data = client.get("/api/focus/overview").json()
    assert data["active"] is False
    assert data["signalDays"] == 1 and data["recentSignalDays"] == 0
    assert data["plan"] is None and len(data["days"]) == 28


def test_overview_summarises_recent_signals(client, db_session):
    _entry(db_session, 0, _scroll(load=3, displaced=("the gym", "the report")))
    _entry(db_session, 1, _scroll(load=2, tod="evening", lost=False, after="flat"))
    _entry(db_session, 2, {**_scroll(load=1), "behaviours": [{"behaviour": "Online shopping", "category": "shopping", "trigger": "stress", "timeOfDay": "afternoon", "lostControl": False}]})
    _entry(db_session, 3, NONE)
    data = client.get("/api/focus/overview").json()
    assert data["active"] is True
    assert data["signalDays"] == 3 and data["heavyDays"] == 1 and data["lostControlDays"] == 1
    assert data["topBehaviours"][0] == {"label": "late-night scrolling", "category": "social_media", "count": 2}
    assert {t["label"] for t in data["topTriggers"]} == {"boredom", "stress"}
    assert data["timeOfDay"] == {"night": 1, "evening": 1, "afternoon": 1}
    assert data["afterStates"] == {"guilt": 2, "flat": 1}
    assert data["displaced"] == ["the gym", "the report"]
    assert data["sleepDisruptedDays"] == 2
    assert data["days"][-1]["load"] == 3 and data["days"][-4]["load"] == 0 and data["days"][-4]["analysed"] is True


def test_plan_lifecycle_with_checkins_and_urges(client, db_session):
    res = client.post("/api/focus/plans?tz_offset=330", json={
        "behaviour": "late-night scrolling", "category": "social_media", "objectives": "winding down",
        "problems": "sleep, mornings", "abstinenceDays": 7, "rules": ["phone charges in the kitchen", ""], "replacements": ["read", "stretch"],
    })
    assert res.status_code == 200
    plan = res.json()["plan"]
    assert plan["status"] == "active" and plan["dayNumber"] == 1 and plan["daysLeft"] == 7 and plan["finished"] is False
    assert plan["rules"] == ["phone charges in the kitchen"] and plan["cleanStreak"] == 0

    # a second plan replaces the first
    res2 = client.post("/api/focus/plans", json={"behaviour": "gaming", "abstinenceDays": 14})
    second = res2.json()["plan"]
    assert second["id"] != plan["id"]
    first_row = db_session.get(models.FocusPlan, plan["id"])
    assert first_row.status == "abandoned" and first_row.completed_at is not None
    assert client.get("/api/focus/overview").json()["plan"]["id"] == second["id"]

    # urges attach to the active plan
    client.post("/api/focus/urges", json={"intensity": 4, "acted": False, "trigger": "bored"})
    client.post("/api/focus/urges", json={"intensity": 2, "acted": True})
    today = datetime.utcnow().date().isoformat()
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

    # check-ins upsert per day; yesterday is before the plan start so it is rejected
    assert client.post("/api/focus/checkins", json={"date": yesterday, "urges": 1}).status_code == 422
    res = client.post("/api/focus/checkins", json={"date": today, "urges": 3, "gaveIn": False, "sleepOk": True, "note": "ok"})
    updated = res.json()["plan"]
    assert updated["cleanStreak"] == 1 and updated["cleanDays"] == 1 and updated["checkedInDays"] == 1
    assert updated["urges"] == {"total": 2, "surfed": 1, "recent": updated["urges"]["recent"]}
    res = client.post("/api/focus/checkins", json={"date": today, "urges": 5, "gaveIn": True})
    updated = res.json()["plan"]
    assert updated["cleanStreak"] == 0 and updated["cleanDays"] == 0 and updated["checkedInDays"] == 1

    # extending is allowed, shrinking is not; completion is recorded
    assert client.patch(f"/api/focus/plans/{second['id']}", json={"abstinenceDays": 7}).status_code == 422
    assert client.patch(f"/api/focus/plans/{second['id']}", json={"abstinenceDays": 30}).json()["plan"]["abstinenceDays"] == 30
    done = client.patch(f"/api/focus/plans/{second['id']}", json={"status": "completed"}).json()["plan"]
    assert done["status"] == "completed" and done["completedAt"]
    data = client.get("/api/focus/overview").json()
    assert data["plan"] is None and data["lastPlan"]["behaviour"] == "gaming" and data["lastPlan"]["status"] == "completed"
    assert client.post("/api/focus/checkins", json={"date": today, "urges": 0}).status_code == 409


def test_plan_progress_after_the_window(client, db_session):
    start = (datetime.utcnow().date() - timedelta(days=8)).isoformat()
    plan = client.post("/api/focus/plans", json={"behaviour": "gaming", "abstinenceDays": 7, "startDate": start}).json()["plan"]
    assert plan["dayNumber"] == 9 and plan["daysLeft"] == 0 and plan["finished"] is True
    for i in builtins_range(3):
        day = (datetime.utcnow().date() - timedelta(days=i)).isoformat()
        client.post("/api/focus/checkins", json={"date": day, "urges": 1, "gaveIn": False})
    assert client.get("/api/focus/overview").json()["plan"]["cleanStreak"] == 3
    assert client.post("/api/focus/plans", json={"behaviour": "x", "abstinenceDays": 9}).status_code == 422
    assert client.patch("/api/focus/plans/nope", json={"status": "completed"}).status_code == 404


def builtins_range(n):
    return range(n)


# ---------------------------------------------------------------- mind fitness

def _fog(minutes=90, short=True, builders=(), rot=2, note="could not focus on the report"):
    return {"fogOrAttention": True, "attentionNote": note, "passiveConsumptionMinutes": minutes, "shortFormVideo": short, "builders": list(builders), "brainRotLoad": rot}


def _clear(builders=()):
    return {"fogOrAttention": False, "attentionNote": "", "passiveConsumptionMinutes": 0, "shortFormVideo": False, "builders": list(builders), "brainRotLoad": 0}


def _entry_cog(db, days_ago, cognition, user_id=TEST_USER):
    entry = models.JournalEntry(user_id=user_id, content="<p>day</p>", date=datetime.utcnow() - timedelta(days=days_ago))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.add(models.FeedbackReport(journal_entry_id=entry.id, mood_score=6, grammar_score=8, stimulation_data=NONE, cognition_data=cognition))
    db.commit()


def test_mind_inactive_without_signals_but_reports_builders(client, db_session):
    _entry_cog(db_session, 0, _clear(builders=("exercise", "deep_reading")))
    _entry_cog(db_session, 1, _clear())
    data = client.get("/api/focus/overview").json()
    mind = data["mind"]
    assert data["active"] is False and mind["active"] is False
    assert mind["fogDays"] == 0 and mind["shortFormDays"] == 0 and mind["avgMinutes"] is None
    assert mind["builders"]["exercise"] == {"weekDays": 1, "monthDays": 1, "target": 3}
    assert mind["weekScore"] == round((1 + 1) / sum(focus.WEEK_TARGETS.values()) * 100)
    assert mind["days"][-1]["builders"] == ["deep_reading", "exercise"] and mind["guide"] is None


def test_mind_active_on_fog_and_short_form(client, db_session):
    _entry_cog(db_session, 0, _fog(minutes=120, rot=3, note="reread the same page three times"))
    _entry_cog(db_session, 1, _fog(minutes=60, rot=2))
    _entry_cog(db_session, 2, _clear(builders=("nature",)))
    _entry_cog(db_session, 20, _fog())  # outside the recent window, still counted in the month
    data = client.get("/api/focus/overview").json()
    mind = data["mind"]
    assert data["active"] is True and mind["active"] is True
    assert mind["fogDays"] == 3 and mind["recentFogDays"] == 2 and mind["shortFormDays"] == 3
    assert mind["rotDays"] == 3 and mind["heavyRotDays"] == 1
    assert mind["avgMinutes"] == 90 and mind["totalMinutes"] == 270
    assert mind["notes"][-1] == "reread the same page three times"
    assert mind["days"][-1]["rot"] == 3 and mind["days"][-1]["fog"] is True


def test_builder_toggle_merges_with_entries_and_validates(client, db_session):
    _entry_cog(db_session, 0, _clear(builders=("exercise",)))
    today = datetime.utcnow().date().isoformat()
    assert client.post("/api/focus/mind/builders", json={"date": today, "builder": "juggling"}).status_code == 422
    future = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    assert client.post("/api/focus/mind/builders", json={"date": future, "builder": "sleep"}).status_code == 422

    assert client.post("/api/focus/mind/builders", json={"date": today, "builder": "sleep"}).json()["done"] is True
    client.post("/api/focus/mind/builders", json={"date": today, "builder": "sleep"})  # idempotent
    mind = client.get("/api/focus/overview").json()["mind"]
    assert mind["days"][-1]["builders"] == ["exercise", "sleep"] and mind["days"][-1]["manual"] == ["sleep"]
    assert mind["builders"]["sleep"]["weekDays"] == 1 and db_session.query(models.MindLog).count() == 1

    client.post("/api/focus/mind/builders", json={"date": today, "builder": "sleep", "done": False})
    mind = client.get("/api/focus/overview").json()["mind"]
    assert mind["days"][-1]["builders"] == ["exercise"] and db_session.query(models.MindLog).count() == 0


def test_guide_start_and_stop(client, db_session):
    data = client.post("/api/focus/mind/guide?tz_offset=330", json={"action": "start"}).json()
    assert data["guide"]["day"] == 1 and data["guide"]["week"] == 1 and data["guide"]["finished"] is False
    overview = client.get("/api/focus/overview?tz_offset=330").json()
    assert overview["active"] is True and overview["mind"]["guide"]["startDate"] == data["guide"]["startDate"]

    # a guide started 22 days ago is in week 4; 29 days ago is finished
    user = db_session.get(models.User, TEST_USER)
    user.preferences = {"mind_guide": {"startDate": (datetime.utcnow().date() - timedelta(days=21)).isoformat()}}
    db_session.commit()
    assert client.get("/api/focus/overview").json()["mind"]["guide"]["week"] == 4
    user.preferences = {"mind_guide": {"startDate": (datetime.utcnow().date() - timedelta(days=28)).isoformat()}}
    db_session.commit()
    assert client.get("/api/focus/overview").json()["mind"]["guide"]["finished"] is True

    assert client.post("/api/focus/mind/guide", json={"action": "stop"}).json()["guide"] is None
    assert client.get("/api/focus/overview").json()["mind"]["guide"] is None
    assert client.post("/api/focus/mind/guide", json={"action": "pause"}).status_code == 422


def test_entry_builders_can_be_excluded_and_restored(client, db_session):
    _entry_cog(db_session, 0, _clear(builders=("exercise",)))
    today = datetime.utcnow().date().isoformat()
    day = client.get("/api/focus/overview").json()["mind"]["days"][-1]
    assert day["fromEntry"] == ["exercise"] and day["builders"] == ["exercise"] and day["excluded"] == []
    res = client.post("/api/focus/mind/builders", json={"date": today, "builder": "exercise", "done": False}).json()
    assert res["fromEntry"] is True
    mind = client.get("/api/focus/overview").json()["mind"]
    assert mind["days"][-1]["builders"] == [] and mind["days"][-1]["excluded"] == ["exercise"]
    assert mind["builders"]["exercise"]["weekDays"] == 0 and mind["weekBuilderDays"] == 0
    client.post("/api/focus/mind/builders", json={"date": today, "builder": "exercise", "done": True})
    day = client.get("/api/focus/overview").json()["mind"]["days"][-1]
    assert day["builders"] == ["exercise"] and day["excluded"] == [] and day["manual"] == []
    assert db_session.query(models.MindLog).count() == 0


def test_builder_backfill_for_a_past_day(client, db_session):
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
    client.post("/api/focus/mind/builders", json={"date": yesterday, "builder": "nature"})
    mind = client.get("/api/focus/overview").json()["mind"]
    assert mind["days"][-2]["date"] == yesterday and mind["days"][-2]["builders"] == ["nature"]
    assert mind["builders"]["nature"]["weekDays"] == 1
    too_old = (datetime.utcnow().date() - timedelta(days=28)).isoformat()
    assert client.post("/api/focus/mind/builders", json={"date": too_old, "builder": "nature"}).status_code == 422


def test_week_blocks_and_guide_weeks(client, db_session):
    for days_ago in (0, 1, 2):
        _entry_cog(db_session, days_ago, _fog())
    _entry_cog(db_session, 8, _clear(builders=("exercise",)))
    _entry_cog(db_session, 22, _fog())
    weeks = client.get("/api/focus/overview").json()["mind"]["weeks"]
    assert [w["week"] for w in weeks] == [1, 2, 3, 4] and all(w["days"] == 7 for w in weeks)
    assert weeks[3]["fogDays"] == 3 and weeks[2]["builderDays"] == 1 and weeks[0]["fogDays"] == 1 and weeks[1]["analysedDays"] == 0
    # a guide that started 21 days ago is in week 4; its last block holds today alone
    user = db_session.get(models.User, TEST_USER)
    user.preferences = {"mind_guide": {"startDate": (datetime.utcnow().date() - timedelta(days=21)).isoformat()}}
    db_session.commit()
    guide = client.get("/api/focus/overview").json()["mind"]["guide"]
    assert guide["week"] == 4 and len(guide["weeks"]) == 4 and guide["weeks"][3]["days"] == 1
    assert guide["weeks"][3]["fogDays"] == 1 and guide["weeks"][0]["fogDays"] == 0 and guide["weeks"][1]["builderDays"] == 1


def test_hide_focus_preference_switches_everything_off(client, db_session):
    _entry_cog(db_session, 0, _fog())
    _entry_cog(db_session, 1, _fog())
    assert client.get("/api/focus/overview").json()["active"] is True
    user = db_session.get(models.User, TEST_USER)
    user.preferences = {"hide_focus": True}
    db_session.commit()
    data = client.get("/api/focus/overview").json()
    assert data["hidden"] is True and data["active"] is False and data["mind"]["active"] is False
    assert data["mind"]["fogDays"] == 2  # still computed, for when it is switched back on
