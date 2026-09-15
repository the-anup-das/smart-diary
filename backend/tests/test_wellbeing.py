"""
Tests for the Wellbeing Profile: the pure axis maths in wellbeing.py and the
aggregation exposed by GET /api/insights. Offline, SQLite, no model calls.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

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
from wellbeing import WELLBEING_AXES, average_axes, axes_from_feedback

TEST_USER = "user-1"


def _fb(mood=8, grammar=9, self_focus=4, battery=70.0, rumination="low", controllables=2, uncontrollables=2):
    return SimpleNamespace(
        mood_score=mood,
        grammar_score=grammar,
        self_focus_score=self_focus,
        energy_data={
            "battery_level": battery,
            "rumination_level": rumination,
            "controllables": [{"item": f"c{i}"} for i in range(controllables)],
            "uncontrollables": [{"item": f"u{i}"} for i in range(uncontrollables)],
        },
    )


# ---------------------------------------------------------------- pure maths

def test_axes_all_point_the_same_way():
    axes = axes_from_feedback(_fb(mood=8, grammar=9, self_focus=4, battery=70, rumination="low", controllables=3, uncontrollables=1))
    assert axes == {"mood": 80.0, "energy": 70.0, "calm": 100.0, "agency": 75.0, "outward": 60.0, "clarity": 90.0}
    # a worse day scores lower on every axis
    worse = axes_from_feedback(_fb(mood=3, grammar=5, self_focus=9, battery=20, rumination="high", controllables=0, uncontrollables=3))
    assert all(worse[k] < axes[k] for k in axes)


def test_missing_signals_become_none_not_zero():
    bare = SimpleNamespace(mood_score=6, grammar_score=None, self_focus_score=None, energy_data=None)
    axes = axes_from_feedback(bare)
    assert axes["mood"] == 60.0
    assert axes["clarity"] is None and axes["outward"] is None
    assert axes["energy"] is None and axes["calm"] is None and axes["agency"] is None
    assert axes_from_feedback(None)["mood"] is None


def test_average_skips_missing_axes_and_empty_reports():
    values, entries = average_axes([_fb(mood=8, rumination="low"), _fb(mood=4, rumination="high"), SimpleNamespace(mood_score=None, grammar_score=None, self_focus_score=None, energy_data=None)])
    assert entries == 2
    assert values["mood"] == 60.0 and values["calm"] == 50.0
    assert [a["key"] for a in WELLBEING_AXES] == list(values.keys())
    assert average_axes([]) == ({k: None for k in values}, 0)


# ---------------------------------------------------------------- endpoint

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


def _add_entry(db, days_ago, **fb_kwargs):
    entry = models.JournalEntry(user_id=TEST_USER, content="<p>Some words about the day and the demo.</p>", date=datetime.utcnow() - timedelta(days=days_ago))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    src = _fb(**fb_kwargs)
    db.add(models.FeedbackReport(
        journal_entry_id=entry.id, mood_score=src.mood_score, grammar_score=src.grammar_score,
        self_focus_score=src.self_focus_score, energy_data=src.energy_data, sentiment="Calm",
        topics={"work": 1.0}, word_count=9, unique_word_count=9, new_words=[],
    ))
    db.commit()


def test_insights_returns_profile_with_previous_period(client, db_session):
    _add_entry(db_session, 1, mood=8, rumination="low")
    _add_entry(db_session, 2, mood=6, rumination="moderate")
    _add_entry(db_session, 3, mood=7, rumination="low")
    _add_entry(db_session, 9, mood=4, rumination="high", battery=30)   # previous week
    _add_entry(db_session, 10, mood=2, rumination="high", battery=20)

    data = client.get("/api/insights?range=week").json()
    wb = data["wellbeing"]
    assert wb["entries"] == 3 and wb["previousEntries"] == 2
    by_key = {a["key"]: a for a in wb["axes"]}
    assert [a["key"] for a in wb["axes"]] == [a["key"] for a in WELLBEING_AXES]
    assert by_key["mood"]["value"] == 70.0 and by_key["mood"]["previous"] == 30.0
    assert by_key["calm"]["value"] == pytest.approx(83.3) and by_key["calm"]["previous"] == 0.0
    assert by_key["energy"]["value"] == 70.0 and by_key["energy"]["previous"] == 25.0
    assert by_key["agency"]["value"] == 50.0 and by_key["clarity"]["value"] == 90.0
    assert by_key["mood"]["label"] == "Mood" and by_key["outward"]["description"]


def test_insights_profile_without_previous_period(client, db_session):
    _add_entry(db_session, 1)
    data = client.get("/api/insights?range=week").json()
    wb = data["wellbeing"]
    assert wb["entries"] == 1 and wb["previousEntries"] == 0
    assert all(a["previous"] is None for a in wb["axes"])
    assert {a["key"]: a["value"] for a in wb["axes"]}["mood"] == 80.0

    # "all" has no previous period by definition
    data = client.get("/api/insights?range=all").json()
    assert data["wellbeing"]["previousEntries"] == 0


def test_insights_profile_is_empty_for_no_entries(client):
    data = client.get("/api/insights?range=month").json()
    wb = data["wellbeing"]
    assert wb["entries"] == 0
    assert all(a["value"] is None and a["previous"] is None for a in wb["axes"])
