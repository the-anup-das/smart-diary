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
import inspect
import json
import random
import re
import time
from dataclasses import dataclass, field

import json_repair
import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from data_pipeline import config
from data_pipeline.endpoints import Endpoint, host_limiter, reset_host_limiters
from data_pipeline.metrics import METRICS
from data_pipeline.status import TRACKER

_clients: dict[tuple[str, str], AsyncOpenAI] = {}
_json_schema_support: dict[str, bool] = {}

RETRYABLE = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)
_extras_rejected: set[str] = set()          # hosts that answered 400 to the endpoint's extra parameters
_create_params: dict[type, set[str] | None] = {}   # per client class: named parameters of chat.completions.create
_REJECTED_HINTS = ("unrecognized", "unsupported", "unknown", "not permitted", "extra field", "not allowed", "invalid parameter", "unexpected")
# Queue order at a shared host: the later a stage, the sooner it goes, so samples finish before new ones start.
STAGE_PRIORITY = {"writer": 0, "reviewer": 1, "editor": 2, "analyzer": 3, "judge": 4, "judge2": 5}


def stage_priority(role: str) -> int:
    role = (role or "").lower()
    if role.startswith("judge2"):
        return STAGE_PRIORITY["judge2"]
    if role.startswith("judge"):
        return STAGE_PRIORITY["judge"]
    return STAGE_PRIORITY.get(role, 0)


def _request_kwargs(client, params: dict) -> dict:
    """Named parameters go to `create` directly; anything the SDK does not know goes in `extra_body`."""
    create = client.chat.completions.create
    key = type(client)
    if key not in _create_params:
        try:
            signature = inspect.signature(create)
        except (TypeError, ValueError):
            _create_params[key] = None
        else:
            accepts_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())
            _create_params[key] = None if accepts_any else set(signature.parameters)
    known = _create_params[key]
    if known is None:
        return dict(params)
    direct = {k: v for k, v in params.items() if k in known}
    body = {k: v for k, v in params.items() if k not in known}
    if body:
        direct["extra_body"] = {**(direct.get("extra_body") or {}), **body}
    return direct


def _extras_rejected_error(e: Exception, extra: dict) -> bool:
    text = str(e).lower()
    return any(k.lower() in text for k in extra) or any(hint in text for hint in _REJECTED_HINTS)
_RESPONSE_FORMAT_HINTS = ("response_format", "json_schema", "json_object", "structured", "not supported", "unsupported", "invalid")


PERMANENT_STATUSES = (401, 402, 403, 404)   # a key, a bill, a permission or a model id: retrying cannot help
LONG_COOLDOWN_S = 3600.0                      # for a host that is out of quota or permanently refusing


def cooldown_for(error: "LLMCallError") -> float | None:
    """How long a failing host should sit out: hours for a permanent refusal or an exhausted quota, else the pool's default."""
    if error.status in PERMANENT_STATUSES:
        return 10 * LONG_COOLDOWN_S
    text = str(error).lower()
    if error.status == 429 and ("quota" in text or "billing" in text or "exceeded your current" in text):
        return LONG_COOLDOWN_S
    return None


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

    extras_sent = bool(ep.extra) and ep.host not in _extras_rejected
    if not extras_sent:
        for key in ep.extra:
            params.pop(key, None)

    client = get_client(ep)
    mode = config.host_model_mode(ep.host)
    # Separate backends per model: count per model. One GPU behind them: count per host, and in
    # "shared" mode let only one model run at a time so the server never holds two of them.
    limiter_key = f"{ep.host}#{ep.model}" if mode == "separate" else ep.host
    limiter = host_limiter(limiter_key, config.host_limit(ep.host, ep.model if mode == "separate" else None), config.HOST_PACING_S, mode == "shared")
    last: LLMCallError | None = None
    for attempt in range(max_retries):
        try:
            queued = limiter.waiting
            swapping = limiter.blocked_by_model(ep.model)
            started = time.monotonic()
            async with limiter.slot(ep.model, stage_priority(getattr(ep, "name", ""))):
                waited = time.monotonic() - started
                if waited > 1.0 and (queued or swapping):
                    reason = f"{ep.host} was busy with another model" if swapping else f"{ep.host} takes {limiter.limit} at a time, {queued} queued"
                    TRACKER.note(f"waited {waited:.0f}s: {reason}")
                call_started = METRICS.start(ep)
                try:
                    response = await client.chat.completions.create(**_request_kwargs(client, params))
                except Exception as e:  # noqa: BLE001  recorded, then handled by the retry policy below
                    METRICS.finish(ep, call_started, error=f"{type(e).__name__}: {e}", timeout=isinstance(e, openai.APITimeoutError))
                    raise
            config.CONCURRENCY_CONTROLLER.increase()
            content = (response.choices[0].message.content or "").strip() if response.choices else ""
            usage = _usage(response, ep)
            METRICS.finish(ep, call_started, usage=usage)
            return content, usage
        except openai.RateLimitError as e:
            config.CONCURRENCY_CONTROLLER.decrease()
            last = LLMCallError(f"429 from {ep.label}: {e}", retryable=True, endpoint=ep, status=429)
        except RETRYABLE as e:
            if isinstance(e, openai.APITimeoutError):
                config.CONCURRENCY_CONTROLLER.decrease()  # a slow server needs fewer parallel requests, like a rate limit
            status = getattr(e, "status_code", None)
            last = LLMCallError(f"{type(e).__name__} from {ep.label}: {e}", retryable=True, endpoint=ep, status=status)
        except openai.BadRequestError as e:
            if extras_sent and _extras_rejected_error(e, ep.extra):
                # The host does not take this model family's extra parameters (reasoning effort, thinking switch):
                # send the request again without them and remember that for the host.
                _extras_rejected.add(ep.host)
                extras_sent = False
                for key in ep.extra:
                    params.pop(key, None)
                TRACKER.note(f"{ep.host} rejected the extra parameters {sorted(ep.extra)}; retrying without them")
                continue
            raise LLMCallError(f"{e.status_code} from {ep.label}: {e.message}", retryable=False, endpoint=ep, status=e.status_code) from e
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


# Hosts whose replies show response_format was accepted but not enforced (prose around the JSON,
# missing required fields, wrong types). Their calls carry the schema in the prompt instead.
_schema_ignored: set[str] = set()
_STRUCTURAL_ERRORS = ("Field required", "Input should be a valid", "Extra inputs are not permitted")


def _inline_refs(node, defs: dict):
    """Replace every $ref with the definition it points at, so a model reads one self-contained schema."""
    if isinstance(node, dict):
        if "$ref" in node:
            # pydantic puts the field's description next to the reference; keep it on the inlined object
            target = dict(defs.get(node["$ref"].split("/")[-1], {}))
            target.update({k: v for k, v in node.items() if k != "$ref"})
            return _inline_refs(target, defs)
        return {k: _inline_refs(v, defs) for k, v in node.items() if k not in ("$defs", "title")}
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    return node


def schema_instruction(schema: type[BaseModel]) -> str:
    """The schema as text, descriptions kept: for a model the server will not constrain, they are the guidance."""
    body = schema.model_json_schema()
    body = _inline_refs(body, body.get("$defs", {}))
    return (
        "Reply with one JSON object and nothing else: no prose before or after it and no code fences. "
        "It must match this JSON Schema exactly: every required field present, every value of the type shown, "
        "and every array of objects filled with objects that have the listed keys, never plain strings.\n"
        + json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    )


def with_schema(messages: list[dict], schema: type[BaseModel]) -> list[dict]:
    """A copy of the messages with the schema appended to the system message (or added as one)."""
    out = [dict(m) for m in messages]
    text = schema_instruction(schema)
    if out and out[0].get("role") == "system":
        out[0]["content"] = f"{out[0]['content']}\n\n{text}"
    else:
        out.insert(0, {"role": "system", "content": text})
    return out


def _looks_unenforced(raw: str, error: str | None) -> bool:
    """A constrained decoder only emits the object itself and cannot leave out a required field."""
    if error is None:
        return False
    stripped = (raw or "").strip()
    return not (stripped.startswith("{") and stripped.endswith("}")) or any(s in error for s in _STRUCTURAL_ERRORS)


def _add_usage(a: dict, b: dict) -> dict:
    out = dict(a)
    for k in ("tokens", "prompt_tokens", "completion_tokens", "cost"):
        out[k] = (a.get(k) or 0) + (b.get(k) or 0)
    return out


def _validate(raw: str, schema: type[BaseModel]) -> tuple[dict | None, BaseModel | None, str | None]:
    data = extract_json_object(raw)
    if data is None:
        return None, None, "the reply contained no JSON object"
    try:
        return data, schema.model_validate(data), None
    except ValidationError as ve:
        return data, None, "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in ve.errors()[:5])


# ---------------------------------------------------------------- lenient text fields

def as_text(value):
    """Free-text fields from models that answer with a list, an object or null instead of a string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(v).strip() for v in value if v is not None and str(v).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


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
    """Ask for `schema` and validate the reply. Never raises on bad content, only on transport failure.

    The schema travels in response_format. A host that accepts that field but does not enforce it
    (the reply has prose around the JSON, a missing required field or a wrong type) is remembered,
    the same request is sent once more with the schema written into the prompt, and every later
    call to that host carries the schema in the prompt from the start.
    """
    key = f"{ep.base_url}|{ep.model}"
    mode = "json_schema" if _json_schema_support.get(ep.base_url, True) else "json_object"

    async def attempt(schema_in_prompt: bool) -> tuple[str, dict, list[dict]]:
        nonlocal mode
        for _ in range(3):
            send = with_schema(messages, schema) if (schema_in_prompt or mode != "json_schema") else messages
            if mode == "json_schema":
                rf = json_schema_format(schema)
            elif mode == "json_object":
                rf = {"type": "json_object"}
            else:
                rf = None
            try:
                raw, usage = await acall_llm(ep, send, temperature=temperature, max_tokens=max_tokens, response_format=rf, max_retries=max_retries)
                return raw, usage, send
            except LLMCallError as e:
                if mode != "text" and _is_response_format_rejection(e):
                    if mode == "json_schema":
                        _json_schema_support[ep.base_url] = False
                        mode = "json_object"
                    else:
                        mode = "text"
                    continue
                raise
        return "", _zero_usage(ep), messages

    known = key in _schema_ignored
    raw, usage, sent = await attempt(known)
    data, parsed, error = _validate(raw, schema)
    if error and not known and mode == "json_schema" and _looks_unenforced(raw, error):
        _schema_ignored.add(key)
        TRACKER.note(f"{ep.host} ignores the JSON schema for {ep.model}; sending it in the prompt from now on")
        try:
            raw2, usage2, sent2 = await attempt(True)
        except LLMCallError:
            return StructuredResult(data, parsed, error, raw, usage, mode, sent)
        usage = _add_usage(usage, usage2)
        raw, sent = raw2, sent2
        data, parsed, error = _validate(raw, schema)
    return StructuredResult(data, parsed, error, raw, usage, mode, sent)


def reset_caches() -> None:
    """For tests."""
    _clients.clear()
    _json_schema_support.clear()
    _extras_rejected.clear()
    _create_params.clear()
    _schema_ignored.clear()
    reset_host_limiters()
    METRICS.reset()
