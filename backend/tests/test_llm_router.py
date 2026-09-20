"""The per-request LLM router: route precedence, the structured-output ladder, retries with feedback, and cloud fallback."""
from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

import llm_router as lr


class Verdict(BaseModel):
    decision: str
    score: int


def _response(content=None, parsed=None, prompt=10, completion=5, model="served"):
    message = SimpleNamespace(content=content, parsed=parsed, refusal=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion), model=model)


def _http_error(cls, status, message):
    request = httpx.Request("POST", "http://test.local/v1/chat/completions")
    return cls(message, response=httpx.Response(status, request=request), body=None)


class FakeClient:
    """Serves queued outcomes; records every request."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create, parse=self._parse))
        self.models = SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id="served")]))

    def _next(self, params):
        self.calls.append(params)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if callable(outcome):
            return outcome()
        return outcome

    def _create(self, **params):
        return self._next(params)

    def _parse(self, **params):
        return self._next(params)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    lr.reset_caches()
    for var in ("USE_LOCAL_LLM", "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL", "LOCAL_LLM_FALLBACK", "OPENAI_BASE_URL", "CHAT_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _install(monkeypatch, by_provider: dict):
    def fake_client_for(route):
        return by_provider[route.provider]
    monkeypatch.setattr(lr, "_client_for", fake_client_for)


# ---------------------------------------------------------------- routes

def test_preferences_win_over_environment(monkeypatch):
    assert lr.resolve_route({}).provider == "cloud"
    monkeypatch.setenv("USE_LOCAL_LLM", "true")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "env-model")
    env_route = lr.resolve_route({})
    assert env_route.provider == "local" and env_route.model == "env-model" and env_route.base_url == lr.DEFAULT_LOCAL_BASE_URL
    pref_route = lr.resolve_route({"ai_mode": "local", "local_llm_base_url": "http://box:8080/v1/", "local_llm_model": "my-slm", "local_llm_fallback": False})
    assert pref_route.base_url == "http://box:8080/v1" and pref_route.model == "my-slm" and pref_route.fallback_to_cloud is False
    assert lr.resolve_route({"ai_mode": "cloud"}).provider == "cloud"


def test_invalid_local_url_and_missing_cloud_key(monkeypatch):
    assert lr.resolve_route({"ai_mode": "local", "local_llm_base_url": "not a url"}).provider == "cloud"
    monkeypatch.delenv("OPENAI_API_KEY")
    route = lr.resolve_route({"ai_mode": "local", "local_llm_base_url": "http://box:8080/v1", "local_llm_fallback": True})
    assert route.provider == "local" and route.fallback_to_cloud is False  # nothing to fall back to


# ---------------------------------------------------------------- structured ladder

def _local_router(fallback=True):
    return lr.LLMRouter(lr.resolve_route({"ai_mode": "local", "local_llm_base_url": "http://box:8080/v1", "local_llm_model": "slm", "local_llm_fallback": fallback}))


def test_json_schema_downgrades_to_json_object_and_is_remembered(monkeypatch):
    local = FakeClient([
        _http_error(openai.BadRequestError, 400, "response_format json_schema is not supported"),
        _response('```json\n{"decision": "PASS", "score": 9}\n```'),
        _response('{"decision": "FAIL", "score": 1}'),
    ])
    _install(monkeypatch, {"local": local})
    router = _local_router()
    first = router.structured(Verdict, [{"role": "user", "content": "judge"}])
    assert first.parsed.decision == "PASS" and first.mode == "json_object" and first.provider == "local" and first.model == "slm"
    assert local.calls[0]["response_format"]["type"] == "json_schema" and local.calls[1]["response_format"] == {"type": "json_object"}
    second = router.structured(Verdict, [{"role": "user", "content": "judge"}])
    assert second.mode == "json_object" and local.calls[2]["response_format"] == {"type": "json_object"}


def test_validation_error_is_fed_back_once(monkeypatch):
    local = FakeClient([_response('{"decision": "PASS", "score": "nine"}'), _response('{"decision": "PASS", "score": 9}')])
    _install(monkeypatch, {"local": local})
    result = _local_router().structured(Verdict, [{"role": "user", "content": "judge"}])
    assert result.parsed.score == 9 and result.attempts == 2 and result.usage["total_tokens"] == 30
    retry_messages = local.calls[1]["messages"]
    assert retry_messages[-2]["role"] == "assistant" and "score" in retry_messages[-1]["content"] and "rejected" in retry_messages[-1]["content"]


def test_rules_get_one_correction_turn_then_the_answer_is_accepted(monkeypatch):
    local = FakeClient([_response('{"decision": "PASS", "score": 3}'), _response('{"decision": "PASS", "score": 4}')])
    _install(monkeypatch, {"local": local})
    rules = lambda v: [f"score {v.score} is below 5"] if v.score < 5 else []  # noqa: E731
    result = _local_router().structured(Verdict, [{"role": "user", "content": "judge"}], rules=rules)
    assert result.parsed.score == 4 and result.rule_problems == ["score 4 is below 5"] and result.attempts == 2
    assert "Fix these problems" in local.calls[1]["messages"][-1]["content"]


def test_local_failure_falls_back_to_cloud_when_allowed(monkeypatch):
    local = FakeClient([openai.APIConnectionError(request=httpx.Request("POST", "http://box"))])
    cloud = FakeClient([_response(parsed=Verdict(decision="PASS", score=8))])
    _install(monkeypatch, {"local": local, "cloud": cloud})
    result = _local_router(fallback=True).structured(Verdict, [{"role": "user", "content": "judge"}])
    assert result.fallback_used and result.provider == "cloud" and result.mode == "native" and result.parsed.score == 8
    assert cloud.calls[0]["response_format"] is Verdict  # native parse on api.openai.com


def test_local_failure_without_fallback_raises(monkeypatch):
    local = FakeClient([_response("I cannot answer that."), _response("still no json")])
    _install(monkeypatch, {"local": local})
    with pytest.raises(lr.LLMUnavailable):
        _local_router(fallback=False).structured(Verdict, [{"role": "user", "content": "judge"}])


def test_native_refusal_is_unavailable(monkeypatch):
    cloud = FakeClient([_response(parsed=None), _response(parsed=None)])
    _install(monkeypatch, {"cloud": cloud})
    with pytest.raises(lr.LLMUnavailable):
        lr.LLMRouter(lr.cloud_route()).structured(Verdict, [{"role": "user", "content": "x"}])


# ---------------------------------------------------------------- text and stream

def test_stream_falls_back_only_before_the_first_token(monkeypatch):
    def chunks(*texts):
        return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=t))]) for t in texts]

    local = FakeClient([_http_error(openai.InternalServerError, 500, "boom")])
    cloud = FakeClient([lambda: iter(chunks("hel", "lo"))])
    _install(monkeypatch, {"local": local, "cloud": cloud})
    assert "".join(_local_router().stream([{"role": "user", "content": "hi"}])) == "hello"

    def broken():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="part"))])
        raise _http_error(openai.InternalServerError, 500, "mid-stream")

    local2 = FakeClient([broken])
    _install(monkeypatch, {"local": local2, "cloud": FakeClient([])})
    out = []
    with pytest.raises(lr.LLMUnavailable):
        for delta in _local_router().stream([{"role": "user", "content": "hi"}]):
            out.append(delta)
    assert out == ["part"]


def test_text_uses_cloud_after_local_error(monkeypatch):
    local = FakeClient([_http_error(openai.RateLimitError, 429, "slow")])
    cloud = FakeClient([_response("fine")])
    _install(monkeypatch, {"local": local, "cloud": cloud})
    text, usage, provenance = _local_router().text([{"role": "user", "content": "hi"}])
    assert text == "fine" and provenance == {"provider": "cloud", "model": lr.DEFAULT_CLOUD_MODEL, "fallbackUsed": True}


def test_provider_summary_and_lean_schema():
    summary = lr.provider_summary({"ai_mode": "local", "local_llm_base_url": "http://box:8080/v1", "local_llm_model": "slm"})
    assert summary["is_local"] and summary["host"] == "box:8080" and summary["chat_model"] == "slm" and summary["cloud_available"]
    lean = lr.lean_json_schema(Verdict)
    assert lean["additionalProperties"] is False and "description" not in str(lean)
    assert lr.extract_json_object('Sure: ```json\n{"a": 1,}\n```') == {"a": 1}
