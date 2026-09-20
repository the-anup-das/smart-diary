"""Save & Reflect through the router: provenance, the cache key, 503 without fallback, usage pricing, intentions."""
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from ai_contracts.analysis import PROMPT_VERSION, FeedbackReportSchema
from database import get_db
from llm_router import LLMUnavailable, RouteConfig, StructuredResult
from routers import analyze
from routers.auth import verify_session
from tests.test_ai_contracts import _good_report

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


class FakeRouter:
    def __init__(self, route: RouteConfig, *, fail=False, fallback=False):
        self.route = route
        self.fail = fail
        self.fallback = fallback
        self.calls = []

    def structured(self, schema, messages, **kw):
        self.calls.append((schema.__name__, messages, kw))
        if self.fail:
            raise LLMUnavailable("connection refused")
        if schema is FeedbackReportSchema:
            parsed = _good_report()
        else:
            parsed = schema(intentions=["What matters today?", "What can wait?", "Who to thank?"])
        provider = "cloud" if self.fallback else self.route.provider
        model = "gpt-4o-mini" if self.fallback else self.route.model
        return StructuredResult(parsed, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, provider, model, self.fallback, "json_schema", 1, [])


@pytest.fixture()
def client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(analyze.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    monkeypatch.setattr(analyze, "ingest_diary_entry", lambda *a, **k: None)
    return TestClient(app)


def _use(monkeypatch, router: FakeRouter):
    monkeypatch.setattr(analyze, "get_router", lambda prefs=None: router)
    monkeypatch.setattr(analyze, "resolve_route", lambda prefs=None: router.route)
    return router


def _entry(db, text="Today I scrolled for an hour and felt flat afterwards, then went for a run."):
    entry = models.JournalEntry(user_id=TEST_USER, content=f"<p>{text}</p>", date=datetime.utcnow())
    db.add(entry)
    db.commit()
    return entry


LOCAL = RouteConfig(provider="local", base_url="http://box:8080/v1", api_key="empty", model="smart-diary-slm", fallback_to_cloud=False)
CLOUD = RouteConfig(provider="cloud", base_url=None, api_key="sk", model="gpt-4o-mini")


def test_analysis_records_provenance_and_caches_per_model_and_prompt(client, db_session, monkeypatch):
    _entry(db_session)
    router = _use(monkeypatch, FakeRouter(LOCAL))
    first = client.post("/api/analyze").json()
    assert first["cached"] is False and first["model"] == {"provider": "local", "name": "smart-diary-slm", "promptVersion": PROMPT_VERSION, "fallbackUsed": False}
    assert first["feedback"]["model"]["name"] == "smart-diary-slm"
    row = db_session.query(models.FeedbackReport).first()
    assert (row.model_provider, row.model_name, row.prompt_version) == ("local", "smart-diary-slm", PROMPT_VERSION)
    assert router.calls[0][2]["rules"] is analyze.check_business_rules

    second = client.post("/api/analyze").json()
    assert second["cached"] is True and len(router.calls) == 1

    cloud = _use(monkeypatch, FakeRouter(CLOUD))
    third = client.post("/api/analyze").json()
    assert third["cached"] is False and third["model"]["provider"] == "cloud" and len(cloud.calls) == 1
    assert db_session.query(models.FeedbackReport).count() == 1


def test_stale_prompt_version_is_reanalysed(client, db_session, monkeypatch):
    _entry(db_session)
    router = _use(monkeypatch, FakeRouter(LOCAL))
    client.post("/api/analyze")
    row = db_session.query(models.FeedbackReport).first()
    row.prompt_version = "2025.01-v1"
    db_session.commit()
    assert client.post("/api/analyze").json()["cached"] is False and len(router.calls) == 2


def test_local_outage_without_fallback_is_a_503(client, db_session, monkeypatch):
    _entry(db_session)
    _use(monkeypatch, FakeRouter(LOCAL, fail=True))
    res = client.post("/api/analyze")
    assert res.status_code == 503 and "not available" in res.json()["detail"]
    assert db_session.query(models.FeedbackReport).count() == 0


def test_fallback_is_reported(client, db_session, monkeypatch):
    _entry(db_session)
    _use(monkeypatch, FakeRouter(LOCAL, fallback=True))
    data = client.post("/api/analyze").json()
    assert data["model"]["fallbackUsed"] is True and data["model"]["provider"] == "cloud"


def test_usage_prices_cloud_tokens_only(client, db_session, monkeypatch):
    entry = _entry(db_session)
    db_session.add(models.FeedbackReport(journal_entry_id=entry.id, mood_score=5, prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000, model_provider="local", model_name="slm"))
    other = _entry(db_session, "Another day.")
    db_session.add(models.FeedbackReport(journal_entry_id=other.id, mood_score=5, prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000, model_provider=None))
    db_session.commit()
    usage = client.get("/api/user/usage").json()["usage"]
    assert usage["local_tokens"] == 1_000_000 and usage["cloud_tokens"] == 2_000_000 and usage["total_tokens"] == 3_000_000
    assert usage["estimated_cost_usd"] == pytest.approx(0.15 + 0.60) and usage["local_analysis_count"] == 1 and usage["analysis_count"] == 2


def test_intentions_use_the_router_and_fall_back_to_static_prompts(client, db_session, monkeypatch):
    router = _use(monkeypatch, FakeRouter(LOCAL))
    data = client.get("/api/analyze/intentions?time_of_day=evening").json()
    assert data["intentions"] == ["What matters today?", "What can wait?", "Who to thank?"] and router.calls[0][0] == "DailyIntentionsSchema"
    assert client.get("/api/analyze/intentions?time_of_day=evening").json()["cached"] is True
    _use(monkeypatch, FakeRouter(LOCAL, fail=True))
    night = client.get("/api/analyze/intentions?time_of_day=night").json()
    assert night["error"] and len(night["intentions"]) == 3
