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
    time.sleep(0.12)   # well past the cooldown: the Windows clock ticks every 16 ms
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


def test_model_family_defaults_for_reasoning(monkeypatch):
    from data_pipeline import config
    from data_pipeline.endpoints import Endpoint, default_extras, is_local_host

    assert is_local_host("http://127.0.0.1:1234/v1") and is_local_host("http://llm-server:8080/v1") and is_local_host("http://192.168.1.20:8080/v1")
    assert not is_local_host("https://api.cerebras.ai/v1") and not is_local_host("https://api.eolarityinnovations.com/v1")

    local_oss = Endpoint(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio", model="openai/gpt-oss-20b")
    assert local_oss.extra == {"reasoning_effort": "low", "chat_template_kwargs": {"reasoning_effort": "low"}}
    remote_oss = Endpoint(base_url="https://api.cerebras.ai/v1", api_key="k", model="gpt-oss-120b")
    assert remote_oss.extra == {"reasoning_effort": "low"}
    gemma_local = Endpoint(base_url="http://localhost:1234/v1", api_key="lm-studio", model="google/gemma-4-12b-qat")
    assert gemma_local.extra == {"chat_template_kwargs": {"enable_thinking": False}}
    assert Endpoint(base_url="https://api.eolarityinnovations.com/v1", api_key="k", model="Qwen/Qwen3-30B-A3B-Instruct-2507").extra == {}
    assert default_extras("Ternary-Bonsai-2-27B", "https://api.eolarityinnovations.com/v1") == {}

    explicit = Endpoint(base_url="http://localhost:1234/v1", api_key="lm-studio", model="openai/gpt-oss-20b", extra={"reasoning_effort": "high"})
    assert explicit.extra["reasoning_effort"] == "high" and explicit.extra["chat_template_kwargs"] == {"reasoning_effort": "low"}
    spec = parse_endpoint('http://localhost:1234/v1|lm-studio|google/gemma-4-26b-a4b|{"chat_template_kwargs": {"enable_thinking": true}, "rpm": 30}')
    assert spec.extra == {"chat_template_kwargs": {"enable_thinking": True}} and spec.rpm == 30

    monkeypatch.setenv("REVIEWER_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("REVIEWER_API_KEY", "lm-studio")
    monkeypatch.setenv("REVIEWER_EXTRA", '{"reasoning_effort": "medium"}')
    reviewer = config.role_endpoint("reviewer", "openai/gpt-oss-20b")
    assert reviewer.extra == {"reasoning_effort": "medium", "chat_template_kwargs": {"reasoning_effort": "low"}} and reviewer.host == "127.0.0.1:1234"
    monkeypatch.setenv("REVIEWER_EXTRA", "[1, 2]")
    with pytest.raises(SystemExit):
        config.role_endpoint("reviewer", "openai/gpt-oss-20b")


def test_host_limiter_caps_parallel_requests_and_paces_starts():
    import asyncio
    import time

    from data_pipeline.endpoints import HostLimiter, host_limiter, reset_host_limiters

    async def scenario():
        limiter = HostLimiter(2, pacing_s=0.1)      # coarse Windows timers: keep every interval well above 16 ms
        peak = 0
        active = 0
        starts = []

        async def request():
            nonlocal peak, active
            async with limiter.slot():
                starts.append(time.monotonic())
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.3)      # longer than the pacing, so two requests overlap
                active -= 1

        await asyncio.gather(*(request() for _ in range(5)))
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        return peak, gaps, limiter.waiting

    peak, gaps, waiting = asyncio.run(scenario())
    assert peak == 2 and waiting == 0 and all(g >= 0.05 for g in gaps)   # never more than two at once, starts spaced out

    async def registry():
        reset_host_limiters()
        a = host_limiter("api.example.com", 2, 0.5)
        assert host_limiter("api.example.com", 2, 0.5) is a          # same host, same settings: one limiter shared by all callers
        assert host_limiter("api.example.com", 1, 0.5) is not a      # changed settings: a fresh one
        assert host_limiter("127.0.0.1:1234", 2, 0.5) is not a
        return True

    assert asyncio.run(registry())


def test_host_limits_from_env(monkeypatch):
    from data_pipeline import config

    assert config._parse_host_limits("api.example.com=2; 127.0.0.1:1234=1") == {"api.example.com": 2, "127.0.0.1:1234": 1}
    assert config._parse_host_limits("") == {}
    with pytest.raises(SystemExit):
        config._parse_host_limits("api.example.com=two")
    monkeypatch.setattr(config, "HOST_LIMITS", {"127.0.0.1:1234": 1})
    monkeypatch.setattr(config, "MAX_CONCURRENT_PER_HOST", 2)
    assert config.host_limit("127.0.0.1:1234") == 1 and config.host_limit("api.example.com") == 2


def test_one_model_at_a_time_batches_and_switches_without_starving():
    import asyncio

    from data_pipeline.endpoints import HostLimiter

    async def scenario():
        limiter = HostLimiter(2, exclusive_model=True)
        together: list[set[str]] = []
        running: set[str] = set()

        async def request(model, delay=0.0):
            await asyncio.sleep(delay)
            async with limiter.slot(model):
                running.add(model)
                together.append(set(running))
                await asyncio.sleep(0.05)
                running.discard(model)

        await asyncio.gather(
            request("teacher"), request("teacher"), request("teacher", 0.01),
            request("judge", 0.02), request("judge", 0.02),
        )
        return together, limiter

    together, limiter = asyncio.run(scenario())
    assert all(len(models) == 1 for models in together)          # the two models never generate at the same time
    assert limiter.in_flight == 0 and limiter.switches == 2      # teacher batch, judge batch, teacher again: a swap per batch, not per call
    assert together[0] == together[1] == {"teacher"} and together[2] == together[3] == {"judge"}   # the newcomer took over instead of starving


def test_separate_backends_let_two_models_run_side_by_side():
    import asyncio

    from data_pipeline.endpoints import host_limiter, reset_host_limiters

    async def scenario():
        reset_host_limiters()
        peak = 0
        running = 0

        async def request(model):
            nonlocal peak, running
            limiter = host_limiter(f"api.example.com#{model}", 2, 0.0)   # the key the client builds in "separate" mode
            async with limiter.slot(model):
                running += 1
                peak = max(peak, running)
                await asyncio.sleep(0.05)
                running -= 1

        await asyncio.gather(*(request("teacher") for _ in range(2)), *(request("judge") for _ in range(2)))
        return peak

    assert asyncio.run(scenario()) == 4     # two per model, both models at once


def test_host_model_modes_from_env():
    from data_pipeline import config

    assert config._parse_host_modes("a.example=separate; b.example=shared") == {"a.example": "separate", "b.example": "shared"}
    assert config._parse_host_modes("") == {}
    with pytest.raises(SystemExit):
        config._parse_host_modes("a.example=sometimes")
    assert config.host_model_mode("unknown.example") == "mixed"


def test_a_model_may_have_its_own_cap(monkeypatch):
    from data_pipeline import config

    parsed = config._parse_host_limits("api.example.com=2;api.example.com/Ternary-27B=4;127.0.0.1:1234=1")
    assert parsed == {"api.example.com": 2, "api.example.com/Ternary-27B": 4, "127.0.0.1:1234": 1}
    monkeypatch.setattr(config, "HOST_LIMITS", parsed)
    monkeypatch.setattr(config, "MAX_CONCURRENT_PER_HOST", 2)
    assert config.host_limit("api.example.com", "Ternary-27B") == 4      # the model's own cap
    assert config.host_limit("api.example.com", "Qwen/Qwen3-30B") == 2   # falls back to the host's
    assert config.host_limit("api.example.com") == 2 and config.host_limit("other.example", "any") == 2
    with pytest.raises(SystemExit):
        config._parse_host_limits("api.example.com/model=lots")
