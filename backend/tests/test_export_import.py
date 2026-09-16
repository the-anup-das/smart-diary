"""Offline tests for export and import (routers/users.py): feedback signals, focus plans, urges, check-ins, mind logs, preferences."""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import get_db
from routers import focus, users
from routers.auth import verify_session

USER_A = "user-a"
USER_B = "user-b"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    session.add(models.User(id=USER_A, email="a@example.com", password="x", name="A", preferences={"hide_mood": False}))
    session.add(models.User(id=USER_B, email="b@example.com", password="x", name="B", preferences={"hide_mood": True}))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def make_client(db_session):
    def _make(user_id: str) -> TestClient:
        app = FastAPI()
        app.include_router(users.router)
        app.include_router(focus.router)
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[verify_session] = lambda: user_id
        return TestClient(app)
    return _make


STIM = {"behaviours": [{"behaviour": "gaming", "category": "gaming", "trigger": "boredom", "timeOfDay": "night", "lostControl": True}],
        "cravingLanguage": False, "afterState": "flat", "lowMotivation": False, "sleepDisrupted": True, "displaced": [], "load": 2}
COG = {"fogOrAttention": True, "attentionNote": "could not focus", "passiveConsumptionMinutes": 45, "shortFormVideo": True, "builders": ["exercise"], "brainRotLoad": 2}


def test_export_and_import_round_trip(db_session, make_client):
    a = make_client(USER_A)
    entry = models.JournalEntry(user_id=USER_A, content="<p>played too long</p>", date=datetime.utcnow())
    db_session.add(entry)
    db_session.flush()
    db_session.add(models.FeedbackReport(journal_entry_id=entry.id, mood_score=4, sentiment="Flat", grammar_score=7,
                                         energy_data={"battery_level": 40}, stimulation_data=STIM, cognition_data=COG))
    db_session.commit()
    today = datetime.utcnow().date().isoformat()
    plan = a.post("/api/focus/plans", json={"behaviour": "gaming", "category": "gaming", "abstinenceDays": 7, "rules": ["timer first"]}).json()["plan"]
    a.post("/api/focus/checkins", json={"date": today, "urges": 2, "gaveIn": False, "sleepOk": True})
    a.post("/api/focus/urges", json={"intensity": 3, "acted": False, "trigger": "bored"})
    a.post("/api/focus/mind/builders", json={"date": today, "builder": "sleep"})
    a.post("/api/focus/mind/builders", json={"date": today, "builder": "exercise", "done": False})  # exclusion of an entry-derived builder
    a.post("/api/focus/mind/guide", json={"action": "start"})

    export = a.get("/api/users/export").json()
    assert export["preferences"]["mind_guide"]["startDate"] == today
    fb = export["entries"][0]["feedback"]
    assert fb["stimulationData"]["load"] == 2 and fb["cognitionData"]["brainRotLoad"] == 2 and fb["energyData"]["battery_level"] == 40
    assert export["focusPlans"][0]["behaviour"] == "gaming" and export["focusPlans"][0]["rules"] == ["timer first"]
    assert export["focusPlans"][0]["checkins"][0]["urges"] == 2 and export["focusPlans"][0]["checkins"][0]["sleep_ok"] is True
    assert export["focusUrges"][0]["plan_id"] == plan["id"] and export["focusUrges"][0]["trigger"] == "bored"
    assert sorted((m["builder"], m["source"]) for m in export["mindLogs"]) == [("exercise", "exclude"), ("sleep", "manual")]

    b = make_client(USER_B)
    res = b.post("/api/users/import", json=export)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["focus_plans_imported"] == 1 and body["focus_urges_imported"] == 1 and body["mind_logs_imported"] == 2

    ov = b.get("/api/focus/overview").json()
    assert ov["signalDays"] == 1 and ov["mind"]["fogDays"] == 1  # the signals travelled with the entry
    assert ov["plan"]["behaviour"] == "gaming" and ov["plan"]["checkedInDays"] == 1 and ov["plan"]["urges"]["total"] == 1
    assert ov["mind"]["days"][-1]["builders"] == ["sleep"] and ov["mind"]["days"][-1]["excluded"] == ["exercise"]
    assert ov["mind"]["guide"]["startDate"] == today
    prefs = db_session.get(models.User, USER_B).preferences
    assert prefs["hide_mood"] is True and prefs["mind_guide"]["startDate"] == today  # own choice kept, missing key filled

    # importing the same backup again neither duplicates mind logs nor leaves two active plans
    again = b.post("/api/users/import", json=export).json()
    assert again["mind_logs_imported"] == 0
    statuses = sorted(p.status for p in db_session.query(models.FocusPlan).filter(models.FocusPlan.user_id == USER_B).all())
    assert statuses == ["abandoned", "active"]
    assert db_session.query(models.MindLog).filter(models.MindLog.user_id == USER_B).count() == 2


def test_import_accepts_an_old_backup_without_the_new_sections(db_session, make_client):
    b = make_client(USER_B)
    old = {"profile": {"name": "B", "email": "b@example.com"}, "entries": [{"id": "e1", "date": datetime.utcnow().isoformat(), "content": "<p>hi</p>", "feedback": {"moodScore": 6}}], "openLoops": []}
    res = b.post("/api/users/import", json=old)
    assert res.status_code == 200 and res.json()["entries_imported"] == 1 and res.json()["mind_logs_imported"] == 0
    assert db_session.get(models.User, USER_B).preferences == {"hide_mood": True}
