"""
Tests for the Insights "patterns" block: 28-day heatmap, weekday rhythm and the
overthinking trend, bucketed in the viewer's local time. Offline, SQLite.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import get_db
from routers import insights
from routers.auth import verify_session

TEST_USER = "user-1"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    session.add(models.User(id=TEST_USER, email="t@example.com", password="x", name="Test", preferences={}))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(insights.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    return TestClient(app)


def _entry(db, when, mood=None, rumination=None, battery=None, analysed=True):
    entry = models.JournalEntry(user_id=TEST_USER, content="<p>words words words</p>", date=when)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    if analysed:
        energy = {}
        if rumination:
            energy["rumination_level"] = rumination
        if battery is not None:
            energy["battery_level"] = battery
        db.add(models.FeedbackReport(journal_entry_id=entry.id, mood_score=mood, grammar_score=7, energy_data=energy or None))
        db.commit()
    return entry


def _reset(db, when):
    db.add(models.CalmSession(user_id=TEST_USER, source="manual", started_at=when, completed_at=when + timedelta(minutes=3)))
    db.commit()


def test_last28_heatmap_and_overthinking_counts(client, db_session):
    now = datetime.utcnow()
    _entry(db_session, now, mood=8, rumination="low", battery=72.4)
    _entry(db_session, now - timedelta(days=1), mood=4, rumination="high")
    _entry(db_session, now - timedelta(days=2), mood=5, rumination="moderate")
    _entry(db_session, now - timedelta(days=3), analysed=False)          # written, never analysed
    _entry(db_session, now - timedelta(days=40), mood=9, rumination="low")  # outside the window
    _reset(db_session, now - timedelta(days=1))

    p = client.get("/api/insights?range=week").json()["patterns"]
    assert len(p["last28"]) == 28
    assert p["last28"][-1]["date"] == now.date().isoformat()
    today, yesterday, two_ago, three_ago = p["last28"][-1], p["last28"][-2], p["last28"][-3], p["last28"][-4]
    assert today["mood"] == 8 and today["battery"] == 72 and today["rumination"] == "low" and today["resetDone"] is False
    assert yesterday["rumination"] == "high" and yesterday["resetDone"] is True
    assert three_ago["hasEntry"] is True and three_ago["mood"] is None
    assert p["last28"][0]["hasEntry"] is False
    assert p["analysedDays"] == 4  # includes the entry outside the 28-day window

    ot = p["overthinking"]
    assert ot == {"analysedDays": 3, "loopingDays": 2, "highDays": 1, "resetDays": 1, "loopingDaysWithReset": 1}


def test_weekday_rhythm_buckets_by_local_weekday(client, db_session):
    now = datetime.utcnow()
    for i in range(14):
        _entry(db_session, now - timedelta(days=i), mood=3 if (now - timedelta(days=i)).weekday() == 0 else 8, rumination="high" if (now - timedelta(days=i)).weekday() == 0 else "low")
    p = client.get("/api/insights?range=month").json()["patterns"]
    days = {w["day"]: w for w in p["weekday"]}
    assert [w["day"] for w in p["weekday"]] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert days["Mon"]["entries"] == 2 and days["Mon"]["avgMood"] == 3.0 and days["Mon"]["avgCalm"] == 0
    assert days["Tue"]["avgMood"] == 8.0 and days["Tue"]["avgCalm"] == 100
    assert sum(w["entries"] for w in p["weekday"]) == 14


def test_tz_offset_shifts_days_and_streak(client, db_session):
    # 23:30 UTC yesterday is already "today" in IST (UTC+5:30)
    offset = timedelta(minutes=330)
    ist_today = (datetime.utcnow() + offset).date()
    when = datetime.combine(ist_today, datetime.min.time()) - offset + timedelta(minutes=1)
    _entry(db_session, when, mood=7, rumination="low")

    ist = client.get("/api/insights?range=week&tz_offset=330").json()
    assert ist["patterns"]["today"] == ist_today.isoformat()
    assert ist["patterns"]["last28"][-1]["hasEntry"] is True
    assert ist["summary"]["currentStreak"] == 1

    if when.date() != datetime.utcnow().date():
        utc = client.get("/api/insights?range=week").json()
        assert utc["patterns"]["last28"][-1]["hasEntry"] is False
        assert utc["patterns"]["last28"][-2]["hasEntry"] is True

    assert client.get("/api/insights?range=week&tz_offset=5000").status_code == 422


def test_patterns_are_empty_but_well_formed_for_a_new_user(client):
    p = client.get("/api/insights?range=all").json()["patterns"]
    assert p["analysedDays"] == 0 and len(p["last28"]) == 28 and len(p["weekday"]) == 7
    assert all(not d["hasEntry"] for d in p["last28"])
    assert p["overthinking"]["analysedDays"] == 0
