"""The analysis prompt must define rumination and decisions itself: a grateful look back is not looping, and a plan is not a decision."""
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from routers import analyze  # noqa: E402


def _prompt_source() -> str:
    with open(analyze.__file__, encoding="utf-8") as f:
        return f.read()


def test_rumination_rule_is_in_the_prompt():
    source = _prompt_source()
    assert "8. Rumination: rate ruminationLevel from how the entry itself thinks" in source
    for phrase in ("over and over", "looks back on a hard time that has eased", "naming a past struggle is not rumination"):
        assert phrase in source


def test_decision_rule_is_in_the_prompt():
    source = _prompt_source()
    assert "9. Decisions: set detectedDecision only when the writer is weighing a choice that is still open" in source
    assert "decisions already made are not decisions" in source
    assert "reports a choice as made" in source and "though it contains the word decision" in source


def test_schema_descriptions_match_the_rules():
    fields = analyze.EnergyAnalysisSchema.model_fields
    assert "not its topic" in fields["ruminationLevel"].description
    assert "name what is helping" in fields["ruminationCoaching"].description
    decision = analyze.FeedbackReportSchema.model_fields["detectedDecision"].description
    assert "still weighing" in decision and "decisions already made are null" in decision
