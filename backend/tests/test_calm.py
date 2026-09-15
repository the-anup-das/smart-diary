"""
Offline tests for the 3-Minute Reset router (routers/calm.py).

They run against an in-memory SQLite database with the auth dependency
overridden and the LLM planner mocked, so no Postgres, Qdrant or OpenAI
key is needed:  cd backend && python -m pytest tests -q
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
from routers import calm
from routers.auth import verify_session

TEST_USER = "user-1"
OTHER_USER = "user-2"

FAKE_PLAN = {
    "loopThought": "You keep replaying what you should have said in the review.",
    "ruminationType": "past_regret",
    "acknowledgement": "Your mind is trying to fix a conversation that is already over.",
    "letGo": "The perfect version of that review exists only in your head.",
    "whatMatters": "The follow-up note you can still write tomorrow.",
    "visualisation": ["line one", "line two", "line three", "line four"],
    "affirmations": ["one", "two", "three"],
    "lessonQuestion": "What does this reveal about how you want to be heard?",
}


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    session.add(models.User(id=TEST_USER, email="t@example.com", password="x", name="Test", preferences={}))
    session.add(models.User(id=OTHER_USER, email="o@example.com", password="x", name="Other", preferences={}))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(calm.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    monkeypatch.setattr(calm, "_safe_memories", lambda user_id, text: "")
    return TestClient(app)


def _add_analyzed_entry(db, level="high", content_hash="hash-1"):
    entry = models.JournalEntry(
        user_id=TEST_USER,
        content="<p>I keep replaying the meeting with my manager and what I should have said.</p>",
        date=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    feedback = models.FeedbackReport(
        journal_entry_id=entry.id,
        mood_score=4,
        sentiment="Anxious",
        grammar_score=8,
        content_hash=content_hash,
        energy_data={
            "rumination_level": level,
            "rumination_coaching": "You are replaying a conversation that is over.",
            "controllables": [{"item": "How I prepare the follow-up", "reframe": "x"}],
            "uncontrollables": [{"item": "My manager's mood", "reframe": "y"}],
        },
    )
    db.add(feedback)
    db.commit()
    return entry, feedback


def _fake_builder(calls):
    def build(entry_text, energy=None, memories="", preferences=None):
        calls.append({"text": entry_text, "energy": energy, "preferences": preferences})
        return dict(FAKE_PLAN), {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    return build


# ---------------------------------------------------------------- creating sessions

def test_manual_session_without_entry_uses_generic_plan(client):
    res = client.post("/api/calm/sessions", json={"source": "manual"})
    assert res.status_code == 200
    session = res.json()["session"]
    assert session["personalized"] is False
    assert session["entryId"] is None
    assert session["ruminationLevel"] is None
    assert len(session["plan"]["visualisation"]) == 4
    assert len(session["plan"]["affirmations"]) == 3
    assert session["completed"] is False


def test_entry_session_is_personalized_and_plan_is_reused(client, db_session, monkeypatch):
    _add_analyzed_entry(db_session)
    calls = []
    monkeypatch.setattr(calm, "build_reset_plan", _fake_builder(calls))

    first = client.post("/api/calm/sessions", json={"source": "entry"}).json()["session"]
    assert first["personalized"] is True
    assert first["loopThought"] == FAKE_PLAN["loopThought"]
    assert first["ruminationType"] == "past_regret"
    assert first["ruminationLevel"] == "high"
    assert first["entryId"] is not None
    assert calls[0]["energy"]["rumination_level"] == "high"
    assert "manager" in calls[0]["text"] and "<p>" not in calls[0]["text"]

    # Starting again for the same entry content reuses the plan instead of paying for a second call.
    second = client.post("/api/calm/sessions", json={"source": "manual"}).json()["session"]
    assert second["personalized"] is True
    assert second["plan"]["visualisation"] == FAKE_PLAN["visualisation"]
    assert len(calls) == 1

    rows = db_session.query(models.CalmSession).order_by(models.CalmSession.started_at).all()
    assert [r.total_tokens for r in rows] == [150, 0]
    assert rows[0].source_hash == "hash-1" and rows[1].source_hash == "hash-1"


def test_edited_entry_gets_a_fresh_plan(client, db_session, monkeypatch):
    entry, feedback = _add_analyzed_entry(db_session, content_hash="hash-1")
    calls = []
    monkeypatch.setattr(calm, "build_reset_plan", _fake_builder(calls))
    client.post("/api/calm/sessions", json={"source": "entry"})
    feedback.content_hash = "hash-2"  # entry was edited and re-analysed
    db_session.commit()
    client.post("/api/calm/sessions", json={"source": "entry"})
    assert len(calls) == 2


def test_llm_failure_falls_back_to_generic_plan(client, db_session, monkeypatch):
    _add_analyzed_entry(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("OpenAI unavailable")

    monkeypatch.setattr(calm, "build_reset_plan", boom)
    res = client.post("/api/calm/sessions", json={"source": "entry"})
    assert res.status_code == 200
    session = res.json()["session"]
    assert session["personalized"] is False
    assert session["ruminationLevel"] == "high"
    assert session["plan"]["visualisation"] == calm.GENERIC_PLAN["visualisation"]


def test_paused_ai_skips_personalization(client, db_session, monkeypatch):
    user = db_session.get(models.User, TEST_USER)
    user.preferences = {"pause_ai": True}
    db_session.commit()
    _add_analyzed_entry(db_session)
    calls = []
    monkeypatch.setattr(calm, "build_reset_plan", _fake_builder(calls))
    session = client.post("/api/calm/sessions", json={"source": "entry"}).json()["session"]
    assert session["personalized"] is False
    assert calls == []


def test_invalid_source_is_rejected(client):
    assert client.post("/api/calm/sessions", json={"source": "nope"}).status_code == 422


# ---------------------------------------------------------------- updating sessions

def test_update_session_tracks_progress_and_completion(client):
    sid = client.post("/api/calm/sessions", json={"source": "manual"}).json()["session"]["id"]

    s = client.patch(f"/api/calm/sessions/{sid}", json={"mind_before": 4, "steps_completed": 1}).json()["session"]
    assert s["mindBefore"] == 4 and s["stepsCompleted"] == 1 and s["completed"] is False

    # Progress never moves backwards (a late PATCH from a slow tab cannot undo a step).
    s = client.patch(f"/api/calm/sessions/{sid}", json={"steps_completed": 0, "duration_seconds": 30}).json()["session"]
    assert s["stepsCompleted"] == 1 and s["durationSeconds"] == 30

    s = client.patch(
        f"/api/calm/sessions/{sid}",
        json={"mind_after": 2, "steps_completed": 3, "duration_seconds": 181, "note": "  lighter  ", "completed": True},
    ).json()["session"]
    assert s["completed"] is True and s["completedAt"] is not None
    assert s["mindAfter"] == 2 and s["stepsCompleted"] == 3 and s["durationSeconds"] == 181
    assert s["note"] == "lighter"

    # Completion is sticky and a blank note clears it.
    s = client.patch(f"/api/calm/sessions/{sid}", json={"completed": False, "note": "   "}).json()["session"]
    assert s["completed"] is True and s["note"] is None


def test_update_validation_and_ownership(client, db_session):
    sid = client.post("/api/calm/sessions", json={"source": "manual"}).json()["session"]["id"]
    assert client.patch(f"/api/calm/sessions/{sid}", json={"mind_after": 9}).status_code == 422
    assert client.patch("/api/calm/sessions/does-not-exist", json={"mind_after": 1}).status_code == 404

    foreign = models.CalmSession(user_id=OTHER_USER, source="manual", plan=calm.GENERIC_PLAN)
    db_session.add(foreign)
    db_session.commit()
    assert client.patch(f"/api/calm/sessions/{foreign.id}", json={"mind_after": 1}).status_code == 404


# ---------------------------------------------------------------- summary

def _add_session(db, days_ago, before=None, after=None, completed=True, note=None, user_id=TEST_USER):
    started = datetime.utcnow() - timedelta(days=days_ago)
    db.add(models.CalmSession(
        user_id=user_id,
        source="manual",
        plan=calm.GENERIC_PLAN,
        mind_before=before,
        mind_after=after,
        steps_completed=3 if completed else 1,
        started_at=started,
        completed_at=(started + timedelta(minutes=3)) if completed else None,
        note=note,
    ))


def test_summary_is_empty_for_a_new_user(client):
    data = client.get("/api/calm/summary").json()
    assert data["streak"] == 0
    assert data["totalSessions"] == 0 and data["completedSessions"] == 0
    assert data["avgDelta"] is None
    assert data["today"] is None and data["recent"] == []
    assert len(data["last28"]) == 28
    assert all(day["completed"] is False for day in data["last28"])


def test_summary_streak_strip_and_deltas(client, db_session):
    _add_session(db_session, 0, 4, 2, note="calmer")
    _add_session(db_session, 1, 5, 3)
    _add_session(db_session, 2, 3, 3)
    # day 3 missed, which ends the streak
    _add_session(db_session, 4, 4, 1)
    _add_session(db_session, 5, 4, None, completed=False)
    _add_session(db_session, 0, 5, 1, user_id=OTHER_USER)  # someone else's practice must not leak in
    db_session.commit()

    data = client.get("/api/calm/summary").json()
    assert data["streak"] == 3
    assert data["totalSessions"] == 5
    assert data["completedSessions"] == 4
    assert data["avgDelta"] == pytest.approx((2 + 2 + 0 + 3) / 4)

    strip = data["last28"]
    assert len(strip) == 28
    assert strip[-1]["date"] == datetime.utcnow().strftime("%Y-%m-%d")
    assert [d["completed"] for d in strip[-6:]] == [False, True, False, True, True, True]
    assert strip[-1]["delta"] == 2 and strip[-6]["completed"] is False and strip[-6]["sessions"] == 1

    assert data["today"]["note"] == "calmer" and data["today"]["completed"] is True
    assert data["recent"][0]["note"] == "calmer" and data["recent"][0]["delta"] == 2
    assert len(data["recent"]) == 4


def test_streak_survives_until_a_full_day_is_missed(client, db_session):
    _add_session(db_session, 1, 4, 2)
    _add_session(db_session, 2, 4, 2)
    db_session.commit()
    data = client.get("/api/calm/summary").json()
    assert data["streak"] == 2
    assert data["today"] is None

    _add_session(db_session, 0, 3, 1, completed=False)  # started today, not finished yet
    db_session.commit()
    data = client.get("/api/calm/summary").json()
    assert data["streak"] == 2
    assert data["today"] is not None and data["today"]["completed"] is False


def test_build_reset_plan_pads_and_normalises(monkeypatch):
    """The planner keeps the UI's fixed pacing even if the model returns short lists or an odd type."""
    class FakeParsed:
        def model_dump(self):
            return {**FAKE_PLAN, "visualisation": ["only one"], "affirmations": [], "ruminationType": "weird"}

    class FakeUsage:
        prompt_tokens, completion_tokens, total_tokens = 10, 5, 15

    class FakeResponse:
        usage = FakeUsage()
        choices = [type("C", (), {"message": type("M", (), {"parsed": FakeParsed()})()})()]

    class FakeCompletions:
        def parse(self, **kwargs):
            assert kwargs["response_format"] is calm.ResetPlanSchema
            assert "CONTEXT FROM TODAY'S ANALYSIS" in kwargs["messages"][0]["content"]
            assert "Within the writer's control: prep" in kwargs["messages"][0]["content"]
            assert "USER'S CUSTOM INSTRUCTIONS: be brief" in kwargs["messages"][0]["content"]
            return FakeResponse()

    class FakeClient:
        beta = type("B", (), {"chat": type("Ch", (), {"completions": FakeCompletions()})()})()

    monkeypatch.setattr(calm, "_get_client", lambda: FakeClient())
    plan, usage = calm.build_reset_plan(
        "text",
        energy={"rumination_level": "high", "controllables": [{"item": "prep"}]},
        preferences={"custom_persona_prompt": "be brief"},
    )
    assert plan["visualisation"][0] == "only one" and len(plan["visualisation"]) == 4
    assert len(plan["affirmations"]) == 3
    assert plan["ruminationType"] == "mixed"
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


# ---------------------------------------------------------------- follow-up coverage

def test_entry_without_analysis_is_still_personalized(client, db_session, monkeypatch):
    """The live nudge can start a reset before Save & Reflect; the plan is built from the raw text."""
    entry = models.JournalEntry(user_id=TEST_USER, content="<p>What if the demo fails tomorrow and everyone sees?</p>", date=datetime.utcnow())
    db_session.add(entry)
    db_session.commit()
    calls = []
    monkeypatch.setattr(calm, "build_reset_plan", _fake_builder(calls))
    s = client.post("/api/calm/sessions", json={"source": "entry"}).json()["session"]
    assert s["personalized"] is True and s["entryId"] == entry.id and s["ruminationLevel"] is None
    assert calls[0]["energy"] == {}
    # Same text again reuses the plan; the hash is derived from the text when no analysis exists yet.
    client.post("/api/calm/sessions", json={"source": "entry"})
    assert len(calls) == 1


def test_summary_uses_viewer_timezone(client, db_session):
    # A session just after local midnight for a viewer at UTC+5:30 counts as "today" for them,
    # while in UTC it still belongs to the previous day (whenever the two dates differ).
    offset = timedelta(minutes=330)
    ist_today = (datetime.utcnow() + offset).date()
    started = datetime.combine(ist_today, datetime.min.time()) - offset + timedelta(minutes=1)
    db_session.add(models.CalmSession(user_id=TEST_USER, source="manual", plan=calm.GENERIC_PLAN, mind_before=4, mind_after=2,
                                      started_at=started, completed_at=started + timedelta(minutes=3)))
    db_session.commit()

    utc_view = client.get("/api/calm/summary").json()
    if started.date() != datetime.utcnow().date():
        assert utc_view["today"] is None
        assert utc_view["last28"][-2]["completed"] is True
    else:  # in the UTC evening the session also falls on the current UTC day
        assert utc_view["today"] is not None

    ist_view = client.get("/api/calm/summary?tz_offset=330").json()
    assert ist_view["today"] is not None and ist_view["today"]["completed"] is True
    assert ist_view["last28"][-1]["completed"] is True
    assert ist_view["streak"] == 1

    assert client.get("/api/calm/summary?tz_offset=9999").status_code == 422


def test_completed_resets_today_counts_only_finished_sessions(client, db_session):
    assert calm.completed_resets_today(TEST_USER, db_session) == 0
    sid = client.post("/api/calm/sessions", json={"source": "manual"}).json()["session"]["id"]
    assert calm.completed_resets_today(TEST_USER, db_session) == 0
    client.patch(f"/api/calm/sessions/{sid}", json={"completed": True})
    assert calm.completed_resets_today(TEST_USER, db_session) == 1
    assert calm.completed_resets_today(OTHER_USER, db_session) == 0


def test_export_and_import_round_trip_calm_sessions(db_session, monkeypatch):
    from routers import users
    app = FastAPI()
    app.include_router(users.router)
    app.include_router(calm.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    monkeypatch.setattr(calm, "_safe_memories", lambda user_id, text: "")
    api = TestClient(app)

    _add_analyzed_entry(db_session)
    monkeypatch.setattr(calm, "build_reset_plan", _fake_builder([]))
    sid = api.post("/api/calm/sessions", json={"source": "entry"}).json()["session"]["id"]
    api.patch(f"/api/calm/sessions/{sid}", json={"mind_before": 4, "mind_after": 1, "note": "clear", "completed": True})

    export = api.get("/api/users/export").json()
    assert len(export["calmSessions"]) == 1
    exported = export["calmSessions"][0]
    assert exported["note"] == "clear" and exported["personalized"] is True and exported["entry_id"] is not None

    res = api.post("/api/users/import", json=export)
    assert res.status_code == 200 and res.json()["calm_sessions_imported"] == 1

    rows = db_session.query(models.CalmSession).filter(models.CalmSession.user_id == TEST_USER).all()
    assert len(rows) == 2
    imported = [r for r in rows if r.id != sid][0]
    assert imported.note == "clear" and imported.completed_at is not None and imported.mind_after == 1
    assert imported.entry_id is not None and imported.entry_id != exported["entry_id"]  # remapped to the imported entry
    assert imported.plan["loopThought"] == FAKE_PLAN["loopThought"]
