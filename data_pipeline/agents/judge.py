"""
The quality gate: one rubric-scored call, temperature 0, structured output, fail closed.

The judge is a different model from the analyzer so labels are not graded by their author.
Its verdict does three jobs: it gates the sample, its critique drives one repair attempt by
the analyzer, and its notes feed the lessons store that steers later samples.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_structured
from data_pipeline.contracts import PERSONA_HEADER, TOPIC_VOCAB
from data_pipeline.endpoints import Endpoint


class JudgeVerdict(BaseModel):
    grounding: int = Field(ge=0, le=10, description="Every claim in the analysis is supported by the entry; nothing invented.")
    safety: int = Field(ge=0, le=10, description="distressFlag is correct: true only for acute crisis or self-harm signals, false for ordinary venting.")
    cbt_quality: int = Field(ge=0, le=10, description="Reframes are specific, kind, believable and grounded in CBT; micro-actions are concrete and tied to the drainers.")
    schema_semantics: int = Field(ge=0, le=10, description="Values mean what the field means: topics from the vocabulary summing to 1.0, exactly 3 micro-actions, rumination level matching the text, stimulation and cognition fields only when the entry states them.")
    persona_adherence: int = Field(ge=0, le=10, description="The custom instructions, when present, are followed in tone. 10 when there are none.")
    overall: int = Field(ge=0, le=10, description="Would this pair teach a small model the right behaviour?")
    hard_fail: bool = Field(description="True for any disqualifying problem, whatever the scores.")
    hard_fail_reason: str = Field(description="The disqualifying problem in one sentence, or an empty string.")
    entry_notes: str = Field(description="What is wrong with the journal entry text itself (unrealistic, generic, contradictory), or an empty string.")
    label_notes: str = Field(description="What is wrong with the analysis (specific fields and why), or an empty string.")


JUDGE_SYSTEM_PROMPT = f"""You are the quality gate for a dataset that teaches a small model to analyse private journal entries.
You receive a journal entry and the analysis a teacher model produced for it. Grade the pair strictly.

Score each dimension 0-10:
- grounding: every claim in the analysis is supported by the entry. Invented facts, feelings or events score low.
- safety: distressFlag is true ONLY for clear self-harm, suicidal thoughts or acute crisis, and false for ordinary sadness, stress, anger or figurative venting ("this job is killing me"). A wrong flag in either direction is a hard fail.
- cbt_quality: reframes are specific to the entry, believable and kind, never dismissive or preachy; micro-actions are concrete and tied to the drainers; tomorrowFocus is realistic.
- schema_semantics: topics use the vocabulary ({", ".join(TOPIC_VOCAB)}) and weights sum to 1.0; exactly 3 micro-actions; ruminationLevel matches how much the writer loops; stimulation behaviours, minutes of passive consumption, short-form video, fog and builders appear ONLY when the entry states them; load and brainRotLoad are 0 when nothing relevant is mentioned.
- persona_adherence: when the analysis was given custom instructions, the tone follows them; 10 when there are none.
- overall: would this pair teach a small model the right behaviour?

hard_fail is true when any of these holds: distressFlag is wrong; a stimulation or cognition value is not stated in the entry; passiveConsumptionMinutes is invented; a reframe is unsafe or dismissive; the mood score contradicts the entry; the analysis is about a different entry.

entry_notes: problems with the entry text (unrealistic, generic, contradictory), or empty.
label_notes: problems with the analysis, naming the fields, or empty.
Return only the JSON verdict."""


def build_judge_messages(entry: str, analysis_json: dict, custom_persona: str | None = None) -> list[dict]:
    persona_block = f"\n\n[CUSTOM INSTRUCTIONS GIVEN TO THE ANALYSIS]\n{PERSONA_HEADER}{custom_persona}" if custom_persona else ""
    user = (
        f"[JOURNAL ENTRY]\n\"\"\"{entry}\"\"\"{persona_block}\n\n"
        f"[ANALYSIS]\n{json.dumps(analysis_json, ensure_ascii=False, indent=1)}\n\n"
        "Grade the pair and return the JSON verdict."
    )
    return [{"role": "system", "content": JUDGE_SYSTEM_PROMPT}, {"role": "user", "content": user}]


def fail_closed(reason: str) -> dict:
    return {
        "grounding": 0, "safety": 0, "cbt_quality": 0, "schema_semantics": 0, "persona_adherence": 0, "overall": 0,
        "hard_fail": True, "hard_fail_reason": reason, "entry_notes": "", "label_notes": "", "unparseable": True,
    }


async def judge_candidate(entry: str, analysis_json: dict, custom_persona: str | None, *, endpoint: Endpoint) -> tuple[dict, dict]:
    """Returns (verdict, usage). An unparseable verdict is a fail."""
    messages = build_judge_messages(entry, analysis_json, custom_persona)
    result = await acall_structured(endpoint, messages, JudgeVerdict, temperature=0.0, max_tokens=config.MAX_TOKENS_JUDGE)
    if result.parsed is None:
        return fail_closed(f"judge output unparseable: {result.error}"), result.usage
    return result.parsed.model_dump(), result.usage


def judge_passes(verdict: dict) -> bool:
    return (
        not verdict.get("hard_fail", True)
        and int(verdict.get("overall", 0)) >= config.JUDGE_THRESHOLD
        and int(verdict.get("safety", 0)) >= config.JUDGE_SAFETY_MIN
    )


def judge_reason(verdict: dict) -> str:
    if verdict.get("hard_fail") and verdict.get("hard_fail_reason"):
        return verdict["hard_fail_reason"]
    if verdict.get("label_notes"):
        return verdict["label_notes"]
    if int(verdict.get("safety", 0)) < config.JUDGE_SAFETY_MIN:
        return f"safety score {verdict.get('safety')} below {config.JUDGE_SAFETY_MIN}"
    return f"overall score {verdict.get('overall')} below {config.JUDGE_THRESHOLD}"
