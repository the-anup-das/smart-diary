import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

from data_pipeline.agents import llm_client
from data_pipeline import config


def _response(content: str, prompt=10, completion=5):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion))


def _http_error(cls, status: int, message: str):
    request = httpx.Request("POST", "http://test.local/v1/chat/completions")
    return cls(message, response=httpx.Response(status, request=request), body=None)


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **params):
        self.calls.append(params)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    llm_client.reset_caches()

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(llm_client.asyncio, "sleep", no_sleep)


def _install(monkeypatch, fake):
    monkeypatch.setattr(llm_client, "get_client", lambda ep: fake)
    return fake


def test_rate_limit_is_retried_and_lowers_concurrency(monkeypatch, endpoint):
    config.CONCURRENCY_CONTROLLER.setup(8)
    fake = _install(monkeypatch, FakeClient([_http_error(openai.RateLimitError, 429, "slow down"), _response("ok")]))
    content, usage = asyncio.run(llm_client.acall_llm(endpoint, [{"role": "user", "content": "hi"}], max_tokens=50))
    assert content == "ok" and usage["tokens"] == 15 and usage["host"] == "test.local"
    assert len(fake.calls) == 2 and fake.calls[0]["max_tokens"] == 50
    assert config.CONCURRENCY_CONTROLLER.current == 4


def test_bad_request_is_not_retried(monkeypatch, endpoint):
    fake = _install(monkeypatch, FakeClient([_http_error(openai.BadRequestError, 400, "bad key name"), _response("never")]))
    with pytest.raises(llm_client.LLMCallError) as info:
        asyncio.run(llm_client.acall_llm(endpoint, [{"role": "user", "content": "hi"}]))
    assert not info.value.retryable and info.value.status == 400 and len(fake.calls) == 1


def test_connection_errors_exhaust_retries(monkeypatch, endpoint):
    request = httpx.Request("POST", "http://test.local")
    fake = _install(monkeypatch, FakeClient([openai.APIConnectionError(request=request)] * 3))
    with pytest.raises(llm_client.LLMCallError) as info:
        asyncio.run(llm_client.acall_llm(endpoint, [{"role": "user", "content": "hi"}]))
    assert info.value.retryable and len(fake.calls) == 3


def test_endpoint_extras_fill_missing_params_only(monkeypatch):
    from data_pipeline.endpoints import Endpoint
    ep = Endpoint(base_url="http://g/v1", api_key="k", model="m", extra={"reasoning_effort": "low", "max_tokens": 800})
    fake = _install(monkeypatch, FakeClient([_response("ok")]))
    asyncio.run(llm_client.acall_llm(ep, [{"role": "user", "content": "hi"}], max_tokens=300))
    assert fake.calls[0]["reasoning_effort"] == "low" and fake.calls[0]["max_tokens"] == 300


class Verdict(BaseModel):
    decision: str
    score: int


def test_structured_downgrades_from_json_schema_to_json_object_and_remembers(monkeypatch, endpoint):
    fake = _install(monkeypatch, FakeClient([
        _http_error(openai.BadRequestError, 400, "response_format json_schema is not supported"),
        _response('```json\n{"decision": "PASS", "score": 9}\n```'),
        _response('{"decision": "FAIL", "score": 2}'),
    ]))
    result = asyncio.run(llm_client.acall_structured(endpoint, [{"role": "user", "content": "judge"}], Verdict))
    assert result.parsed.decision == "PASS" and result.mode == "json_object" and result.error is None
    assert fake.calls[0]["response_format"]["type"] == "json_schema" and fake.calls[1]["response_format"] == {"type": "json_object"}
    # the next call on the same host starts in json_object mode straight away
    second = asyncio.run(llm_client.acall_structured(endpoint, [{"role": "user", "content": "judge"}], Verdict))
    assert second.parsed.decision == "FAIL" and fake.calls[2]["response_format"] == {"type": "json_object"}


def test_structured_repairs_and_reports_validation_errors(monkeypatch, endpoint):
    _install(monkeypatch, FakeClient([_response('{"decision": "PASS", "score": "nine",}')]))
    result = asyncio.run(llm_client.acall_structured(endpoint, [{"role": "user", "content": "x"}], Verdict))
    assert result.data == {"decision": "PASS", "score": "nine"} and result.parsed is None and "score" in result.error
    _install(monkeypatch, FakeClient([_response("I cannot help with that.")]))
    empty = asyncio.run(llm_client.acall_structured(endpoint, [{"role": "user", "content": "x"}], Verdict))
    assert empty.data is None and "no JSON object" in empty.error


def test_analysis_schema_format_is_lean():
    from data_pipeline.contracts import FeedbackReportSchema
    fmt = llm_client.json_schema_format(FeedbackReportSchema)
    body = str(fmt["json_schema"]["schema"])
    assert fmt["json_schema"]["name"] == "FeedbackReportSchema" and "description" not in body and "additionalProperties" in body


class StrictClient(FakeClient):
    """A client whose create() names its parameters, like the OpenAI SDK: unknown ones must travel in extra_body."""

    async def create(self, *, model, messages, temperature=None, max_tokens=None, response_format=None, reasoning_effort=None, extra_body=None):
        return await super().create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, response_format=response_format, reasoning_effort=reasoning_effort, extra_body=extra_body)


def test_unknown_extras_travel_in_extra_body(monkeypatch):
    from data_pipeline.endpoints import Endpoint

    ep = Endpoint(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio", model="openai/gpt-oss-20b")
    fake = _install(monkeypatch, StrictClient([_response("ok")]))
    content, _ = asyncio.run(llm_client.acall_llm(ep, [{"role": "user", "content": "hi"}], max_tokens=50))
    assert content == "ok"
    call = fake.calls[0]
    assert call["reasoning_effort"] == "low" and call["extra_body"] == {"chat_template_kwargs": {"reasoning_effort": "low"}} and call["max_tokens"] == 50


def test_host_that_rejects_extras_is_retried_without_them_and_remembered(monkeypatch):
    from data_pipeline.endpoints import Endpoint

    ep = Endpoint(base_url="http://localhost:1234/v1", api_key="lm-studio", model="google/gemma-4-12b-qat")
    rejected = _http_error(openai.BadRequestError, 400, "Unrecognized request argument supplied: chat_template_kwargs")
    fake = _install(monkeypatch, FakeClient([rejected, _response("ok"), _response("again")]))
    content, _ = asyncio.run(llm_client.acall_llm(ep, [{"role": "user", "content": "hi"}]))
    assert content == "ok"
    assert "chat_template_kwargs" in fake.calls[0] and "chat_template_kwargs" not in fake.calls[1]
    asyncio.run(llm_client.acall_llm(ep, [{"role": "user", "content": "hi"}]))
    assert "chat_template_kwargs" not in fake.calls[2] and len(fake.calls) == 3   # remembered: no extras, no extra round trip


def test_other_bad_requests_still_fail_fast(monkeypatch):
    from data_pipeline.endpoints import Endpoint

    ep = Endpoint(base_url="http://localhost:1234/v1", api_key="lm-studio", model="openai/gpt-oss-20b")
    fake = _install(monkeypatch, FakeClient([_http_error(openai.BadRequestError, 400, "context length exceeded")]))
    with pytest.raises(llm_client.LLMCallError) as info:
        asyncio.run(llm_client.acall_llm(ep, [{"role": "user", "content": "hi"}]))
    assert not info.value.retryable and len(fake.calls) == 1
