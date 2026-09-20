"""
Per-request routing between the configured cloud model and a local OpenAI-compatible server.

The person's preferences win over the environment:
    preferences: ai_mode ("cloud" | "local"), local_llm_base_url, local_llm_model, local_llm_fallback
    environment: USE_LOCAL_LLM, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL, LOCAL_LLM_FALLBACK, LOCAL_LLM_TIMEOUT,
                 OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, OPENAI_TIMEOUT

Nothing is resolved at import time. Structured output uses a ladder: OpenAI's native parse for
api.openai.com, otherwise a `json_schema` response format, downgraded to `json_object` and then
plain text when a server rejects it (remembered per host), followed by strict parsing, repair,
Pydantic validation, one retry with the validation errors fed back, and optional business rules
that get one correction turn before the answer is accepted anyway. When the local model fails
and the person allowed it, the same request is repeated on the cloud model.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional
from urllib.parse import urlparse

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

try:  # optional: mends trailing commas and truncated objects from small models
    import json_repair
except ImportError:  # pragma: no cover
    json_repair = None

DEFAULT_LOCAL_BASE_URL = "http://llm-server:8080/v1"
DEFAULT_LOCAL_MODEL = "smart-diary-slm"
DEFAULT_CLOUD_MODEL = "gpt-4o-mini"
_RESPONSE_FORMAT_HINTS = ("response_format", "json_schema", "json_object", "structured", "not supported", "unsupported", "invalid")
_clients: dict[tuple, OpenAI] = {}
_json_schema_support: dict[str, bool] = {}


class LLMUnavailable(Exception):
    """The configured model could not produce a usable answer."""


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class RouteConfig:
    provider: str                     # "cloud" | "local"
    base_url: Optional[str]
    api_key: str
    model: str
    timeout_s: float = 90.0
    fallback_to_cloud: bool = False

    @property
    def host(self) -> str:
        if self.base_url:
            return urlparse(self.base_url).netloc or self.base_url
        return "api.openai.com"

    @property
    def is_native_openai(self) -> bool:
        return self.provider == "cloud" and not self.base_url


def cloud_route() -> RouteConfig:
    return RouteConfig(
        provider="cloud",
        base_url=(os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/") or None,
        api_key=os.getenv("OPENAI_API_KEY") or "empty",
        model=os.getenv("CHAT_MODEL", DEFAULT_CLOUD_MODEL),
        timeout_s=float(os.getenv("OPENAI_TIMEOUT", "90")),
    )


def cloud_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) or bool(os.getenv("OPENAI_BASE_URL"))


def _valid_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def env_defaults() -> dict:
    return {
        "use_local": _truthy(os.getenv("USE_LOCAL_LLM", "false")),
        "local_base_url": (os.getenv("LOCAL_LLM_BASE_URL") or DEFAULT_LOCAL_BASE_URL).strip().rstrip("/"),
        "local_model": (os.getenv("LOCAL_LLM_MODEL") or DEFAULT_LOCAL_MODEL).strip(),
        "fallback": _truthy(os.getenv("LOCAL_LLM_FALLBACK", "true")),
        "timeout": float(os.getenv("LOCAL_LLM_TIMEOUT", "180")),
    }


def resolve_route(preferences: dict | None = None) -> RouteConfig:
    """The route for one request. A local mode with an unusable URL falls back to the cloud route."""
    prefs = preferences or {}
    env = env_defaults()
    mode = (prefs.get("ai_mode") or ("local" if env["use_local"] else "cloud")).strip().lower()
    if mode != "local":
        return cloud_route()
    base_url = (prefs.get("local_llm_base_url") or env["local_base_url"]).strip().rstrip("/")
    if not _valid_http_url(base_url):
        return cloud_route()
    fallback = prefs.get("local_llm_fallback")
    fallback = env["fallback"] if fallback is None else _truthy(fallback)
    return RouteConfig(
        provider="local",
        base_url=base_url,
        api_key=os.getenv("LOCAL_LLM_API_KEY") or "empty",
        model=(prefs.get("local_llm_model") or env["local_model"]).strip() or DEFAULT_LOCAL_MODEL,
        timeout_s=env["timeout"],
        fallback_to_cloud=fallback and cloud_available(),
    )


def _client_for(route: RouteConfig) -> OpenAI:
    key = (route.base_url, route.api_key, route.timeout_s)
    client = _clients.get(key)
    if client is None:
        client = OpenAI(api_key=route.api_key, base_url=route.base_url, timeout=route.timeout_s, max_retries=1)
        _clients[key] = client
    return client


def usage_dict(response) -> dict:
    usage = getattr(response, "usage", None)
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or 0) or prompt + completion
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _add_usage(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}


def _strip_schema(node) -> None:
    if isinstance(node, dict):
        for key in ("description", "title", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "examples"):
            node.pop(key, None)
        if node.get("type") == "object" and "properties" in node:
            node.setdefault("additionalProperties", False)
        for value in node.values():
            _strip_schema(value)
    elif isinstance(node, list):
        for item in node:
            _strip_schema(item)


def lean_json_schema(schema: type[BaseModel]) -> dict:
    """The schema without descriptions and numeric bounds: a smaller grammar, and Pydantic checks the bounds after."""
    body = schema.model_json_schema()
    _strip_schema(body)
    return body


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def extract_json_object(text: str) -> dict | None:
    if not text:
        return None
    candidate = _FENCE.sub("", text.strip()).strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        candidate = candidate[start:end + 1]
    loaders = [json.loads] + ([json_repair.loads] if json_repair else [])
    for loader in loaders:
        try:
            data = loader(candidate)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, dict) and data:
            return data
    return None


def _format_validation_error(ve: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in ve.errors()[:5])


def _mentions_response_format(err: Exception) -> bool:
    text = str(err).lower()
    return any(hint in text for hint in _RESPONSE_FORMAT_HINTS)


@dataclass
class StructuredResult:
    parsed: BaseModel
    usage: dict
    provider: str
    model: str
    fallback_used: bool = False
    mode: str = "native"
    attempts: int = 1
    rule_problems: list[str] = field(default_factory=list)

    @property
    def provenance(self) -> dict:
        return {"provider": self.provider, "model": self.model, "fallbackUsed": self.fallback_used, "mode": self.mode}


class LLMRouter:
    def __init__(self, route: RouteConfig):
        self.route = route

    # ------------------------------------------------------------------ helpers
    def _routes(self) -> list[RouteConfig]:
        if self.route.provider == "local" and self.route.fallback_to_cloud:
            return [self.route, cloud_route()]
        return [self.route]

    @staticmethod
    def _complete(client: OpenAI, route: RouteConfig, messages: list[dict], schema: type[BaseModel], temperature: float, max_tokens: int | None):
        """One structured request. Returns (mode, payload, usage); payload is a parsed model for 'native', else text."""
        extra = {"max_tokens": max_tokens} if max_tokens else {}
        try:
            if route.is_native_openai:
                parse = getattr(client.chat.completions, "parse", None) or client.beta.chat.completions.parse
                response = parse(model=route.model, messages=messages, response_format=schema, temperature=temperature, **extra)
                choice = response.choices[0] if response.choices else None
                parsed = getattr(getattr(choice, "message", None), "parsed", None)
                if parsed is None:
                    detail = getattr(getattr(choice, "message", None), "refusal", None) or getattr(choice, "finish_reason", "unknown")
                    raise LLMUnavailable(f"no structured answer ({detail})")
                return "native", parsed, usage_dict(response)
            mode = "json_schema" if _json_schema_support.get(route.base_url or "", True) else "json_object"
            for _ in range(3):
                if mode == "json_schema":
                    response_format = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": lean_json_schema(schema)}}
                elif mode == "json_object":
                    response_format = {"type": "json_object"}
                else:
                    response_format = None
                try:
                    response = client.chat.completions.create(
                        model=route.model, messages=messages, temperature=temperature,
                        **({"response_format": response_format} if response_format else {}), **extra,
                    )
                    content = (response.choices[0].message.content or "") if response.choices else ""
                    return mode, content, usage_dict(response)
                except openai.BadRequestError as e:
                    if mode != "text" and _mentions_response_format(e):
                        if mode == "json_schema":
                            _json_schema_support[route.base_url or ""] = False
                            mode = "json_object"
                        else:
                            mode = "text"
                        continue
                    raise
            raise LLMUnavailable("could not agree a response format with the server")
        except LLMUnavailable:
            raise
        except openai.OpenAIError as e:
            raise LLMUnavailable(f"{type(e).__name__}: {str(e)[:240]}") from e

    def _structured_on(self, route: RouteConfig, schema, messages, temperature, max_tokens, rules) -> StructuredResult:
        client = _client_for(route)
        msgs = list(messages)
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        soft_result: StructuredResult | None = None
        last_error = "no answer"
        for attempt in (1, 2):
            mode, payload, usage = self._complete(client, route, msgs, schema, temperature, max_tokens)
            total_usage = _add_usage(total_usage, usage)
            if mode == "native":
                parsed, error, raw = payload, None, payload.model_dump_json()
            else:
                raw = payload
                data = extract_json_object(payload)
                if data is None:
                    parsed, error = None, "the reply contained no JSON object"
                else:
                    try:
                        parsed, error = schema.model_validate(data), None
                    except ValidationError as ve:
                        parsed, error = None, _format_validation_error(ve)
            if parsed is None:
                last_error = error or "unusable reply"
                msgs = msgs + [
                    {"role": "assistant", "content": raw[:6000] if isinstance(raw, str) else ""},
                    {"role": "user", "content": f"That reply was rejected: {last_error}\nReturn only the corrected JSON object."},
                ]
                continue
            problems = list(rules(parsed)) if rules else []
            result = StructuredResult(parsed, total_usage, route.provider, route.model, False, mode, attempt, problems)
            if problems and attempt == 1:
                soft_result = result
                msgs = msgs + [
                    {"role": "assistant", "content": parsed.model_dump_json()},
                    {"role": "user", "content": "Fix these problems and return only the corrected JSON object:\n- " + "\n- ".join(problems)},
                ]
                continue
            return result
        if soft_result is not None:
            soft_result.usage = total_usage
            soft_result.attempts = 2
            return soft_result
        raise LLMUnavailable(f"{route.model} on {route.host}: {last_error}")

    # ------------------------------------------------------------------ public API
    def structured(self, schema: type[BaseModel], messages: list[dict], *, temperature: float = 0.2, max_tokens: int | None = 2048,
                   rules: Callable[[BaseModel], list[str]] | None = None) -> StructuredResult:
        """A validated `schema` instance, from the configured model or, when allowed, the cloud fallback."""
        try:
            return self._structured_on(self.route, schema, messages, temperature, max_tokens, rules)
        except LLMUnavailable as e:
            if self.route.provider == "local" and self.route.fallback_to_cloud:
                print(f"[llm] local model failed ({e}); using the cloud model for this request", flush=True)
                result = self._structured_on(cloud_route(), schema, messages, temperature, max_tokens, rules)
                result.fallback_used = True
                return result
            raise

    def text(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int | None = None) -> tuple[str, dict, dict]:
        """Plain completion. Returns (text, usage, provenance)."""
        last: Exception | None = None
        routes = self._routes()
        for i, route in enumerate(routes):
            try:
                response = _client_for(route).chat.completions.create(
                    model=route.model, messages=messages, temperature=temperature, **({"max_tokens": max_tokens} if max_tokens else {}),
                )
                content = (response.choices[0].message.content or "").strip() if response.choices else ""
                return content, usage_dict(response), {"provider": route.provider, "model": route.model, "fallbackUsed": i > 0}
            except openai.OpenAIError as e:
                last = e
                if i < len(routes) - 1:
                    print(f"[llm] {route.model} on {route.host} failed ({type(e).__name__}); trying the cloud model", flush=True)
        raise LLMUnavailable(f"{type(last).__name__}: {str(last)[:240]}" if last else "no route")

    def stream(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int | None = None) -> Iterator[str]:
        """Token deltas. Falls back to the cloud model only when the local one fails before its first token."""
        routes = self._routes()
        for i, route in enumerate(routes):
            started = False
            try:
                stream = _client_for(route).chat.completions.create(
                    model=route.model, messages=messages, temperature=temperature, stream=True,
                    **({"max_tokens": max_tokens} if max_tokens else {}),
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        started = True
                        yield delta
                return
            except openai.OpenAIError as e:
                if started or i == len(routes) - 1:
                    raise LLMUnavailable(f"{type(e).__name__}: {str(e)[:240]}") from e
                print(f"[llm] {route.model} on {route.host} failed before streaming ({type(e).__name__}); trying the cloud model", flush=True)


def get_router(preferences: dict | None = None) -> LLMRouter:
    return LLMRouter(resolve_route(preferences))


class _Probe(BaseModel):
    ok: bool


def probe(base_url: str | None, model: str, api_key: str = "empty", timeout: float = 15.0) -> dict:
    """Check a server: list models, one tiny completion, and whether it honours a JSON-schema response format."""
    result: dict = {"ok": False, "base_url": base_url, "model": model, "models_listed": [], "model_found": None, "json_schema": None, "latency_ms": None, "error": None}
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
        try:
            listed = [m.id for m in client.models.list().data][:40]
            result["models_listed"] = listed
            result["model_found"] = model in listed if listed else None
        except openai.OpenAIError:
            pass
        started = time.monotonic()
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=5)
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        result["reply"] = ((response.choices[0].message.content or "") if response.choices else "").strip()[:40]
        result["served_model"] = getattr(response, "model", None)
        result["ok"] = True
        try:
            schema_response = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": "Return a JSON object with ok set to true."}], max_tokens=40,
                response_format={"type": "json_schema", "json_schema": {"name": "Probe", "schema": lean_json_schema(_Probe)}},
            )
            content = (schema_response.choices[0].message.content or "") if schema_response.choices else ""
            data = extract_json_object(content)
            result["json_schema"] = bool(data and data.get("ok") is True)
        except openai.BadRequestError:
            result["json_schema"] = False
        except openai.OpenAIError:
            result["json_schema"] = None
    except openai.OpenAIError as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    return result


def provider_summary(preferences: dict | None = None) -> dict:
    """What the settings page shows."""
    route = resolve_route(preferences)
    env = env_defaults()
    return {
        "mode": route.provider,
        "host": route.host,
        "chat_model": route.model,
        "is_local": route.provider == "local",
        "fallback_to_cloud": route.fallback_to_cloud,
        "cloud_available": cloud_available(),
        "cloud_model": cloud_route().model,
        "json_schema_supported": _json_schema_support.get(route.base_url or "") if route.base_url else True,
        "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        "embedding_host": urlparse(os.getenv("EMBEDDING_BASE_URL") or "").netloc or "api.openai.com",
        "server_defaults": {"local_base_url": env["local_base_url"], "local_model": env["local_model"], "use_local": env["use_local"], "fallback": env["fallback"]},
    }


def reset_caches() -> None:
    """For tests."""
    _clients.clear()
    _json_schema_support.clear()
