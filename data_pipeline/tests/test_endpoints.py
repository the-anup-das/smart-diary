import asyncio
import time

import pytest

from data_pipeline.endpoints import EndpointPool, RateLimiter, parse_endpoint, parse_endpoint_list, resolve_key


def test_parse_endpoint_with_env_key_literal_key_and_extras(monkeypatch):
    monkeypatch.setenv("MY_KEY", "sk-abc")
    ep = parse_endpoint('https://host.example/v1/|env:MY_KEY|model-x|{"reasoning_effort":"low","rpm":5,"max_tokens":800}', name="judge")
    assert ep.base_url == "https://host.example/v1" and ep.api_key == "sk-abc" and ep.model == "model-x"
    assert ep.rpm == 5 and ep.extra == {"reasoning_effort": "low", "max_tokens": 800}
    assert ep.host == "host.example" and ep.label == "model-x@host.example"
    literal = parse_endpoint("http://localhost:1234/v1|lm-studio|gemma")
    assert literal.api_key == "lm-studio" and literal.rpm is None and literal.extra == {}


def test_missing_env_key_skips_the_entry(monkeypatch):
    monkeypatch.delenv("NOPE_KEY", raising=False)
    assert parse_endpoint("https://a/v1|env:NOPE_KEY|m") is None
    monkeypatch.setenv("YES_KEY", "k")
    eps = parse_endpoint_list("https://a/v1|env:NOPE_KEY|m; https://b/v1|env:YES_KEY|m2 ;", name="judge")
    assert [e.host for e in eps] == ["b"] and eps[0].name == "judge2"
    assert resolve_key("") == "empty"


def test_bad_spec_raises():
    with pytest.raises(ValueError):
        parse_endpoint("only-two|parts")
    with pytest.raises(ValueError):
        parse_endpoint("https://a/v1|k|m|[1,2]")


def test_pool_rotates_on_penalty_and_recovers():
    eps = parse_endpoint_list("https://a/v1|k|m;https://b/v1|k|m")
    pool = EndpointPool(eps, cooldown_s=0.05)
    first = pool.pick()
    assert first.host == "a"
    pool.penalise(first)
    assert pool.pick().host == "b"
    assert pool.pick(exclude={eps[1]}) is None
    assert pool.seconds_until_available() == 0.0  # b is still free
    pool.penalise(eps[1])
    assert pool.pick() is None and 0 < pool.seconds_until_available() <= 0.05
    time.sleep(0.06)
    assert pool.pick().host == "a"


def test_rate_limiter_spaces_calls():
    limiter = RateLimiter(rpm=1200)  # 50 ms apart

    async def run():
        start = time.monotonic()
        for _ in range(3):
            await limiter.wait()
        return time.monotonic() - start

    elapsed = asyncio.run(run())
    assert elapsed >= 0.09
