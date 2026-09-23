import asyncio
import json
import time
from types import SimpleNamespace

import openai
import pytest

from data_pipeline import config
from data_pipeline.agents import llm_client
from data_pipeline.endpoints import Endpoint
from data_pipeline.metrics import METRICS, MetricsRegistry, fmt_latency, fmt_tps


def _ep(model="m", host="a", name="writer"):
    return Endpoint(base_url=f"http://{host}/v1", api_key="k", model=model, name=name)


def test_registry_turns_timed_calls_into_tokens_per_second(tmp_path):
    reg = MetricsRegistry()
    reg.enable_log(tmp_path / "calls.jsonl")
    ep = _ep()
    started = reg.start(ep)
    assert reg.snapshot()[0]["inFlight"] == 1
    record = reg.finish(ep, started - 2.0, usage={"prompt_tokens": 100, "completion_tokens": 50})   # a two-second call
    assert record["ok"] and 24 <= record["tokens_per_s"] <= 26 and record["role"] == "writer" and record["latency_s"] >= 2.0
    reg.finish(_ep(name="judge1"), reg.start(_ep(name="judge1")) - 1.0, error="APITimeoutError: slow", timeout=True)
    reg.finish(_ep(), reg.start(_ep()) - 4.0, usage={"prompt_tokens": 100, "completion_tokens": 40})   # 10 tok/s
    snap = {s["label"]: s for s in reg.snapshot()}
    m = snap["m@a"]
    assert m["calls"] == 3 and m["errors"] == 1 and m["timeouts"] == 1 and m["inFlight"] == 0
    assert m["roles"] == ["judge1", "writer"] and m["completionTokens"] == 90
    assert 17 <= m["medianTps"] <= 18 and 9.5 <= m["lastTps"] <= 10.5          # median of 25 and 10; the failed call has no speed
    assert 2.9 <= m["medianLatency"] <= 3.1 and 2.9 <= m["avgLatency"] <= 3.1     # failures are not counted in latency
    lines = [json.loads(l) for l in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3 and lines[1]["ok"] is False and lines[1]["timeout"] is True and lines[1]["tokens_per_s"] is None
    reg.reset()
    assert reg.snapshot() == [] and reg.log_path is None
    assert fmt_tps(None) == "-" and fmt_tps(12.34) == "12.3 tok/s" and fmt_latency(0.5) == "0.5s" and fmt_latency(150) == "2.5m"


def test_the_client_records_every_call_including_failures(monkeypatch, endpoint):
    from test_llm_client import FakeClient, _http_error, _response

    llm_client.reset_caches()
    monkeypatch.setattr(config, "HOST_PACING_S", 0.0)

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(llm_client.asyncio, "sleep", no_sleep)
    fake = FakeClient([_response("ok", prompt=30, completion=12), _http_error(openai.BadRequestError, 400, "context length exceeded")])
    monkeypatch.setattr(llm_client, "get_client", lambda ep: fake)
    asyncio.run(llm_client.acall_llm(endpoint, [{"role": "user", "content": "hi"}]))
    with pytest.raises(llm_client.LLMCallError):
        asyncio.run(llm_client.acall_llm(endpoint, [{"role": "user", "content": "hi"}]))
    snap = METRICS.snapshot()
    assert len(snap) == 1 and snap[0]["label"] == "test-model@test.local" and snap[0]["calls"] == 2 and snap[0]["errors"] == 1
    assert snap[0]["completionTokens"] == 12 and snap[0]["inFlight"] == 0 and snap[0]["roles"] == ["test"]
    assert snap[0]["lastLatency"] is not None                                   # a fake call takes no measurable time, so no tok/s, but it was timed


def test_board_shows_speeds_on_request_and_the_m_key_toggles_them(tmp_path, monkeypatch):
    from rich.console import Console

    from data_pipeline.run import PipelineManager, RunBoard, speed_table

    monkeypatch.setattr(config, "TELEMETRY_LOG_PATH", tmp_path / "t.jsonl")
    ep = _ep("teacher", "endpoint", "analyzer")
    manager = PipelineManager(10, SimpleNamespace(analyzer=ep), None, seed=1, dry_run=True)
    console = Console(width=160, height=30, force_terminal=False)
    board = RunBoard(manager, to_add=10, existing=0, console=console, show_speeds=True)
    board.plain = False
    METRICS.reset()
    with console.capture() as cap:
        console.print(board.speeds())
    assert "no calls yet" in cap.get()
    METRICS.finish(ep, METRICS.start(ep) - 1.0, usage={"prompt_tokens": 10, "completion_tokens": 30})
    rows_with = board.visible_rows()
    with console.capture() as cap:
        console.print(board.speeds())
    text = cap.get()
    assert "teacher@endpoint" in text and "analyzer" in text and "tok/s" in text
    board.handle_key("models")
    assert not board.show_speeds and board.visible_rows() > rows_with              # the table gives its rows back
    with console.capture() as cap:
        console.print(board.speeds())
    assert cap.get().strip() == ""
    with console.capture() as cap:
        console.print(speed_table("Model speed this session"))
    assert "Model speed this session" in cap.get()
    METRICS.reset()
