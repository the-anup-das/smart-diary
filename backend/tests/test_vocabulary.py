"""Tests for GET /api/entries/vocabulary, which feeds the editor's Tab word completion."""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import get_db
from routers import entries
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
    app.include_router(entries.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    return TestClient(app)


def _entry(db, content, user_id=TEST_USER, days_ago=0, deleted=False):
    db.add(models.JournalEntry(user_id=user_id, content=content, date=datetime.utcnow() - timedelta(days=days_ago), is_deleted=deleted))
    db.commit()


def test_vocabulary_counts_words_by_frequency(client, db_session):
    _entry(db_session, "<p>The meeting with my manager. Another meeting tomorrow, and the manager's deadline.</p>", days_ago=1)
    _entry(db_session, "<h2>Later</h2><p>Meeting again. Grateful, though.</p>")
    _entry(db_session, "<p>Deleted words should vanish: xylophone xylophone.</p>", deleted=True)
    _entry(db_session, "<p>Someone else's vocabulary: zeppelin zeppelin.</p>", user_id="user-2")

    data = client.get("/api/entries/vocabulary").json()
    words = {item["w"]: item["n"] for item in data["words"]}
    assert words["meeting"] == 3
    assert words["manager"] == 2           # "manager's" counts for "manager"
    assert words["tomorrow"] == 1 and words["grateful"] == 1
    assert "the" not in words and "and" not in words   # under four letters is not worth completing
    assert words["with"] == 1                             # four letters is the floor
    assert "xylophone" not in words and "zeppelin" not in words
    assert data["words"][0]["w"] == "meeting"   # most frequent first
    assert data["total"] == len(words)


def test_vocabulary_is_empty_for_a_new_writer_and_respects_limit(client, db_session):
    assert client.get("/api/entries/vocabulary").json() == {"words": [], "total": 0}
    _entry(db_session, "<p>" + " ".join(f"word{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(300)) + "</p>")
    data = client.get("/api/entries/vocabulary?limit=100").json()
    assert len(data["words"]) == 100 and data["total"] == 300
    assert client.get("/api/entries/vocabulary?limit=5").status_code == 422


def test_streak_counts_consecutive_local_days(client, db_session):
    assert client.get("/api/entries/streak").json() == {"streak": 0, "wroteToday": False}
    _entry(db_session, "<p>yesterday</p>", days_ago=1)
    _entry(db_session, "<p>two days ago</p>", days_ago=2)
    _entry(db_session, "<p>gap before this one</p>", days_ago=4)
    _entry(db_session, "<p>not mine</p>", user_id="user-2")
    data = client.get("/api/entries/streak").json()
    assert data == {"streak": 2, "wroteToday": False}   # survives until today is missed
    _entry(db_session, "<p>today</p>")
    data = client.get("/api/entries/streak").json()
    assert data == {"streak": 3, "wroteToday": True}
    assert client.get("/api/entries/streak?tz_offset=9999").status_code == 422
