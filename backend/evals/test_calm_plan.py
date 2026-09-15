"""
DeepEval benchmark for the 3-Minute Reset planner (routers/calm.py).
Needs `deepeval` and a live OPENAI_API_KEY:  cd backend && python -m pytest evals/test_calm_plan.py
"""
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from routers.calm import build_reset_plan, RUMINATION_TYPES


@pytest.mark.parametrize("diary_text, expected_types", [
    (
        "I keep replaying the review with my manager. I should have pushed back on the deadline instead of just nodding. "
        "Now it is 1am and I am rewriting the conversation in my head for the tenth time.",
        {"past_regret", "mixed"},
    ),
    (
        "The demo is on Thursday and I cannot stop thinking about everything that could go wrong. What if the API is slow, "
        "what if they ask about pricing, what if I freeze.",
        {"future_worry", "mixed"},
    ),
])
def test_reset_plan_is_faithful_and_specific(diary_text, expected_types):
    plan, usage = build_reset_plan(diary_text, energy={"rumination_level": "high"})

    assert plan["ruminationType"] in RUMINATION_TYPES and plan["ruminationType"] in expected_types
    assert len(plan["visualisation"]) == 4 and len(plan["affirmations"]) == 3
    assert all(len(line.split()) <= 24 for line in plan["visualisation"])
    assert not any("!" in a for a in plan["affirmations"]), "affirmations must stay calm, no exclamation marks"
    assert usage["total_tokens"] > 0

    actual_output = (
        f"Loop: {plan['loopThought']} Acknowledgement: {plan['acknowledgement']} "
        f"Let go: {plan['letGo']} What matters: {plan['whatMatters']} "
        f"Visualisation: {' '.join(plan['visualisation'])} Question: {plan['lessonQuestion']}"
    )
    test_case = LLMTestCase(input=diary_text, actual_output=actual_output, retrieval_context=[diary_text])
    assert_test(test_case, [FaithfulnessMetric(threshold=0.7), AnswerRelevancyMetric(threshold=0.7)])
