"""Four Fuels: the maths on stand-in reports, then the endpoints on an in-memory database."""
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
from fuels import CHALLENGES, FUEL_KEYS, build_fuels, evidence_from_feedback, level_for, pick_challenge, score_days
from routers import fuels as fuels_router
from routers.auth import verify_session

TEST_USER = "user-1"


def _fb(*, mood=6, labels=(), builders=(), chargers=(), drainers=(), rumination="moderate", stim=None, cog=None, actions=0, topics=None):
    return SimpleNamespace(
        mood_score=mood, emotion_labels=list(labels), topics=topics or [],
        energy_data={"chargers": list(chargers), "drainers": list(drainers), "rumination_level": rumination,
                     "micro_actions": [{"id": str(i), "text": "x", "completed": True} for i in range(actions)]},
        stimulation_data=stim or {"behaviours": [], "load": 0, "afterState": "none", "cravingLanguage": False, "sleepDisrupted": False},
        cognition_data=cog or {"builders": list(builders), "shortFormVideo": False, "brainRotLoad": 0, "passiveConsumptionMinutes": 0, "fogOrAttention": False},
    )


SCROLL_NIGHT = {"behaviours": [{"behaviour": "doomscrolling", "category": "social_media", "timeOfDay": "night", "lostControl": True}],
                "load": 2, "afterState": "guilt", "cravingLanguage": False, "sleepDisrupted": True, "displaced": ["sleep"]}


def _day(date, *reports):
    evidence = {k: {"fed": [], "drained": []} for k in FUEL_KEYS}
    for fb in reports:
        ev = evidence_from_feedback(fb)
        for k in FUEL_KEYS:
            evidence[k]["fed"] += ev[k]["fed"]
            evidence[k]["drained"] += ev[k]["drained"]
    return {"date": date, "analysed": bool(reports), "evidence": evidence}


# ---------------------------------------------------------------- the maths

def test_a_night_of_scrolling_drains_drive_and_calm_but_a_walk_with_a_friend_feeds_bond_and_spark():
    bad = evidence_from_feedback(_fb(mood=3, labels=["exhausted", "anxious"], stim=SCROLL_NIGHT,
                                     cog={"builders": [], "shortFormVideo": True, "brainRotLoad": 2, "passiveConsumptionMinutes": 200}))
    assert [t for t, _ in bad["drive"]["drained"]][:2] == ["night_screens", "short_video"] and not bad["drive"]["fed"]
    assert {t for t, _ in bad["calm"]["drained"]} == {"rumination", "sleep", "low_mood"}
    assert {t for t, _ in bad["spark"]["drained"]} == {"sedentary", "flat"}
    assert not bad["bond"]["fed"] and not bad["bond"]["drained"]         # nothing about people either way

    good = evidence_from_feedback(_fb(mood=8, labels=["content", "connected"], builders=["exercise", "conversation", "nature"],
                                      chargers=["a long walk with Sam", "finished the report at last"], rumination="low", actions=2))
    assert {t for t, _ in good["drive"]["fed"]} == {"effort"} and len(good["drive"]["fed"]) == 2   # ticked actions, finished something
    assert len(good["bond"]["fed"]) >= 3 and not good["bond"]["drained"]
    assert any("no looping worry" in r for _, r in good["calm"]["fed"]) and not good["calm"]["drained"]
    assert any(r == "exercise" for _, r in good["spark"]["fed"])

    empty = evidence_from_feedback(SimpleNamespace(mood_score=None, emotion_labels=None, topics=None, energy_data=None, stimulation_data=None, cognition_data=None))
    assert all(not v["fed"] and not v["drained"] for v in empty.values())
    assert all(not v["fed"] and not v["drained"] for v in evidence_from_feedback(None).values())


def test_topics_work_in_either_stored_shape():
    as_list = evidence_from_feedback(_fb(mood=8, topics=[{"topic": "family", "weight": 0.6}]))
    as_dict = evidence_from_feedback(_fb(mood=8, topics={"family": 0.6}))
    assert as_list["bond"]["fed"] == as_dict["bond"]["fed"] == [("contact", "a good day with people")]
    low = evidence_from_feedback(_fb(mood=3, topics={"relationships": 0.5}))
    assert low["bond"]["drained"] == [("strain", "a hard day around people")]


def test_score_is_the_balance_of_days_not_of_mentions():
    days = [
        _day("2026-09-15", _fb(stim=SCROLL_NIGHT, cog={"builders": [], "shortFormVideo": True, "brainRotLoad": 3})),   # drained three ways, one day
        _day("2026-09-16", _fb(builders=["deep_work"])),
        _day("2026-09-17", _fb(actions=1)),
        _day("2026-09-18"),                                                                                          # no entry
    ]
    score, fed, drained = score_days(days, "drive")
    assert (score, fed, drained) == (67, 2, 1)            # 50 + 50 * (2 - 1) / 3 analysed days
    assert score_days([_day("2026-09-18")], "drive") == (None, 0, 0)
    assert score_days([_day("d", _fb(stim=SCROLL_NIGHT))] * 3, "drive")[0] == 0
    assert level_for(None, 0) == "none" and level_for(50, 0) == "quiet" and level_for(39, 1) == "low"
    assert level_for(40, 1) == "steady" and level_for(65, 1) == "strong"


def test_challenge_answers_the_weeks_main_drain_and_a_done_one_stays_visible():
    assert pick_challenge("drive", "night_screens", set())["id"] == "phone_outside_bedroom"
    assert pick_challenge("drive", "short_video", set())["id"] == "short_video_cap"
    assert pick_challenge("drive", None, set())["id"] == "finish_one_thing"
    assert pick_challenge("drive", "night_screens", {"hard_thing_first"})["id"] == "hard_thing_first"
    assert pick_challenge("calm", "sleep", set())["builder"] == "sleep"
    for fuel, items in CHALLENGES.items():
        assert sum(1 for c in items if c["when"] is None) == 1, fuel           # exactly one default each
        assert len({c["id"] for c in items}) == len(items)


def test_build_fuels_reads_like_a_sentence():
    days = [_day(f"2026-09-1{i}", _fb(stim=SCROLL_NIGHT, mood=3, labels=["exhausted"])) for i in range(4, 8)]
    days += [_day("2026-09-18", _fb(builders=["exercise", "conversation"], mood=8, labels=["proud"]))]
    body = build_fuels(days, [_day("2026-09-10", _fb(builders=["deep_work"]))], done_today=set(), today="2026-09-18")
    by_key = {f["key"]: f for f in body["fuels"]}
    drive = by_key["drive"]
    assert drive["score"] == 10 and drive["level"] == "low" and drive["previous"] == 100
    assert drive["because"].startswith("Drive was drained on 4 of 5 days (screens late into the night)")
    assert drive["challenge"]["id"] == "phone_outside_bedroom" and drive["challenge"]["doneToday"] is False
    assert [d["drained"] for d in drive["days"]] == [True, True, True, True, False]
    assert by_key["bond"]["level"] in ("steady", "strong") and by_key["bond"]["fedDays"] == 1
    assert "Light on Drive" in body["headline"] or "Light on Calm" in body["headline"]
    assert body["window"] == {"days": 5, "entries": 5, "previousEntries": 1, "today": "2026-09-18"}
    assert "Not a measurement" in body["note"]

    quiet = build_fuels([_day("2026-09-18", _fb(mood=5, rumination="moderate"))], [], set(), "2026-09-18")
    assert {f["level"] for f in quiet["fuels"]} == {"quiet"} and quiet["headline"].startswith("Write and reflect")
    assert build_fuels([], [], set(), "2026-09-18")["fuels"][0]["score"] is None


# ---------------------------------------------------------------- endpoints

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
    app.include_router(fuels_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    return TestClient(app)


def _add_entry(db, days_ago, **kwargs):
    src = _fb(**kwargs)
    entry = models.JournalEntry(user_id=TEST_USER, content="<p>A day.</p>", date=datetime.utcnow() - timedelta(days=days_ago))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.add(models.FeedbackReport(
        journal_entry_id=entry.id, mood_score=src.mood_score, grammar_score=9, self_focus_score=5, sentiment="Calm",
        topics={"work": 1.0}, word_count=3, unique_word_count=3, new_words=[], emotion_labels=src.emotion_labels,
        energy_data=src.energy_data, stimulation_data=src.stimulation_data, cognition_data=src.cognition_data,
    ))
    db.commit()


def test_endpoint_reads_the_week_and_the_one_before(client, db_session):
    for d in (1, 2, 3):
        _add_entry(db_session, d, stim=SCROLL_NIGHT, mood=3, labels=["exhausted"])
    _add_entry(db_session, 0, builders=["exercise", "nature", "conversation"], mood=8, labels=["content"], rumination="low")
    _add_entry(db_session, 9, builders=["deep_work"])      # last week
    data = client.get("/api/insights/fuels?tz_offset=0").json()
    assert data["window"]["days"] == 7 and data["window"]["entries"] == 4 and data["window"]["previousEntries"] == 1
    by_key = {f["key"]: f for f in data["fuels"]}
    assert by_key["drive"]["level"] == "low" and by_key["drive"]["previous"] == 100
    assert by_key["drive"]["challenge"]["id"] == "phone_outside_bedroom"
    assert by_key["calm"]["fedDays"] == 1 and by_key["calm"]["drainedDays"] == 3
    assert len(by_key["spark"]["days"]) == 7 and by_key["spark"]["days"][-1]["fed"] is True


def test_new_user_gets_a_well_formed_empty_answer(client):
    data = client.get("/api/insights/fuels").json()
    assert [f["key"] for f in data["fuels"]] == list(FUEL_KEYS)
    assert all(f["score"] is None and f["level"] == "none" for f in data["fuels"])
    assert client.get("/api/insights/fuels?tz_offset=5000").status_code == 422


def test_a_done_challenge_feeds_its_fuel_and_counts_for_mind_fitness(client, db_session):
    today = datetime.utcnow().date().isoformat()
    res = client.post("/api/insights/fuels/challenge", json={"id": "daylight_before_noon", "date": today, "done": True})
    assert res.status_code == 200 and res.json()["fuel"] == "calm" and res.json()["builder"] == "nature"
    data = client.get("/api/insights/fuels").json()
    calm = next(f for f in data["fuels"] if f["key"] == "calm")
    assert calm["challenge"]["id"] == "daylight_before_noon" and calm["challenge"]["doneToday"] is True
    assert calm["fedDays"] == 1 and calm["score"] == 100      # the challenge is the day's only evidence
    logs = db_session.query(models.MindLog).filter(models.MindLog.user_id == TEST_USER).all()
    assert [(l.date, l.builder, l.source) for l in logs] == [(today, "nature", "challenge")]
    user = db_session.query(models.User).filter(models.User.id == TEST_USER).first()
    assert user.preferences["fuel_challenges"] == {today: ["daylight_before_noon"]}

    client.post("/api/insights/fuels/challenge", json={"id": "daylight_before_noon", "date": today, "done": False})
    db_session.expire_all()
    assert db_session.query(models.MindLog).count() == 0
    assert next(f for f in client.get("/api/insights/fuels").json()["fuels"] if f["key"] == "calm")["challenge"]["doneToday"] is False

    assert client.post("/api/insights/fuels/challenge", json={"id": "nope", "date": today, "done": True}).status_code == 422
    assert client.post("/api/insights/fuels/challenge", json={"id": "ten_squats", "date": "2020-01-01", "done": True}).status_code == 422
    assert client.post("/api/insights/fuels/challenge", json={"id": "ten_squats", "date": "not-a-date", "done": True}).status_code == 422


def test_keyword_rules_match_words_not_fragments():
    """'huge' is not a hug, 'Sunday' is not sunshine, 'using' is not singing, and 'went running' still counts."""
    from fuels import _ALONE, _CONFLICT, _MOVING, _OUTDOORS, _PEOPLE, _SLEEPLESS

    for rx, misses, hits in (
        (_PEOPLE, ["a huge win at work", "vacation planning", "education stuff", "recalled the meeting"], ["hugged my sister", "chatted with Priya", "called Mum", "the dog"]),
        (_OUTDOORS, ["Sunday was fine", "parking was a nightmare", "a snap decision"], ["sunshine on the balcony", "walked to the shops", "an hour in the garden"]),
        (_MOVING, ["using the new tool", "abundance of work", "veteran colleague"], ["went running", "sang in the car", "a swim before work"]),
        (_ALONE, ["a lone voice"], ["ate alone again"]),
        (_CONFLICT, ["hypertension clinic"], ["we argued", "a row with Dad"]),
        (_SLEEPLESS, ["the 3 amigos"], ["3am again", "couldn't sleep"]),
    ):
        for text in misses:
            assert not rx.search(text), f"{rx.pattern[:30]}... should not match {text!r}"
        for text in hits:
            assert rx.search(text), f"{rx.pattern[:30]}... should match {text!r}"


# ---------------------------------------------------------------- the model judges, the rules are the fallback

def _judgement(*observations, headline="Light on Drive this week, strong on Spark."):
    return fuels_router.FuelJudgement(observations=[fuels_router.FuelObservation(**o) for o in observations], headline=headline)


def test_the_models_observations_drive_the_gauges_and_are_cached_per_day(client, db_session, monkeypatch):
    today = datetime.utcnow().date()
    _add_entry(db_session, 0, mood=6)                         # signals alone would say nothing about drive
    _add_entry(db_session, 1, mood=6)
    calls = []

    def fake_judge(day_texts):
        calls.append([d for d, _ in day_texts])
        return _judgement(
            {"date": today.isoformat(), "fuel": "drive", "effect": "drained", "tag": "night_screens", "reason": "scrolled until 2am again"},
            {"date": (today - timedelta(days=1)).isoformat(), "fuel": "drive", "effect": "drained", "tag": "night_screens", "reason": "phone in bed till late"},
            {"date": today.isoformat(), "fuel": "spark", "effect": "fed", "tag": "moving", "reason": "ran by the river before work"},
            {"date": "1999-01-01", "fuel": "calm", "effect": "fed", "tag": "steady", "reason": "outside the window, dropped"},
        )

    monkeypatch.setattr(fuels_router, "judge_week", fake_judge)
    data = client.get("/api/insights/fuels").json()
    assert data["source"]["kind"] == "model" and data["source"]["cached"] is False
    assert data["headline"] == "Light on Drive this week, strong on Spark."
    by_key = {f["key"]: f for f in data["fuels"]}
    assert by_key["drive"]["score"] == 0 and by_key["drive"]["drainedDays"] == 2 and by_key["drive"]["challenge"]["id"] == "phone_outside_bedroom"
    assert by_key["drive"]["drainedByReasons"][0]["text"] in ("scrolled until 2am again", "phone in bed till late")
    assert by_key["spark"]["fedDays"] == 1 and by_key["calm"]["fedDays"] == 0
    assert calls == [[(today - timedelta(days=1)).isoformat(), today.isoformat()]]   # both days went to the model, oldest first

    again = client.get("/api/insights/fuels").json()
    assert again["source"]["cached"] is True and len(calls) == 1                   # same day, same entries: no second call
    client.get("/api/insights/fuels?refresh=true")
    assert len(calls) == 2                                                           # refresh asks again
    _add_entry(db_session, 0, mood=6)
    client.get("/api/insights/fuels")
    assert len(calls) == 3                                                           # a new entry invalidates the cache


def test_without_a_model_the_stored_signals_carry_the_gauges(client, db_session, monkeypatch):
    _add_entry(db_session, 0, stim=SCROLL_NIGHT, mood=3)
    monkeypatch.setattr(fuels_router, "judge_week", lambda day_texts: None)         # the model could not answer
    data = client.get("/api/insights/fuels").json()
    assert data["source"] == {"kind": "signals", "model": None, "cached": False}
    assert next(f for f in data["fuels"] if f["key"] == "drive")["drainedDays"] == 1

    user = db_session.query(models.User).filter(models.User.id == TEST_USER).first()
    user.preferences = {"pause_ai": True}
    db_session.commit()
    calls = []
    monkeypatch.setattr(fuels_router, "judge_week", lambda day_texts: calls.append(1) or _judgement())
    assert client.get("/api/insights/fuels").json()["source"]["kind"] == "signals" and calls == []   # paused AI: never asked


def test_judge_week_prompt_lists_every_tag_and_survives_a_dead_client(monkeypatch):
    prompt = fuels_router._judging_prompt()
    for fuel, sides in fuels_router.TAGS.items():
        for tags in sides.values():
            for tag in tags:
                assert f"`{tag}`" in prompt
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(fuels_router, "_client", None)
    assert fuels_router.judge_week([("2026-09-20", "a day")]) is None      # no key, no crash
    assert fuels_router.judge_week([]) is None
