"""
The AI provider as the settings page sees it, and a connection test.

The route is resolved per person: the preferences `ai_mode`, `local_llm_base_url`,
`local_llm_model` and `local_llm_fallback` override the environment defaults, so a person can
point the app at their own llama.cpp, vLLM, LM Studio or Ollama server without touching the
deployment.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db
from llm_router import probe, provider_summary, resolve_route
from rate_limit import rate_limit
from .auth import verify_session

router = APIRouter()


def _preferences(user_id: str, db: Session) -> dict:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    return (user.preferences if user else None) or {}


@router.get("/api/ai/config")
def get_ai_config(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    return provider_summary(_preferences(user_id, db))


class TestRequest(BaseModel):
    base_url: str | None = None   # test unsaved values from the settings form
    model: str | None = None
    mode: str | None = None       # "local" | "cloud"; defaults to the resolved route


@router.post("/api/ai/test", dependencies=[Depends(rate_limit("ai_test", 5, 60))])
def test_ai_connection(payload: TestRequest | None = None, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    prefs = dict(_preferences(user_id, db))
    payload = payload or TestRequest()
    if payload.mode:
        prefs["ai_mode"] = payload.mode
    if payload.base_url:
        prefs["ai_mode"] = "local"
        prefs["local_llm_base_url"] = payload.base_url
    if payload.model:
        prefs["local_llm_model"] = payload.model
    route = resolve_route(prefs)
    if payload.base_url and route.provider != "local":
        return {"ok": False, "error": "That is not a valid http(s) URL.", "mode": "local"}
    result = probe(route.base_url, route.model, api_key=route.api_key, timeout=15.0)
    result["mode"] = route.provider
    result["host"] = route.host
    return result
