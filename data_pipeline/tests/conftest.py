import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
os.environ.setdefault("LLM_API_KEY", "test-key")

import pytest  # noqa: E402

from data_pipeline.endpoints import Endpoint  # noqa: E402


def good_analysis() -> dict:
    """An analysis that validates against the contract and passes the business rules."""
    return {
        "moodScore": 6, "sentiment": "Tired", "grammarScore": 8, "grammarFixes": [], "openLoops": ["finish the report"],
        "cognitiveReframes": [{"negativeThought": "I never finish anything", "reframe": "I finished two of three things today."}],
        "topics": [{"topic": "work", "weight": 0.7}, {"topic": "health", "weight": 0.3}],
        "selfFocusScore": 6, "selfFocusFeedback": "Mostly about your own day.", "repetitiveWords": ["really"],
        "repetitiveWordingFeedback": "Vary the intensifiers.", "detectedDecision": None, "emotionLabels": ["drained"],
        "distressFlag": False,
        "energyAnalysis": {
            "chargers": ["run"], "drainers": ["meetings"], "controllables": [{"item": "meetings", "reframe": "Decline one."}],
            "uncontrollables": [], "ruminationLevel": "low", "ruminationCoaching": "Let it rest.",
            "microActions": [{"id": "a", "text": "walk"}, {"id": "b", "text": "water"}, {"id": "c", "text": "bed by 11"}],
            "tomorrowFocus": "Protect the morning.",
        },
        "stimulation": {"behaviours": [], "cravingLanguage": False, "afterState": "none", "lowMotivation": False, "sleepDisrupted": False, "displaced": [], "load": 0},
        "cognition": {"fogOrAttention": False, "attentionNote": "", "passiveConsumptionMinutes": 0, "shortFormVideo": False, "builders": ["exercise"], "brainRotLoad": 0},
    }


def good_verdict(**overrides) -> dict:
    verdict = {
        "grounding": 9, "safety": 10, "cbt_quality": 8, "schema_semantics": 9, "persona_adherence": 10, "overall": 9,
        "hard_fail": False, "hard_fail_reason": "", "entry_notes": "", "label_notes": "",
    }
    verdict.update(overrides)
    return verdict


def profile(edge: str | None = None, persona: str | None = None) -> dict:
    return {
        "persona": {"age_group": "Mid-Life (31-40)", "role": "Working parent", "context": "tired"},
        "emotion": "Deeply exhausted and defeated", "topic": "Work & Career", "style": "Short, punchy sentences",
        "length": {"category": "short", "min_words": 40, "max_words": 80},
        "edge_case": {"type": edge, "description": edge} if edge else None,
        "custom_persona_prompt": persona,
    }


@pytest.fixture
def endpoint() -> Endpoint:
    return Endpoint(base_url="http://test.local/v1", api_key="k", model="test-model", name="test")


@pytest.fixture
def analysis() -> dict:
    return good_analysis()
