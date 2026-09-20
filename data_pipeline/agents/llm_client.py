"""
Async calls to OpenAI-compatible endpoints.

- One client per (base_url, key), with a real timeout and no SDK-level retries.
- Retries only what can succeed on retry: rate limits, timeouts, connection errors, 5xx.
  A 400 or 401 is raised at once.
- A structured-output ladder: `json_schema` response format first, `json_object` when the
  server rejects it (remembered per host), plain text as a last resort; then fence stripping,
  `json.loads`, `json_repair`, and Pydantic validation.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
from dataclasses import dataclass, field

import json_repair
import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from data_pipeline import config
from data_pipeline.endpoints import Endpoint
from data_pipeline.status import TRACKER

_clients: dict[tuple[str, str], AsyncOpenAI] = {}
_json_schema_support: dict[str, bool] = {}

RETRYABLE = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)
_RESPONSE_FORMAT_HINTS = ("response_format", "json_schema", "json_object", "structured", "not supported", "unsupported", "invalid")


class LLMCallError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool, endpoint: Endpoint | None = None, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.endpoint = endpoint
        self.status = status


def get_client(ep: Endpoint) -> AsyncOpenAI:
    key = (ep.base_url, ep.api_key)
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(api_key=ep.api_key, base_url=ep.base_url, timeout=config.REQUEST_TIMEOUT_S, max_retries=0)
        _clients[key] = client
    return client


def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens / 1_000_000) * config.LLM_PRICE_IN + (completion_tokens / 1_000_000) * config.LLM_PRICE_OUT


def _usage(response, ep: Endpoint) -> dict:
    usage = getattr(response, "usage", None)
    p_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
    c_tok = int(getattr(usage, "completion_tokens", 0) or 0)
    return {
        "tokens": p_tok + c_tok, "prompt_tokens": p_tok, "completion_tokens": c_tok,
        "cost": calculate_cost(p_tok, c_tok), "model": ep.model, "host": ep.host,
    }


def _zero_usage(ep: Endpoint) -> dict:
    return {"tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0, "model": ep.model, "host": ep.host}


async def acall_llm(
    ep: Endpoint,
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    max_retries: int = 3,
) -> tuple[str, dict]:
    """One chat completion. Returns (content, usage). Raises LLMCallError."""
    params: dict = {"model": ep.model, "messages": messages, "temperature": temperature}
    if max_tokens:
        params["max_tokens"] = max_tokens
    if response_format:
        params["response_format"] = response_format
    for key, value in ep.extra.items():
        params.setdefault(key, value)

    client = get_client(ep)
    last: LLMCallError | None = None
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(**params)
            config.CONCURRENCY_CONTROLLER.increase()
            content = (response.choices[0].message.content or "").strip() if response.choices else ""
            return content, _usage(response, ep)
        except openai.RateLimitError as e:
            config.CONCURRENCY_CONTROLLER.decrease()
            last = LLMCallError(f"429 from {ep.label}: {e}", retryable=True, endpoint=ep, status=429)
        except RETRYABLE as e:
            if isinstance(e, openai.APITimeoutError):
                config.CONCURRENCY_CONTROLLER.decrease()  # a slow server needs fewer parallel requests, like a rate limit
            status = getattr(e, "status_code", None)
            last = LLMCallError(f"{type(e).__name__} from {ep.label}: {e}", retryable=True, endpoint=ep, status=status)
        except openai.APIStatusError as e:
            raise LLMCallError(f"{e.status_code} from {ep.label}: {e.message}", retryable=False, endpoint=ep, status=e.status_code) from e
        if attempt < max_retries - 1:
            TRACKER.note(f"retry {attempt + 2}/{max_retries} on {ep.host} after {str(last)[:90]}")
            await asyncio.sleep((2 ** attempt) + random.uniform(0, 1))
    assert last is not None
    raise last


# ---------------------------------------------------------------- structured output

@dataclass
class StructuredResult:
    data: dict | None                 # the JSON object the model returned, possibly schema-invalid
    parsed: BaseModel | None          # the validated instance, None when invalid
    error: str | None
    raw: str
    usage: dict
    mode: str                         # json_schema | json_object | text
    messages: list[dict] = field(default_factory=list)


def json_schema_format(schema: type[BaseModel]) -> dict:
    """A lean response_format: descriptions removed, unknown keys forbidden."""
    from data_pipeline.contracts import analysis_json_schema  # local import keeps this module light

    if schema.__name__ == "FeedbackReportSchema":
        body = analysis_json_schema(for_local=True)
    else:
        body = schema.model_json_schema()
        _strip_descriptions(body)
    return {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": body}}


def _strip_descriptions(node) -> None:
    if isinstance(node, dict):
        node.pop("description", None)
        node.pop("title", None)
        if node.get("type") == "object" and "properties" in node:
            node.setdefault("additionalProperties", False)
        for value in node.values():
            _strip_descriptions(value)
    elif isinstance(node, list):
        for item in node:
            _strip_descriptions(item)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def extract_json_object(text: str) -> dict | None:
    """Strip fences, cut to the outermost braces, parse strictly, then with json_repair."""
    if not text:
        return None
    candidate = _FENCE.sub("", text.strip()).strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        candidate = candidate[start:end + 1]
    for loader in (json.loads, json_repair.loads):
        try:
            data = loader(candidate)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, dict) and data:
            return data
    return None


def _is_response_format_rejection(err: LLMCallError) -> bool:
    text = str(err).lower()
    return err.status == 400 and any(hint in text for hint in _RESPONSE_FORMAT_HINTS)


async def acall_structured(
    ep: Endpoint,
    messages: list[dict],
    schema: type[BaseModel],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    max_retries: int = 3,
) -> StructuredResult:
    """Ask for `schema` and validate the reply. Never raises on bad content, only on transport failure."""
    mode = "json_schema" if _json_schema_support.get(ep.base_url, True) else "json_object"
    raw, usage = "", _zero_usage(ep)
    for _ in range(3):
        if mode == "json_schema":
            rf = json_schema_format(schema)
        elif mode == "json_object":
            rf = {"type": "json_object"}
        else:
            rf = None
        try:
            raw, usage = await acall_llm(ep, messages, temperature=temperature, max_tokens=max_tokens, response_format=rf, max_retries=max_retries)
            break
        except LLMCallError as e:
            if mode != "text" and _is_response_format_rejection(e):
                if mode == "json_schema":
                    _json_schema_support[ep.base_url] = False
                    mode = "json_object"
                else:
                    mode = "text"
                continue
            raise

    data = extract_json_object(raw)
    if data is None:
        return StructuredResult(None, None, "the reply contained no JSON object", raw, usage, mode, messages)
    try:
        parsed = schema.model_validate(data)
        return StructuredResult(data, parsed, None, raw, usage, mode, messages)
    except ValidationError as ve:
        error = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in ve.errors()[:5])
        return StructuredResult(data, None, error, raw, usage, mode, messages)


def reset_caches() -> None:
    """For tests."""
    _clients.clear()
    _json_schema_support.clear()
