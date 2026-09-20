"""End-to-end runs of the LangGraph workflow with the agents faked: the review loop, the schema
retry with error feedback, the judge's repair-before-discard, and the second opinion."""
import asyncio
import json
import random

from conftest import good_analysis, good_verdict, profile

from data_pipeline import config, graph as graph_module
from data_pipeline.agents.llm_client import LLMCallError
from data_pipeline.endpoints import Endpoint, EndpointPool
from data_pipeline.graph import PipelineRuntime, build_pipeline_graph
from data_pipeline.lessons import LessonsStore
from data_pipeline.run import initial_state

USAGE = {"tokens": 10, "cost": 0.0, "model": "m", "host": "h"}


def _ep(model="m", host="a"):
    return Endpoint(base_url=f"http://{host}/v1", api_key="k", model=model, name=model)


def _runtime(tmp_path, judges=None, judge2=None):
    judges = judges or [_ep("judge", "judge-a"), _ep("judge", "judge-b")]
    return PipelineRuntime(
        analyzer=_ep("teacher"), editor=_ep("editor"), reviewer=_ep("reviewer"), writers=[_ep("writer")],
        judge_pool=EndpointPool(judges, cooldown_s=0.01), lessons=LessonsStore(tmp_path / "lessons.json"),
        judge2=judge2, judge2_pool=EndpointPool([judge2]) if judge2 else None, judge2_enabled=judge2 is not None,
        rng=random.Random(0), disagreements_path=tmp_path / "disagreements.jsonl",
    )


def _fakes(monkeypatch, *, reviews, analyses, verdicts):
    """Each argument is a list consumed in order; the last element repeats."""
    calls = {"review": [], "analyze": [], "judge": []}

    def take(items, log, key):
        log[key].append(None)
        idx = min(len(log[key]) - 1, len(items) - 1)
        return items[idx]

    async def fake_write(profile_, *, endpoint, lessons=None):
        return "I replayed the argument all night and could not sleep.", USAGE

    async def fake_edit(entry, critique, profile_, *, endpoint):
        return entry + " Revised.", USAGE

    async def fake_review(entry, profile_, *, endpoint):
        return take(reviews, calls, "review"), USAGE

    async def fake_analyze(entry, persona=None, *, endpoint, previous_json=None, previous_error=None, lessons=None):
        calls.setdefault("analyze_args", []).append({"previous_error": previous_error, "previous_json": previous_json, "lessons": list(lessons or [])})
        data = take(analyses, calls, "analyze")
        return json.loads(json.dumps(data)), None, USAGE

    async def fake_judge(entry, analysis_json, persona, *, endpoint):
        calls.setdefault("judge_endpoints", []).append(endpoint.host)
        item = take(verdicts, calls, "judge")
        if isinstance(item, Exception):
            raise item
        return dict(item), USAGE

    monkeypatch.setattr(graph_module, "generate_journal_entry", fake_write)
    monkeypatch.setattr(graph_module, "edit_journal_entry", fake_edit)
    monkeypatch.setattr(graph_module, "review_journal_entry", fake_review)
    monkeypatch.setattr(graph_module, "analyze_journal_entry", fake_analyze)
    monkeypatch.setattr(graph_module, "judge_candidate", fake_judge)
    return calls


def _run(runtime, prof=None):
    compiled = build_pipeline_graph(runtime)
    return asyncio.run(compiled.ainvoke(initial_state(prof or profile(), 0), {"recursion_limit": 80}))


def test_clean_pass(tmp_path, monkeypatch):
    calls = _fakes(monkeypatch, reviews=[{"approved": True, "critique": "good"}], analyses=[good_analysis()], verdicts=[good_verdict()])
    state = _run(_runtime(tmp_path))
    assert state["final_status"] == "PASSED" and state["judge_retry_count"] == 0 and state["judge_host"] == "judge-a"
    assert state["calls"] == 4 and state["total_tokens"] == 40  # writer, reviewer, analyzer, judge
    assert calls["analyze_args"][0]["previous_error"] is None


def test_editor_loop_then_failed_review_records_a_lesson(tmp_path, monkeypatch):
    _fakes(monkeypatch, reviews=[{"approved": False, "critique": "Ends with a tidy moral, unlike a real diary."}], analyses=[good_analysis()], verdicts=[good_verdict()])
    runtime = _runtime(tmp_path)
    state = _run(runtime)
    assert state["final_status"] == "FAILED_REVIEW" and state["editor_iteration"] == config.MAX_EDITOR_ITERATIONS
    assert "tidy moral" in state["discard_reason"] and runtime.lessons.top("entry") == ["Ends with a tidy moral, unlike a real diary."]


def test_schema_retry_feeds_the_error_back(tmp_path, monkeypatch):
    broken = good_analysis()
    broken["topics"] = [{"topic": "work", "weight": 0.4}]
    calls = _fakes(monkeypatch, reviews=[{"approved": True, "critique": ""}], analyses=[broken, good_analysis()], verdicts=[good_verdict()])
    state = _run(_runtime(tmp_path))
    assert state["final_status"] == "PASSED" and state["schema_retry_count"] == 1
    second = calls["analyze_args"][1]
    assert "sum to 0.40" in second["previous_error"] and second["previous_json"]["topics"] == [{"topic": "work", "weight": 0.4}]


def test_schema_failures_exhaust_into_failed_schema(tmp_path, monkeypatch):
    broken = good_analysis()
    broken["energyAnalysis"]["microActions"] = []
    _fakes(monkeypatch, reviews=[{"approved": True, "critique": ""}], analyses=[broken], verdicts=[good_verdict()])
    state = _run(_runtime(tmp_path))
    assert state["final_status"] == "FAILED_SCHEMA" and state["schema_retry_count"] == config.MAX_SCHEMA_RETRY and "microActions" in state["discard_reason"]


def test_judge_failure_triggers_one_repair_with_the_critique_then_passes(tmp_path, monkeypatch):
    first = good_verdict(overall=4, label_notes="ruminationLevel should be high: the writer replays the argument all night.")
    calls = _fakes(monkeypatch, reviews=[{"approved": True, "critique": ""}], analyses=[good_analysis()], verdicts=[first, good_verdict()])
    runtime = _runtime(tmp_path)
    state = _run(runtime)
    assert state["final_status"] == "PASSED" and state["judge_retry_count"] == 1
    repair = calls["analyze_args"][1]
    assert "quality judge rejected it" in repair["previous_error"] and "ruminationLevel should be high" in repair["previous_error"]
    assert repair["previous_json"]["moodScore"] == 6
    assert runtime.lessons.top("labels") == [first["label_notes"]]


def test_two_judge_failures_discard(tmp_path, monkeypatch):
    bad = good_verdict(hard_fail=True, hard_fail_reason="distressFlag set for figurative venting")
    _fakes(monkeypatch, reviews=[{"approved": True, "critique": ""}], analyses=[good_analysis()], verdicts=[bad])
    state = _run(_runtime(tmp_path))
    assert state["final_status"] == "FAILED_JUDGE" and state["judge_retry_count"] == 1 and "figurative venting" in state["discard_reason"]


def test_judge_pool_rotates_when_a_host_fails(tmp_path, monkeypatch):
    calls = _fakes(monkeypatch, reviews=[{"approved": True, "critique": ""}], analyses=[good_analysis()],
                   verdicts=[LLMCallError("429", retryable=True), good_verdict()])
    state = _run(_runtime(tmp_path))
    assert state["final_status"] == "PASSED" and calls["judge_endpoints"] == ["judge-a", "judge-b"] and state["judge_host"] == "judge-b"


def test_second_opinion_can_flip_a_pass_and_logs_the_disagreement(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "JUDGE2_SAMPLE_RATE", 1.0)
    _fakes(monkeypatch, reviews=[{"approved": True, "critique": ""}], analyses=[good_analysis()],
           verdicts=[good_verdict(), good_verdict(overall=3, label_notes="the reframe is dismissive")])
    runtime = _runtime(tmp_path, judge2=_ep("gpt-oss-120b", "cerebras"))
    state = _run(runtime)
    assert state["final_status"] == "FAILED_JUDGE2" and state["judge2_host"] == "cerebras" and "second opinion" in state["discard_reason"]
    rows = (tmp_path / "disagreements.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["first"]["passed"] is True and json.loads(rows[0])["second"]["passed"] is False
