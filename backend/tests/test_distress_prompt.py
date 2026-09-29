"""The analysis prompt must name the passive signals of a wish to die, not only the strict half of the rule."""
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from routers import analyze  # noqa: E402


def _prompt_source() -> str:
    with open(analyze.__file__, encoding="utf-8") as f:
        return f.read()


def test_distress_rule_names_the_passive_signals():
    source = _prompt_source()
    for signal in ("wanting to disappear", "not wanting to wake up", "better off without you", "not seeing how to keep going"):
        assert signal in source
    assert "this job is killing me" in source and "When unsure" in source
    assert "ONLY for clear self-harm" not in source


def test_schema_description_matches_the_rule():
    description = analyze.FeedbackReportSchema.model_fields["distressFlag"].description
    assert "wanting to disappear" in description and "figurative venting are False" in description
