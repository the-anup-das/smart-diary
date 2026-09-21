import json

from conftest import good_analysis, good_verdict, profile

from data_pipeline.contracts import PROMPT_VERSION, FeedbackReportSchema, build_analysis_system_prompt
from data_pipeline.run import format_record
from data_pipeline.scripts import build_splits


def _record(text: str, edge=None, persona=None, distress=False, analysis=None):
    analysis = analysis or good_analysis()
    analysis["distressFlag"] = distress
    return format_record(text, analysis, profile(edge=edge, persona=persona), models={"writer": "w", "reviewer": "r", "teacher": "t", "judge": "j", "judge_host": "h"}, judge_verdict=good_verdict())


def test_record_carries_meta_and_converts_to_sharegpt_with_the_production_prompt():
    record = _record("A long day at the clinic.", edge="rumination_high", persona="be blunt")
    meta = record["meta"]
    assert meta["edge_case"] == "rumination_high" and meta["custom_persona"] == "be blunt" and meta["prompt_version"] == PROMPT_VERSION
    assert meta["teacher_model"] == "t" and meta["judge_scores"]["overall"] == 9 and len(meta["entry_sha256"]) == 64
    convo = build_splits.to_sharegpt(record)["conversations"]
    assert [c["from"] for c in convo] == ["system", "human", "gpt"]
    assert convo[0]["value"] == build_analysis_system_prompt("be blunt")
    assert convo[1]["value"] == "A long day at the clinic."
    gpt = json.loads(convo[2]["value"])
    assert "thought_reasoning" not in gpt and FeedbackReportSchema.model_validate(gpt)
    assert ": " not in convo[2]["value"]  # compact JSON


def test_build_is_deterministic_dedups_and_stratifies(tmp_path):
    raw = tmp_path / "dataset_raw.jsonl"
    rows = []
    base = "Today I sat through three meetings and then argued with my sister about the house sale, which left me wrung out and awake at one in the morning replaying every word she said to me."
    for i in range(12):
        rows.append(_record(f"{base} Version {i}.", edge="rumination_high"))         # near-duplicates of each other
    rows.append(_record(base, edge="rumination_high"))                                  # exact duplicate of the family
    for i in range(8):
        rows.append(_record(f"Plain day number {i}: coffee, a walk in the park, an early night and a call with my mum.", edge=None))
    for i in range(6):
        rows.append(_record(f"Crisis entry {i}: I do not see the point of any of it any more and I want it all to stop.", edge="acute_crisis_signals", distress=True))
    bad = _record("Broken analysis row that must be dropped.")
    bad["analysis"].pop("moodScore")
    rows.append(bad)
    with open(raw, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    out1, out2 = tmp_path / "a", tmp_path / "b"
    m1 = build_splits.build(raw, out1, test_ratio=0.2, seed=3407)
    m2 = build_splits.build(raw, out2, test_ratio=0.2, seed=3407)
    assert m1["train"]["sha256"] == m2["train"]["sha256"] and m1["test"]["sha256"] == m2["test"]["sha256"]
    assert m1["dedup"]["invalid"] == 1 and m1["dedup"]["exact"] == 0 and m1["dedup"]["near"] == 12  # one of the family survives
    assert m1["kept"] == 1 + 8 + 6
    strata = m1["strata"]
    assert set(strata) == {"rumination_high|ok", "none|ok", "acute_crisis_signals|distress"}
    assert strata["none|ok"] == {"train": 6, "test": 2} and strata["acute_crisis_signals|distress"] == {"train": 5, "test": 1}
    m3 = build_splits.build(raw, tmp_path / "c", test_ratio=0.2, seed=1)
    assert m3["train"]["sha256"] != m1["train"]["sha256"]
    lines = (out1 / "training_dataset.jsonl").read_text(encoding="utf-8").splitlines()
    assert all(json.loads(line)["conversations"][0]["from"] == "system" for line in lines)


def test_splits_can_keep_one_teachers_labels(tmp_path):
    import json

    import pytest

    from data_pipeline.scripts.build_splits import build
    from conftest import good_analysis

    raw = tmp_path / "raw.jsonl"
    with open(raw, "w", encoding="utf-8") as f:
        for i in range(10):
            teacher = "teacher-a" if i % 2 == 0 else "teacher-b"
            entry = f"Sample {i}: " + " ".join(f"word{i}{j}" for j in range(40))
            f.write(json.dumps({"id": f"r{i}", "entry": entry, "analysis": good_analysis(),
                                "meta": {"teacher_model": teacher, "edge_case": None, "custom_persona": None}}) + "\n")

    both = build(raw, tmp_path, test_ratio=0.2, seed=1)
    assert both["kept"] == 10 and both["teacher_filter"] is None and both["teachers_in_file"] == ["teacher-a", "teacher-b"]

    one = build(raw, tmp_path, test_ratio=0.2, seed=1, teacher="teacher-a")
    assert one["kept"] == 5 and one["teacher_filter"] == "teacher-a"
    assert one["teacher_models"] == ["teacher-a"]                    # the manifest records what the student was trained on
    assert one["train"]["rows"] + one["test"]["rows"] == 5
    with pytest.raises(SystemExit, match="teacher-a, teacher-b"):
        build(raw, tmp_path, test_ratio=0.2, seed=1, teacher="teacher-c")
