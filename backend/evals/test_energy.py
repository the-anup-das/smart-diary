import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from routers.analyze import perform_ai_analysis
import os

# Mock preferences for testing
mock_prefs = {
    "custom_persona_prompt": ""
}

@pytest.mark.parametrize("diary_text, expected_domain", [
    (
        "I spent the whole morning worrying about my bank account and upcoming bills. The weather is so gloomy too.",
        "Finances"
    ),
    (
        "I went to the gym today and set a personal record! Feeling amazing. But I didn't sleep well last night.",
        "Exercise"
    )
])
def test_energy_analysis_quality(diary_text, expected_domain):
    # 1. Run the actual AI analysis logic
    parsed_output, usage = perform_ai_analysis(diary_text, mock_prefs)
    
    # 2. Extract key results for evaluation
    # We'll check if the dominant topic matches our expectation
    # and if the micro-actions are relevant.
    dominant_topic = max(parsed_output.topics, key=lambda t: t.weight).topic.replace("_", " ").title()
    
    # We create an LLMTestCase for DeepEval
    # 'actual_output' is what the user sees (micro-actions and coaching)
    # 'retrieval_context' is the original diary text (what the AI should be faithful to)
    actual_output = f"Sentiment: {parsed_output.sentiment}. Coaching: {parsed_output.energyAnalysis.ruminationCoaching}. Actions: {[a.text for a in parsed_output.energyAnalysis.microActions]}"
    
    test_case = LLMTestCase(
        input=diary_text,
        actual_output=actual_output,
        retrieval_context=[diary_text]
    )
    
    # 3. Define metrics
    # Faithfulness: Does the AI summary contradict the diary?
    faithfulness_metric = FaithfulnessMetric(threshold=0.7)
    # Relevancy: Are the actions relevant to the input text?
    relevancy_metric = AnswerRelevancyMetric(threshold=0.7)
    
    # 4. Assert quality
    assert_test(test_case, [faithfulness_metric, relevancy_metric])

    # 5. Domain specific check (simple python assert)
    assert expected_domain in [t.topic.replace("_", " ").title() for t in parsed_output.topics]
