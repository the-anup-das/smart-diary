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
