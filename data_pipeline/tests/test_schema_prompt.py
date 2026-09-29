"""A host that accepts response_format but ignores it gets the schema in the prompt."""
import asyncio
import json

import pytest
from pydantic import BaseModel

from data_pipeline import config
from data_pipeline.agents import llm_client
from data_pipeline.agents.reviewer import ReviewVerdict
from data_pipeline.contracts import FeedbackReportSchema
from data_pipeline.endpoints import Endpoint
from test_llm_client import FakeClient, _response


class Reframe(BaseModel):
    negativeThought: str
    reframe: str


class Report(BaseModel):
    mood: int
    reframes: list[Reframe]


GOOD = json.dumps({"mood": 6, "reframes": [{"negativeThought": "I failed", "reframe": "I tried"}]})
BAD = "Sure! Here is the analysis:\n```json\n" + json.dumps({"reframes": ["I failed -> I tried"]}) + "\n```"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    llm_client.reset_caches()
    monkeypatch.setattr(config, "HOST_PACING_S", 0.0)

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(llm_client.asyncio, "sleep", no_sleep)


def _ep():
    return Endpoint(base_url="https://gateway.example/v1", api_key="k", model="nova-pro", name="analyzer")


def _system(call) -> str:
    return call["messages"][0]["content"] if call["messages"][0]["role"] == "system" else ""


def test_an_unenforced_reply_is_retried_once_with_the_schema_in_the_prompt(monkeypatch):
    fake = FakeClient([_response(BAD), _response(GOOD), _response(GOOD)])
    monkeypatch.setattr(llm_client, "get_client", lambda ep: fake)
    messages = [{"role": "system", "content": "Analyse the entry."}, {"role": "user", "content": "An entry."}]

    result = asyncio.run(llm_client.acall_structured(_ep(), messages, Report))
    assert result.parsed is not None and result.parsed.mood == 6
    assert len(fake.calls) == 2
    assert "JSON Schema" not in _system(fake.calls[0])                       # first try: the schema only in response_format
    assert "JSON Schema" in _system(fake.calls[1]) and '"negativeThought"' in _system(fake.calls[1])
    assert result.usage["completion_tokens"] == 10                           # both calls are counted

    asyncio.run(llm_client.acall_structured(_ep(), messages, Report))
    assert len(fake.calls) == 3 and "JSON Schema" in _system(fake.calls[2])   # remembered: from the start next time
    assert messages[0]["content"] == "Analyse the entry."                     # the caller's messages are untouched


def test_an_enforcing_host_never_sees_the_schema_in_the_prompt(monkeypatch):
    fake = FakeClient([_response(GOOD), _response(GOOD)])
    monkeypatch.setattr(llm_client, "get_client", lambda ep: fake)
    messages = [{"role": "user", "content": "An entry."}]
    for _ in range(2):
        assert asyncio.run(llm_client.acall_structured(_ep(), messages, Report)).parsed is not None
    assert all(c["messages"][0]["role"] == "user" for c in fake.calls)


def test_a_host_that_stays_wrong_returns_the_error_after_one_retry(monkeypatch):
    fake = FakeClient([_response(BAD), _response(BAD)])
    monkeypatch.setattr(llm_client, "get_client", lambda ep: fake)
    result = asyncio.run(llm_client.acall_structured(_ep(), [{"role": "user", "content": "x"}], Report))
    assert result.parsed is None and "mood" in result.error and len(fake.calls) == 2
    assert result.messages[0]["role"] == "system" and "JSON Schema" in result.messages[0]["content"]


def test_the_prompt_schema_is_self_contained_and_keeps_descriptions():
    text = llm_client.schema_instruction(FeedbackReportSchema)
    body = json.loads(text[text.index("{"):])
    assert "$ref" not in text and "$defs" not in body
    reframes = body["properties"]["cognitiveReframes"]
    assert reframes["type"] == "array" and set(reframes["items"]["required"]) == {"negativeThought", "reframe"}
    assert "selfFocusScore" in body["required"] and reframes.get("description")
    assert "never plain strings" in text


def test_free_text_verdict_fields_accept_a_list_or_null():
    assert ReviewVerdict.model_validate({"approved": False, "critique": ["Too tidy.", "Add a detail."]}).critique == "Too tidy. Add a detail."
    assert ReviewVerdict.model_validate({"approved": True, "critique": None}).critique == ""
    from data_pipeline.agents.judge import JudgeVerdict

    verdict = JudgeVerdict.model_validate({
        "own_mood": 6, "own_rumination": "low", "own_distress": False,
        "grounding": 9, "safety": 10, "cbt_quality": 8, "schema_semantics": 9, "persona_adherence": 10, "overall": 9,
        "hard_fail": False, "hard_fail_reason": None, "entry_notes": [], "label_notes": ["mood too low", "topics off"],
    })
    assert verdict.hard_fail_reason == "" and verdict.entry_notes == "" and verdict.label_notes == "mood too low topics off"
