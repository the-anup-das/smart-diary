"""The AI settings endpoints: the resolved provider for the person, and the connection test with unsaved values."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import get_db
from routers import ai_config
from routers.auth import verify_session

TEST_USER = "user-1"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    session.add(models.User(id=TEST_USER, email="t@example.com", password="x", name="Test",
                            preferences={"ai_mode": "local", "local_llm_base_url": "http://box:8080/v1", "local_llm_model": "slm", "local_llm_fallback": True}))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for var in ("USE_LOCAL_LLM", "OPENAI_BASE_URL", "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    app = FastAPI()
    app.include_router(ai_config.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_session] = lambda: TEST_USER
    return TestClient(app)


def test_config_reflects_the_persons_route(client):
    data = client.get("/api/ai/config").json()
    assert data["mode"] == "local" and data["host"] == "box:8080" and data["chat_model"] == "slm"
    assert data["fallback_to_cloud"] is True and data["cloud_available"] is True and data["server_defaults"]["local_model"]


def test_connection_test_uses_unsaved_values(client, monkeypatch):
    seen = {}

    def fake_probe(base_url, model, api_key="empty", timeout=15.0):
        seen.update({"base_url": base_url, "model": model})
        return {"ok": True, "latency_ms": 12, "models_listed": [model], "model_found": True, "json_schema": True, "error": None}

    monkeypatch.setattr(ai_config, "probe", fake_probe)
    data = client.post("/api/ai/test", json={"base_url": "http://other:1234/v1", "model": "gemma"}).json()
    assert data["ok"] and data["mode"] == "local" and data["host"] == "other:1234" and seen == {"base_url": "http://other:1234/v1", "model": "gemma"}
    cloud = client.post("/api/ai/test", json={"mode": "cloud"}).json()
    assert cloud["mode"] == "cloud" and seen["base_url"] is None
    bad = client.post("/api/ai/test", json={"base_url": "nope"}).json()
    assert bad["ok"] is False and "valid http" in bad["error"]
