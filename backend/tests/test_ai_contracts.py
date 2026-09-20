"""The analysis contract: one prompt, one schema, shared by production, the pipeline and the evaluator."""
import json
import os
import sys

from ai_contracts import analysis as c

# Pinned on purpose. If this fails you changed the prompt or the schema: bump PROMPT_VERSION,
# update the hash here, and expect the analysis cache to refill.
PINNED_PROMPT_SHA256 = "84d87c2775f05ee944ea51efc453b6fbe2c8b95fad0ee18cea2d7a1beb986cf1"


def _good_report() -> c.FeedbackReportSchema:
    return c.FeedbackReportSchema(
        moodScore=6, sentiment="Tired", grammarScore=8, grammarFixes=[], openLoops=["finish the report"],
        cognitiveReframes=[], topics=[c.TopicWeight(topic="work", weight=0.7), c.TopicWeight(topic="health", weight=0.3)],
        selfFocusScore=6, selfFocusFeedback="Mostly about your own day.", repetitiveWords=["really"],
        repetitiveWordingFeedback="Vary the intensifiers.", detectedDecision=None, emotionLabels=["drained"],
        distressFlag=False,
        energyAnalysis=c.EnergyAnalysisSchema(
            chargers=["run"], drainers=["meetings"], controllables=[], uncontrollables=[], ruminationLevel="low",
            ruminationCoaching="Let it rest.", microActions=[c.EnergyMicroAction(id=str(i), text=f"a{i}") for i in range(3)],
            tomorrowFocus="Protect the morning.",
        ),
        stimulation=c.StimulationSignalsSchema(behaviours=[], cravingLanguage=False, afterState="none", lowMotivation=False, sleepDisrupted=False, displaced=[], load=0),
        cognition=c.CognitionSignalsSchema(fogOrAttention=False, attentionNote="", passiveConsumptionMinutes=0, shortFormVideo=False, builders=["exercise"], brainRotLoad=0),
    )


def test_prompt_hash_is_pinned():
    assert c.PROMPT_SHA256 == PINNED_PROMPT_SHA256
    assert c.PROMPT_VERSION == "2026.09-v2"


def test_prompt_carries_every_enum_value_and_the_topic_vocabulary():
    prompt = c.build_analysis_system_prompt()
    for values in (c.RUMINATION_LEVELS, c.STIMULATION_CATEGORIES, c.TIMES_OF_DAY, c.AFTER_STATES, c.BUILDERS, c.TOPIC_VOCAB):
        for value in values:
            assert value in prompt, value
    assert "never infer, never diagnose" in prompt
    assert prompt.startswith("You are an empathetic AI psychologist")


def test_schema_has_no_reasoning_field_and_rumination_is_an_enum():
    assert "thought_reasoning" not in c.FeedbackReportSchema.model_fields
    assert c.RUMINATION_LEVELS == ("low", "moderate", "high")
    assert c.literal_values(c.CognitionSignalsSchema, "builders") == c.BUILDERS


def test_persona_is_appended_exactly_like_production():
    assert c.build_analysis_system_prompt("  be blunt ").endswith("\n\nUSER'S CUSTOM INSTRUCTIONS: be blunt")
    assert c.build_analysis_system_prompt("") == c.build_analysis_system_prompt(None)
    messages = c.analysis_messages("Today was fine.", "")
    assert [m["role"] for m in messages] == ["system", "user"] and messages[1]["content"] == "Today was fine."


def test_local_json_schema_is_lean_and_closed():
    local = json.dumps(c.analysis_json_schema(for_local=True))
    assert "description" not in local and '"minimum"' not in local and '"maximum"' not in local
    assert '"additionalProperties": false' in local
    cloud = c.analysis_json_schema(for_local=False)
    assert cloud["properties"]["moodScore"]["minimum"] == 1


def test_business_rules_accept_a_consistent_report_and_name_each_problem():
    assert c.check_business_rules(_good_report()) == []
    bad = _good_report()
    bad.topics = [c.TopicWeight(topic="work", weight=0.4), c.TopicWeight(topic="gardening", weight=0.4)]
    bad.energyAnalysis.microActions = bad.energyAnalysis.microActions[:2]
    bad.emotionLabels = []
    bad.stimulation.load = 2
    bad.cognition.brainRotLoad = 1
    problems = "\n".join(c.check_business_rules(bad))
    for needle in ("sum to 0.80", "gardening", "microActions has 2", "emotionLabels has 0", "load must be 0", "brainRotLoad must be 0"):
        assert needle in problems, needle


def test_pipeline_shim_exports_the_same_objects():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from data_pipeline import contracts
    from data_pipeline.schemas import feedback_schema
    assert contracts.FeedbackReportSchema is c.FeedbackReportSchema
    assert feedback_schema.FeedbackReportSchema is c.FeedbackReportSchema
    assert contracts.build_analysis_system_prompt() == c.build_analysis_system_prompt()
