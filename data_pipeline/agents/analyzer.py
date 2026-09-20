"""Teacher Analyze Agent (powered by Gemma)."""

import re
from typing import Tuple
import json_repair
from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm
from data_pipeline.schemas.feedback_schema import FeedbackReportSchema

ANALYZER_SYSTEM_PROMPT = """You are an expert empathetic AI psychologist, CBT practitioner, and writing coach.
Your task is to analyze personal journal entries with clinical nuance and warmth.

You must ALWAYS format your response in TWO contiguous sections:
Section 1: A <thought>...</thought> block containing your internal psychological reasoning:
- Assess emotional tone, nuance, and mood score (1-10).
- Identify cognitive distortions and formulate realistic CBT reframes.
- Extract energy drainers vs chargers, and controllables vs uncontrollables.
- Safety check: Verify whether distressFlag should be true (strictly for acute crisis/suicidal ideation, NEVER for ordinary venting).
- Inspect for compulsive high-stimulation behaviors and brain fog/brain-building activities.

Section 2: A strictly valid JSON object adhering to the FeedbackReportSchema.

Schema Field Specifications:
- moodScore: 1 (Despair) to 10 (Euphoric)
- sentiment: Single word (e.g. Stressed, Joyful, Neutral, Anxious, Focused, Calm, Wistful, Overwhelmed)
- grammarScore: 1 to 10
- grammarFixes: list of {original, correction, explanation}. Empty list if clean.
- openLoops: list of actionable unresolved tasks or worries
- cognitiveReframes: list of {negativeThought, reframe} using CBT
- topics: list of {topic, weight} where weights sum to 1.0
- selfFocusScore: 1 (others/world) to 10 (extreme self-focus)
- selfFocusFeedback: gentle psychological reflection
- repetitiveWords: list of 3-5 overused words or short phrases
- repetitiveWordingFeedback: coaching tip on vocabulary
- detectedDecision: string topic of life decision if present, else null
- emotionLabels: 1-3 granular emotion words
- distressFlag: boolean (true ONLY for self-harm/suicidal crisis)
- energyAnalysis: {
    chargers: [str],
    drainers: [str],
    controllables: [{item, reframe}],
    uncontrollables: [{item, reframe}],
    ruminationLevel: "low" | "moderate" | "high",
    ruminationCoaching: str,
    microActions: [{id: uuid_str, text: str}] (exactly 3 actions),
    tomorrowFocus: str
  }
- stimulation: {
    behaviours: [{behaviour, category, trigger, timeOfDay, lostControl}],
    cravingLanguage: bool,
    afterState: "none"|"guilt"|"flat"|"restless"|"fine",
    lowMotivation: bool,
    sleepDisrupted: bool,
    displaced: [str],
    load: int (0 to 3)
  }
- cognition: {
    fogOrAttention: bool,
    attentionNote: str,
    passiveConsumptionMinutes: int (0-1440),
    shortFormVideo: bool,
    builders: list of valid builders ("deep_reading", "learning", "creating", "deep_work", "exercise", "nature", "conversation", "play", "rest", "sleep"),
    brainRotLoad: int (0 to 3)
  }
"""

async def analyze_journal_entry(entry: str, custom_persona: str = None) -> Tuple[str, str, dict, dict]:
    """
    Performs AI analysis asynchronously.
    Returns (raw_full_output, thought_block, json_data, usage)
    """
    system_prompt = ANALYZER_SYSTEM_PROMPT
    if custom_persona:
        system_prompt += f"\n\nUSER CUSTOM PERSONA INSTRUCTIONS: {custom_persona}"

    user_prompt = f"""Analyze this journal entry:
\"\"\"{entry}\"\"\"

Generate your <thought> reasoning block first, followed immediately by the JSON object:"""

    raw_response, usage = await acall_llm(
        model=config.ANALYZER_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
    )

    # Extract <thought> block
    thought_match = re.search(r"<thought>(.*?)</thought>", raw_response, re.DOTALL | re.IGNORECASE)
    thought_block = thought_match.group(1).strip() if thought_match else ""

    # Extract JSON part
    json_candidate = raw_response
    if "</thought>" in raw_response:
        json_candidate = raw_response.split("</thought>")[-1]

    # Clean code fences
    json_candidate = re.sub(r"^```json\s*", "", json_candidate.strip(), flags=re.MULTILINE)
    json_candidate = re.sub(r"^```\s*$", "", json_candidate.strip(), flags=re.MULTILINE).strip()

    # Find matching braces if wrapped
    brace_start = json_candidate.find("{")
    brace_end = json_candidate.rfind("}")
    if brace_start != -1 and brace_end != -1:
        json_str = json_candidate[brace_start:brace_end + 1]
    else:
        json_str = json_candidate

    # Use resilient json_repair
    try:
        parsed_json = json_repair.loads(json_str)
        if not isinstance(parsed_json, dict):
            parsed_json = {}
    except Exception:
        parsed_json = {}

    return raw_response, thought_block, parsed_json, usage
