import asyncio
import json
from types import SimpleNamespace

from conftest import good_analysis, good_verdict

from data_pipeline import config
from data_pipeline.endpoints import Endpoint
from data_pipeline.run import PipelineManager, telemetry_row


class FakeGraph:
    def __init__(self, updates: dict | None = None, error: Exception | None = None):
        self.updates = updates or {}
        self.error = error

    async def astream(self, state, cfg=None):
        if self.error:
            raise self.error
        yield {"writer": {"entry": "It was a long day and I could not switch off.", "writer_model": "w"}}
        yield {"judge": self.updates}


def _runtime():
    ep = Endpoint(base_url="http://t/v1", api_key="k", model="teacher", name="analyzer")
    return SimpleNamespace(analyzer=ep, writers=[ep], judge_pool=SimpleNamespace(endpoints=[ep]), judge2=None, lessons=SimpleNamespace(enabled=True, counts=lambda: {}))


def _manager(tmp_path, monkeypatch, graph, target=1):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "TELEMETRY_LOG_PATH", tmp_path / "logs" / "telemetry.jsonl")
    monkeypatch.setattr(config, "REJECTIONS_LOG_PATH", tmp_path / "logs" / "rejections.log")
    return PipelineManager(target, _runtime(), graph, seed=3407, raw_path=tmp_path / "output" / "dataset_raw.jsonl")


def test_passed_sample_is_written_even_when_the_target_is_already_reached(tmp_path, monkeypatch):
    graph = FakeGraph({"analysis_json": good_analysis(), "judge_verdict": good_verdict(), "judge_model": "j", "judge_host": "h", "final_status": "PASSED", "total_tokens": 120, "calls": 4})
    manager = _manager(tmp_path, monkeypatch, graph, target=1)
    manager.total_approved = 1  # the target was reached by another worker while this one was in flight
    record = asyncio.run(manager.run_single_pipeline())
    assert record is not None and manager.total_approved == 2 and manager.session_approved == 1
    lines = (tmp_path / "output" / "dataset_raw.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["analysis"]["moodScore"] == 6 and row["meta"]["teacher_model"] == "teacher" and row["meta"]["judge_host"] == "h"
    telemetry = json.loads((tmp_path / "logs" / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert telemetry["status"] == "PASSED" and telemetry["tokens"] == 120 and telemetry["discard_reason"] is None


def test_failed_sample_is_logged_not_written(tmp_path, monkeypatch):
    graph = FakeGraph({"analysis_json": good_analysis(), "judge_verdict": good_verdict(overall=2, label_notes="mood contradicts the entry"), "final_status": "FAILED_JUDGE", "discard_reason": "mood contradicts the entry"})
    manager = _manager(tmp_path, monkeypatch, graph)
    assert asyncio.run(manager.run_single_pipeline()) is None
    assert not (tmp_path / "output" / "dataset_raw.jsonl").exists()
    assert "mood contradicts" in (tmp_path / "logs" / "rejections.log").read_text(encoding="utf-8")
    assert manager.status_counts == {"FAILED_JUDGE": 1} and manager.discard_count == 1


def test_crash_rows_carry_every_telemetry_key(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch, FakeGraph(error=RuntimeError("boom")))
    assert asyncio.run(manager.run_single_pipeline()) is None
    row = json.loads((tmp_path / "logs" / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == "CRASH" and row["error"].startswith("RuntimeError: boom")
    assert set(row) == set(telemetry_row({}, "PASSED", None))
    assert manager.crash_count == 1


def test_profiles_differ_per_attempt_but_repeat_for_the_same_seed_and_offset(tmp_path, monkeypatch):
    a = _manager(tmp_path, monkeypatch, FakeGraph())
    b = _manager(tmp_path, monkeypatch, FakeGraph())
    assert a._profile_for(1) == b._profile_for(1) and a._profile_for(1) != a._profile_for(2)
    b.start_offset = 100
    assert a._profile_for(1) != b._profile_for(1)


def test_a_missing_model_stops_the_run_after_one_crash(tmp_path, monkeypatch):
    from data_pipeline.agents.llm_client import LLMCallError
    from data_pipeline.run import fatal_reason

    ep = Endpoint(base_url="https://api.example.com/v1", api_key="k", model="Qwen/Qwen3-30B", name="writer")
    gone = LLMCallError("404 from Qwen/Qwen3-30B@api.example.com: model 'qwen3-30b' not found", retryable=False, endpoint=ep, status=404)
    assert "does not serve this model" in fatal_reason(gone)
    assert fatal_reason(LLMCallError("502 from x", retryable=True, endpoint=ep, status=502)) is None
    assert fatal_reason(LLMCallError("400 from x: context too long", retryable=False, endpoint=ep, status=400)) is None
    assert fatal_reason(RuntimeError("boom")) is None

    manager = _manager(tmp_path, monkeypatch, FakeGraph(error=gone), target=5)
    assert asyncio.run(manager.run_single_pipeline()) is None
    assert manager.aborted and "api.example.com" in manager.aborted and manager.crash_count == 1


def test_preflight_reports_every_role_and_fails_on_a_required_model(tmp_path, monkeypatch):
    import random

    from rich.console import Console

    from data_pipeline import run as run_module
    from data_pipeline.agents.llm_client import LLMCallError
    from data_pipeline.endpoints import EndpointPool
    from data_pipeline.graph import PipelineRuntime
    from data_pipeline.lessons import LessonsStore
    from data_pipeline.reputation import JudgeReputation

    def ep(model, host):
        return Endpoint(base_url=f"https://{host}/v1", api_key="k", model=model, name=model)

    runtime = PipelineRuntime(
        analyzer=ep("teacher", "endpoint"), editor=ep("teacher", "endpoint"), reviewer=ep("gpt-oss", "lmstudio"), writers=[ep("teacher", "endpoint")],
        judge_pool=EndpointPool([ep("bonsai", "endpoint"), ep("gemini", "google")]), lessons=LessonsStore(tmp_path / "l.json"),
        reputation=JudgeReputation(tmp_path / "r.json"), judge2=ep("oss-120b", "cerebras"), rng=random.Random(0),
    )
    answers = {"teacher": None, "gpt-oss": None, "bonsai": "404 model not found", "gemini": None, "oss-120b": "429 quota"}

    async def fake_call(endpoint, messages, **kw):
        error = answers[endpoint.model]
        if error:
            raise LLMCallError(error, retryable=False, endpoint=endpoint, status=404)
        return "ok", {"tokens": 1}

    monkeypatch.setattr(run_module, "acall_llm", fake_call)
    console = Console(width=140, force_terminal=False)
    with console.capture() as cap:
        healthy = asyncio.run(run_module.preflight(runtime, console))
    text = cap.get()
    assert healthy                                                   # one judge answers, so the run may start
    assert text.count("ok") >= 3 and "unavailable" in text and "404 model not found" in text and "429 quota" in text
    assert text.count("teacher@endpoint") == 1                       # the same model on the same host is probed once

    answers["teacher"] = "404 model 'qwen3-30b' not found"
    with console.capture() as cap:
        healthy = asyncio.run(run_module.preflight(runtime, console))
    assert not healthy and "FAIL" in cap.get()

    answers["teacher"] = None
    answers["gemini"] = "503"
    with console.capture() as cap:
        healthy = asyncio.run(run_module.preflight(runtime, console))
    assert not healthy and "no judge host answered" in cap.get()


def test_preflight_sidelines_failing_judges_and_falls_back_from_a_dead_second_judge(tmp_path, monkeypatch):
    import random

    from rich.console import Console

    from data_pipeline import run as run_module
    from data_pipeline.agents.llm_client import LLMCallError
    from data_pipeline.endpoints import EndpointPool
    from data_pipeline.graph import PipelineRuntime
    from data_pipeline.lessons import LessonsStore
    from data_pipeline.reputation import JudgeReputation

    def ep(model, host, key="k"):
        return Endpoint(base_url=f"https://{host}/v1", api_key=key, model=model, name=model)

    bonsai, gemini_a, gemini_b = ep("bonsai", "endpoint"), ep("gemini", "google", "key-a"), ep("gemini", "google", "key-b")
    cerebras = ep("oss-120b", "cerebras")
    runtime = PipelineRuntime(
        analyzer=ep("teacher", "endpoint"), editor=ep("teacher", "endpoint"), reviewer=ep("gpt-oss", "lmstudio"), writers=[ep("teacher", "endpoint")],
        judge_pool=EndpointPool([bonsai, gemini_a, gemini_b], cooldown_s=0.05), lessons=LessonsStore(tmp_path / "l.json"),
        reputation=JudgeReputation(tmp_path / "r.json"), judge2=cerebras, judge2_pool=EndpointPool([cerebras]), rng=random.Random(0),
    )
    probed = []

    async def fake_call(endpoint, messages, **kw):
        probed.append((endpoint.model, endpoint.api_key))
        if endpoint is bonsai:
            raise LLMCallError("502 bad gateway", retryable=True, endpoint=endpoint, status=502)
        if endpoint is cerebras:
            raise LLMCallError("402 payment required", retryable=False, endpoint=endpoint, status=402)
        return "ok", {"tokens": 1}

    monkeypatch.setattr(run_module, "acall_llm", fake_call)
    console = Console(width=140, force_terminal=False)
    with console.capture() as cap:
        healthy = asyncio.run(run_module.preflight(runtime, console))
    text = cap.get()
    assert healthy
    assert ("gemini", "key-a") in probed and ("gemini", "key-b") in probed          # both Google keys are checked
    assert runtime.judge_pool.pick() is gemini_a                                     # Bonsai sits out one cooldown after a 502
    assert runtime.judge2 is None and runtime.judge2_pool is None and "fallback" in text   # a 402 second judge gives way to the pool
    assert runtime.second_judge(gemini_a.label) is gemini_b
    assert "wants payment" in run_module.fatal_reason(LLMCallError("402", retryable=False, endpoint=cerebras, status=402))
