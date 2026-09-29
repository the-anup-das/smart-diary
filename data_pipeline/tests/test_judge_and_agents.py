import asyncio

from conftest import good_analysis, good_verdict, profile

from data_pipeline import config
from data_pipeline.agents import analyzer, judge, reviewer, writer
from data_pipeline.agents.llm_client import StructuredResult
from data_pipeline.contracts import build_analysis_system_prompt


def _structured(parsed=None, data=None, error=None):
    async def fake(ep, messages, schema, **kw):
        fake.messages = messages
        fake.schema = schema
        instance = schema.model_validate(parsed) if parsed is not None else None
        return StructuredResult(data if data is not None else parsed, instance, error, "", {"tokens": 1, "cost": 0.0, "model": ep.model, "host": ep.host}, "json_schema", messages)
    return fake


def test_judge_passes_needs_overall_and_safety_and_no_hard_fail():
    assert judge.judge_passes(good_verdict())
    assert not judge.judge_passes(good_verdict(overall=config.JUDGE_THRESHOLD - 1))
    assert not judge.judge_passes(good_verdict(safety=config.JUDGE_SAFETY_MIN - 1))
    assert not judge.judge_passes(good_verdict(hard_fail=True, hard_fail_reason="flag wrong"))
    assert judge.judge_reason(good_verdict(hard_fail=True, hard_fail_reason="flag wrong")) == "flag wrong"
    assert judge.judge_reason(good_verdict(overall=3, label_notes="topics off")) == "topics off"
    assert "safety score 2" in judge.judge_reason(good_verdict(safety=2))


def test_judge_fails_closed_on_unparseable_output(monkeypatch, endpoint):
    monkeypatch.setattr(judge, "acall_structured", _structured(parsed=None, error="no JSON object"))
    verdict, usage = asyncio.run(judge.judge_candidate("entry", good_analysis(), None, endpoint=endpoint))
    assert verdict["hard_fail"] and verdict["unparseable"] and not judge.judge_passes(verdict)


def test_judge_prompt_carries_entry_analysis_and_persona(monkeypatch, endpoint):
    fake = _structured(parsed=good_verdict())
    monkeypatch.setattr(judge, "acall_structured", fake)
    verdict, _ = asyncio.run(judge.judge_candidate("I scrolled until 2am.", good_analysis(), "be blunt", endpoint=endpoint))
    assert judge.judge_passes(verdict)
    user = fake.messages[1]["content"]
    assert "I scrolled until 2am." in user and '"moodScore"' in user and "USER'S CUSTOM INSTRUCTIONS: be blunt" in user
    assert fake.schema is judge.JudgeVerdict and "distressFlag" in fake.messages[0]["content"]


def test_analyzer_uses_the_production_prompt_and_adds_correction_turn(monkeypatch, endpoint):
    fake = _structured(parsed=good_analysis())
    monkeypatch.setattr(analyzer, "acall_structured", fake)
    data, error, usage = asyncio.run(analyzer.analyze_journal_entry("Long day.", "be blunt", endpoint=endpoint, previous_json={"moodScore": 3}, previous_error="topics sum to 0.8", lessons=["never invent minutes"]))
    assert error is None and data["moodScore"] == 6
    system, user, prev, correction = fake.messages
    assert system["content"].startswith(build_analysis_system_prompt("be blunt")) and "never invent minutes" in system["content"]
    assert user == {"role": "user", "content": "Long day."}
    assert prev["role"] == "assistant" and '"moodScore": 3' in prev["content"]
    assert "topics sum to 0.8" in correction["content"]
    # without lessons or a previous attempt the messages are exactly production's
    plain = _structured(parsed=good_analysis())
    monkeypatch.setattr(analyzer, "acall_structured", plain)
    asyncio.run(analyzer.analyze_journal_entry("Long day.", None, endpoint=endpoint))
    assert plain.messages == [{"role": "system", "content": build_analysis_system_prompt()}, {"role": "user", "content": "Long day."}]


def test_reviewer_fails_closed(monkeypatch, endpoint):
    monkeypatch.setattr(reviewer, "acall_structured", _structured(parsed=None, error="garbage"))
    review, _ = asyncio.run(reviewer.review_journal_entry("entry", profile(), endpoint=endpoint))
    assert review["approved"] is False and "unreadable" in review["critique"]
    monkeypatch.setattr(reviewer, "acall_structured", _structured(parsed={"approved": True, "critique": "fine"}))
    review, _ = asyncio.run(reviewer.review_journal_entry("entry", profile(), endpoint=endpoint))
    assert review == {"approved": True, "critique": "fine"}


def test_writer_prompt_never_sees_the_persona_but_sees_lessons_and_edge_case():
    messages = writer.build_writer_messages(profile(edge="rumination_high", persona="be blunt"), lessons=["too tidy an ending"])
    user = messages[1]["content"]
    assert "rumination_high" in user and "too tidy an ending" in user and "be blunt" not in user
    assert "between 40 and 80 words" in user


def test_judge_prompt_says_zero_means_not_mentioned():
    """The rule that caused 729 of 756 judge rejections: every field is required, so a zero is never 'invented'."""
    from data_pipeline.agents.judge import JUDGE_SYSTEM_PROMPT

    assert "never a fault" in JUDGE_SYSTEM_PROMPT and "Only a positive claim can be invented" in JUDGE_SYSTEM_PROMPT
    assert "a stimulation or cognition value is not stated in the entry" not in JUDGE_SYSTEM_PROMPT
    assert "is not left out" in JUDGE_SYSTEM_PROMPT            # the other direction: a described habit labelled 0 is a label fault


def test_judge_and_writer_prompts_carry_the_label_fixes():
    from data_pipeline.agents.judge import JUDGE_SYSTEM_PROMPT
    from data_pipeline.agents.writer import WRITER_SYSTEM_PROMPT

    assert "wanting to disappear" in JUDGE_SYSTEM_PROMPT and "most harmful mistake" in JUDGE_SYSTEM_PROMPT
    assert "grammarScore reflects the text as written" in JUDGE_SYSTEM_PROMPT
    assert "stays ordinary" in WRITER_SYSTEM_PROMPT and "a clock time" in WRITER_SYSTEM_PROMPT


def test_the_judges_own_reading_catches_contradictions_it_would_otherwise_pass():
    """Calibration: both judges passed every mood of 9 on a despairing entry and every flipped rumination level."""
    from conftest import good_analysis, good_verdict

    from data_pipeline.agents.judge import apply_cross_check, cross_check, judge_passes

    analysis = good_analysis()                                   # mood 6, rumination low, distress false
    assert cross_check(good_verdict(), analysis) == []           # the judge reads the entry the same way
    assert judge_passes(apply_cross_check(good_verdict(), analysis))

    mood9 = dict(analysis, moodScore=9)
    assert cross_check(good_verdict(own_mood=6), mood9) == ["moodScore 9 contradicts the entry, which reads as about 6"]
    assert cross_check(good_verdict(own_mood=7), mood9) == []    # two points apart is a matter of opinion

    looping = good_verdict(own_rumination="high")
    assert cross_check(looping, analysis)[0].startswith("ruminationLevel 'low' contradicts")
    assert cross_check(good_verdict(own_rumination="moderate"), analysis) == []   # neighbours are not a contradiction

    crisis = good_verdict(own_distress=True)
    failed = apply_cross_check(crisis, analysis)
    assert failed["hard_fail"] and not judge_passes(failed) and "passive wish to die" in failed["hard_fail_reason"]
    assert failed["label_notes"].startswith("distressFlag is false")   # the analyzer gets told what to repair
    assert cross_check(good_verdict(own_distress=False), dict(analysis, distressFlag=True)) == ["distressFlag is true but the entry shows no crisis signal"]


def test_calibration_reports_the_pipeline_as_a_whole(monkeypatch):
    import asyncio

    from conftest import good_analysis, good_verdict

    from data_pipeline.endpoints import Endpoint
    from data_pipeline.eval import judge_calibration as cal

    rows = [{"entry": "A long day at work, then a quiet evening.", "persona": None, "analysis": good_analysis()}]
    strict = Endpoint(base_url="http://a/v1", api_key="k", model="strict", name="judge")
    lenient = Endpoint(base_url="http://b/v1", api_key="k", model="lenient", name="judge")

    async def fake_judge(entry, analysis, persona, *, endpoint, lessons=None):
        caught = endpoint.model == "strict" and analysis.get("distressFlag") is True     # only the strict judge notices the flip
        return (good_verdict(hard_fail=True, hard_fail_reason="flag") if caught else good_verdict()), {}

    monkeypatch.setattr(cal, "judge_candidate", fake_judge)
    results = asyncio.run(cal.calibrate(rows, [strict, lenient], concurrency=2))
    pipe = results["pipeline: validator + all judges"]
    assert pipe["correct"] == {"passed": 1, "failed": 0, "errors": 0}
    assert pipe["flipped_distress"]["failed"] == 1                  # one judge caught it, so the pipeline did
    assert pipe["topic_weights_half"]["failed"] == 1 and pipe["two_micro_actions"]["failed"] == 1   # the validator's, not the judges'
    assert results[lenient.label]["topic_weights_half"]["passed"] == 1                              # a judge alone missed it
