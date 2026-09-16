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
