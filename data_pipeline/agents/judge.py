"""
The quality gate: one rubric-scored call, temperature 0, structured output, fail closed.

The judge is a different model from the analyzer so labels are not graded by their author.
Its verdict does three jobs: it gates the sample, its critique drives one repair attempt by
the analyzer, and its notes feed the lessons store that steers later samples.
"""
from __future__ import annotations

import json

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_structured, as_text
from data_pipeline.contracts import PERSONA_HEADER, TOPIC_VOCAB
from data_pipeline.endpoints import Endpoint


class JudgeVerdict(BaseModel):
    # Filled from the entry alone, before the analysis's numbers are looked at. Code compares them with
    # the labels, because a judge reading the analysis as a whole does not reliably notice a mood of 9
    # on a despairing entry or "low" rumination on an entry that loops all night.
    own_mood: int = Field(ge=1, le=10, description="From the entry alone: its mood, 1 (lowest) to 10 (best).")
    own_rumination: Literal["low", "moderate", "high"] = Field(description="From the entry alone: how much the writer loops on the same worry.")
    own_distress: bool = Field(description="From the entry alone: self-harm, suicidal thoughts, an acute crisis, or a passive wish to die or vanish?")
    grounding: int = Field(ge=0, le=10, description="Every claim in the analysis is supported by the entry; nothing invented.")
    safety: int = Field(ge=0, le=10, description="distressFlag is correct: true only for acute crisis or self-harm signals, false for ordinary venting.")
    cbt_quality: int = Field(ge=0, le=10, description="Reframes are specific, kind, believable and grounded in CBT; micro-actions are concrete and tied to the drainers.")
    schema_semantics: int = Field(ge=0, le=10, description="Values mean what the field means: topics from the vocabulary summing to 1.0, exactly 3 micro-actions, rumination level matching the text, stimulation and cognition fields only when the entry states them.")
    persona_adherence: int = Field(ge=0, le=10, description="The custom instructions, when present, are followed in tone. 10 when there are none.")
    overall: int = Field(ge=0, le=10, description="Would this pair teach a small model the right behaviour?")
    hard_fail: bool = Field(description="True for any disqualifying problem, whatever the scores.")
    hard_fail_reason: Annotated[str, BeforeValidator(as_text)] = Field(description="The disqualifying problem in one sentence, or an empty string.")
    entry_notes: Annotated[str, BeforeValidator(as_text)] = Field(description="What is wrong with the journal entry text itself (unrealistic, generic, contradictory), or an empty string.")
    label_notes: Annotated[str, BeforeValidator(as_text)] = Field(description="What is wrong with the analysis (specific fields and why), or an empty string.")


JUDGE_SYSTEM_PROMPT = f"""You are the quality gate for a dataset that teaches a small model to analyse private journal entries.
You receive a journal entry and the analysis a teacher model produced for it. Grade the pair strictly.

Work in two steps. First read ONLY the journal entry and fill own_mood, own_rumination and own_distress
from it, as if no analysis existed. Then read the analysis and grade it.

Score each dimension 0-10:
- grounding: every claim in the analysis is supported by the entry. Invented facts, feelings or events score low.
- safety: distressFlag is true for self-harm, suicidal thoughts, an acute crisis, or a passive wish to die or vanish (wanting to disappear, not wanting to wake up, others better off without them, not seeing how to keep going), and false for ordinary sadness, stress, anger or figurative venting ("this job is killing me"). A passive wish to die labelled false is the most harmful mistake a sample can teach. A wrong flag in either direction is a hard fail.
- cbt_quality: reframes are specific to the entry, believable and kind, never dismissive or preachy; micro-actions are concrete and tied to the drainers; tomorrowFocus is realistic.
- schema_semantics: topics use the vocabulary ({", ".join(TOPIC_VOCAB)}) and weights sum to 1.0; exactly 3 micro-actions; ruminationLevel matches how much the writer loops; stimulation and cognition signals match the entry in both directions: a behaviour, fog, short-form video, minutes of passive consumption or a builder is claimed only when the entry describes it, AND one the entry does describe (scrolling, late-night screens, reels, binge-watching, a run, a book) is not left out.
- persona_adherence: when the analysis was given custom instructions, the tone follows them; 10 when there are none.
- grammar: grammarScore reflects the text as written. Casual, phone-typed writing with missing capitals, run-ons or wrong words scored 9 or 10, or scored low without its errors listed in grammarFixes, is a label fault: name it in label_notes and lower schema_semantics.
- overall: would this pair teach a small model the right behaviour?

Every stimulation and cognition field is required in every analysis. When the entry mentions nothing, the correct values are 0, false, "none", "unknown" and empty lists: those say "not mentioned" and are never a fault. Only a positive claim can be invented.

hard_fail is true when any of these holds: distressFlag is wrong; the analysis claims a stimulation or cognition signal the entry does not describe (a behaviour, load or brainRotLoad above 0, shortFormVideo or fogOrAttention true, a builder, or passiveConsumptionMinutes above 0 without the entry stating or clearly implying the time); a reframe is unsafe or dismissive; the mood score contradicts the entry; the analysis is about a different entry. A signal the entry describes but the analysis left at 0 is a label fault: name it in label_notes and lower schema_semantics, it is not a hard fail.

entry_notes: problems with the entry text (unrealistic, generic, contradictory), or empty.
label_notes: problems with the analysis, naming the fields, or empty.
Return only the JSON verdict."""


LESSONS_HEADER = "Verdicts on earlier samples that a second judge overturned. Grade more carefully on these:"


def build_judge_messages(entry: str, analysis_json: dict, custom_persona: str | None = None, lessons: list[str] | None = None) -> list[dict]:
    persona_block = f"\n\n[CUSTOM INSTRUCTIONS GIVEN TO THE ANALYSIS]\n{PERSONA_HEADER}{custom_persona}" if custom_persona else ""
    user = (
        f"[JOURNAL ENTRY]\n\"\"\"{entry}\"\"\"{persona_block}\n\n"
        f"[ANALYSIS]\n{json.dumps(analysis_json, ensure_ascii=False, indent=1)}\n\n"
        "Grade the pair and return the JSON verdict."
    )
    system = JUDGE_SYSTEM_PROMPT
    if lessons:
        system += "\n\n" + LESSONS_HEADER + "\n" + "\n".join(f"- {lesson}" for lesson in lessons)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def fail_closed(reason: str) -> dict:
    return {
        "grounding": 0, "safety": 0, "cbt_quality": 0, "schema_semantics": 0, "persona_adherence": 0, "overall": 0,
        "hard_fail": True, "hard_fail_reason": reason, "entry_notes": "", "label_notes": "", "unparseable": True,
    }


MOOD_GAP_FAIL = 3   # a mood this far from the judge's own reading contradicts the entry


def cross_check(verdict: dict, analysis: dict) -> list[str]:
    """Where the labels disagree with the judge's own reading of the entry. Each item is a hard fail."""
    problems: list[str] = []
    mood, own_mood = analysis.get("moodScore"), verdict.get("own_mood")
    if isinstance(mood, int) and isinstance(own_mood, int) and abs(mood - own_mood) >= MOOD_GAP_FAIL:
        problems.append(f"moodScore {mood} contradicts the entry, which reads as about {own_mood}")
    level = (analysis.get("energyAnalysis") or {}).get("ruminationLevel")
    own_level = verdict.get("own_rumination")
    if {level, own_level} == {"low", "high"}:
        problems.append(f"ruminationLevel '{level}' contradicts the entry, which reads as '{own_level}'")
    flag, own_flag = analysis.get("distressFlag"), verdict.get("own_distress")
    if isinstance(flag, bool) and isinstance(own_flag, bool) and flag != own_flag:
        problems.append(
            "distressFlag is false but the entry shows a crisis or a passive wish to die" if own_flag
            else "distressFlag is true but the entry shows no crisis signal"
        )
    return problems


def apply_cross_check(verdict: dict, analysis: dict) -> dict:
    """Turn a disagreement between the judge's reading and the labels into a hard fail with the reason."""
    problems = cross_check(verdict, analysis)
    if not problems:
        return verdict
    out = dict(verdict)
    out["cross_check"] = problems
    out["hard_fail"] = True
    out["hard_fail_reason"] = "; ".join(problems)
    notes = (out.get("label_notes") or "").strip()
    out["label_notes"] = "; ".join(problems) + (f"; {notes}" if notes else "")
    return out


async def judge_candidate(entry: str, analysis_json: dict, custom_persona: str | None, *, endpoint: Endpoint, lessons: list[str] | None = None) -> tuple[dict, dict]:
    """Returns (verdict, usage). An unparseable verdict is a fail."""
    messages = build_judge_messages(entry, analysis_json, custom_persona, lessons)
    result = await acall_structured(endpoint, messages, JudgeVerdict, temperature=0.0, max_tokens=config.MAX_TOKENS_JUDGE)
    if result.parsed is None:
        return fail_closed(f"judge output unparseable: {result.error}"), result.usage
    return apply_cross_check(result.parsed.model_dump(), analysis_json), result.usage


def judge_passes(verdict: dict, threshold_bump: int = 0) -> bool:
    """`threshold_bump` raises the bar for a judge whose reputation has slipped."""
    return (
        not verdict.get("hard_fail", True)
        and int(verdict.get("overall", 0)) >= config.JUDGE_THRESHOLD + threshold_bump
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
