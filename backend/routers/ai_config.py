"""Read-only view of the configured AI provider + a connection test.

Provider switching itself happens via environment variables (OPENAI_BASE_URL,
CHAT_MODEL, …) since it is deployment-wide, but the settings UI surfaces what
is configured and lets the user verify it actually responds — the key step
when pointing at a local Ollama instead of OpenAI.
"""
import os
import time
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
import openai

from rate_limit import rate_limit
from .auth import verify_session

router = APIRouter()


def _provider_info():
    base_url = os.getenv("OPENAI_BASE_URL")
    host = urlparse(base_url).netloc if base_url else "api.openai.com"
    return {
        "host": host,
        "is_custom": bool(base_url),
        "chat_model": os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
    }


@router.get("/api/ai/config")
def get_ai_config(user_id: str = Depends(verify_session)):
    return _provider_info()


@router.post("/api/ai/test", dependencies=[Depends(rate_limit("ai_test", 5, 60))])
def test_ai_connection(user_id: str = Depends(verify_session)):
    info = _provider_info()
    client = openai.OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", None),
        timeout=15,
    )
    started = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=info["chat_model"],
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            max_tokens=5,
        )
        return {
            "ok": True,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "model": response.model,
            "reply": (response.choices[0].message.content or "").strip()[:40],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
