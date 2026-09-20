"""Value-level metrics, the gate, the golden set's shape, and the evaluator against a fake endpoint."""
import asyncio
import json

from conftest import good_analysis

from data_pipeline.agents import llm_client
from data_pipeline.agents.llm_client import StructuredResult
from data_pipeline.eval import judge_calibration
from data_pipeline.eval.metrics import aggregate, expected_from_analysis, gate, load_thresholds, score_one
from data_pipeline.scripts import evaluate


def test_golden_set_is_well_formed_and_covers_the_groups():
    rows = evaluate.load_golden()
    assert len(rows) >= 40 and len({r["id"] for r in rows}) == len(rows)
    groups = {r["group"] for r in rows}
    for needed in ("crisis", "venting", "rumination_high", "rumination_low", "stimulation", "no_signals", "cognition", "decision", "plain", "messy_grammar", "persona"):
        assert needed in groups, needed
    assert sum(1 for r in rows if r["expected"].get("distressFlag")) >= 3
    assert all(25 <= len(r["entry"].split()) <= 400 for r in rows)


def test_score_one_rewards_a_matching_analysis_and_punishes_a_missing_one():
    expected = {"distressFlag": False, "moodScore": [5, 7], "ruminationLevel": ["low"], "topTopic": ["work"], "stimulationLoad": [0, 0], "brainRotLoad": [0, 0], "builders": ["exercise"], "detectedDecision": False}
    good = score_one(good_analysis(), expected, latency_s=1.2, tokens=300)
    assert good["schema_valid"] and good["rules_ok"] and good["distress_correct"] and good["mood_in_range"] and good["rumination_correct"]
    assert good["top_topic_correct"] and good["stim_load_error"] == 0 and good["rot_load_error"] == 0 and good["builders_recall"] == 1.0 and good["decision_correct"]
    missing = score_one(None, expected, error="timeout")
    assert not missing["schema_valid"] and missing["mood_error"] == 10.0 and missing["distress_correct"] is False and missing["builders_recall"] == 0.0
    off = good_analysis()
    off["moodScore"] = 9
    off["distressFlag"] = True
    scored = score_one(off, expected)
    assert scored["mood_error"] == 2 and scored["distress_correct"] is False and scored["distress_predicted"] is True


def test_aggregate_and_gate():
    expected = {"distressFlag": False, "moodScore": [5, 7], "ruminationLevel": ["low"], "topTopic": ["work"], "stimulationLoad": [0, 0], "brainRotLoad": [0, 0], "builders": ["exercise"], "detectedDecision": False}
    crisis = dict(expected, distressFlag=True)
    flagged = good_analysis()
    flagged["distressFlag"] = True
    rows = [score_one(good_analysis(), expected), score_one(flagged, crisis), score_one(good_analysis(), crisis), score_one(None, expected)]
    agg = aggregate(rows)
    assert agg["count"] == 4 and agg["schema_valid_rate"] == 0.75 and agg["distress_confusion"] == {"tp": 1, "fn": 1, "fp": 0, "tn": 1}
    assert agg["distress_recall"] == 0.5 and agg["distress_precision"] == 1.0 and agg["failures"] == 1
    passed, failures = gate(agg, load_thresholds())
    assert not passed and any(f.startswith("distress_recall") for f in failures) and any(f.startswith("schema_valid_rate") for f in failures)
    perfect = aggregate([score_one(good_analysis(), expected)] * 5)
    passed, failures = gate(perfect, load_thresholds())
    assert passed and all(f.endswith("no data") for f in failures)  # recall has no positives in this tiny set


def test_expected_from_teacher_analysis():
    exp = expected_from_analysis(good_analysis())
    assert exp["moodScore"] == [5, 7] and exp["ruminationLevel"] == ["low"] and exp["topTopic"] == ["work"] and exp["builders"] == ["exercise"]
    assert exp["distressFlag"] is False and exp["stimulationLoad"] == [0, 0] and exp["minutes"] == [0, 5]


def test_evaluator_runs_against_a_fake_endpoint(monkeypatch, tmp_path):
    rows = evaluate.load_golden()[:6]

    crisis_entries = {r["entry"] for r in evaluate.load_golden() if r["expected"].get("distressFlag")}

    async def fake_structured(ep, messages, schema, **kw):
        analysis = good_analysis()
        analysis["distressFlag"] = messages[1]["content"] in crisis_entries
        return StructuredResult(analysis, schema.model_validate(analysis), None, "", {"completion_tokens": 120, "tokens": 500}, "json_schema", messages)

    monkeypatch.setattr(evaluate, "acall_structured", fake_structured)
    monkeypatch.setattr(evaluate, "RESULTS_PATH", tmp_path / "eval_results.json")
    from data_pipeline.endpoints import Endpoint
    outputs = asyncio.run(evaluate.run_endpoint(rows, Endpoint(base_url="http://fake/v1", api_key="k", model="m"), concurrency=2))
    scored = evaluate.score(rows, outputs)
    agg = aggregate(scored)
    assert agg["count"] == 6 and agg["schema_valid_rate"] == 1.0 and agg["avg_tokens"] == 120
    assert agg["distress_recall"] == 1.0  # the crisis entries were flagged by the fake
    code = evaluate.main(["--backend", "endpoint", "--base-url", "http://fake/v1", "--model", "m", "--dataset", "golden", "--limit", "6", "--gate", "--label", "fake"])
    saved = json.loads((tmp_path / "eval_results.json").read_text(encoding="utf-8"))
    assert saved[0]["label"] == "fake" and saved[0]["metrics"]["count"] == 6 and saved[0]["gate"]["passed"] in (True, False)
    assert code in (0, 1)


def test_corruptions_are_each_detectable():
    analysis = good_analysis()
    bad = judge_calibration.corruptions(analysis, "entry")
    assert set(bad) == {"flipped_distress", "topic_weights_half", "invented_minutes", "wrong_rumination", "two_micro_actions", "contradictory_mood"}
    assert bad["flipped_distress"]["distressFlag"] is True and analysis["distressFlag"] is False
    assert sum(t["weight"] for t in bad["topic_weights_half"]["topics"]) == 0.5
    assert bad["invented_minutes"]["cognition"]["passiveConsumptionMinutes"] == 240
    assert bad["wrong_rumination"]["energyAnalysis"]["ruminationLevel"] == "high"
    assert len(bad["two_micro_actions"]["energyAnalysis"]["microActions"]) == 2
    assert bad["contradictory_mood"]["moodScore"] in (2, 9) and bad["contradictory_mood"]["moodScore"] != analysis["moodScore"]
