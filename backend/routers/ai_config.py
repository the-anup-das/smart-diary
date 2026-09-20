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
    from llm_client import get_model_name
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://sglang:30000/v1") if use_local else os.getenv("OPENAI_BASE_URL")
    host = urlparse(base_url).netloc if base_url else "api.openai.com"
    return {
        "host": host,
        "chat_model": get_model_name(),
        "is_local": use_local,
        "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
    }


@router.get("/api/ai/config")
def get_ai_config(user_id: str = Depends(verify_session)):
    return _provider_info()


@router.post("/api/ai/test", dependencies=[Depends(rate_limit("ai_test", 5, 60))])
def test_ai_connection(user_id: str = Depends(verify_session)):
    info = _provider_info()
    from llm_client import get_llm_client, get_model_name
    client = get_llm_client()
    # Override timeout for testing endpoint
    client.timeout = 15.0
    started = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=get_model_name(),
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
