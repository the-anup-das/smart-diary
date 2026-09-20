"""
Teacher analyzer. It sees exactly the production prompt, so the labels it produces are what
the student must learn to reproduce under that prompt. Two generation-time aids never reach
the training records: a short list of lessons from earlier rejections, and a correction turn
when a previous attempt was rejected by the validator or the judge.
"""
from __future__ import annotations

import json

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_structured
from data_pipeline.contracts import FeedbackReportSchema, analysis_messages
from data_pipeline.endpoints import Endpoint

LESSONS_HEADER = "Common mistakes in earlier analyses of other entries. Avoid them:"


def build_analyzer_messages(
    entry: str,
    custom_persona: str | None = None,
    *,
    previous_json: dict | None = None,
    previous_error: str | None = None,
    lessons: list[str] | None = None,
) -> list[dict]:
    messages = analysis_messages(entry, custom_persona or "")
    if lessons:
        messages[0]["content"] += "\n\n" + LESSONS_HEADER + "\n" + "\n".join(f"- {lesson}" for lesson in lessons)
    if previous_json is not None and previous_error:
        messages.append({"role": "assistant", "content": json.dumps(previous_json, ensure_ascii=False)})
        messages.append({
            "role": "user",
            "content": f"That analysis was rejected: {previous_error}\nReturn the corrected JSON object only, with the same schema.",
        })
    return messages


async def analyze_journal_entry(
    entry: str,
    custom_persona: str | None = None,
    *,
    endpoint: Endpoint,
    previous_json: dict | None = None,
    previous_error: str | None = None,
    lessons: list[str] | None = None,
) -> tuple[dict | None, str | None, dict]:
    """Returns (analysis_json, validation_error, usage). The JSON may be present even when invalid."""
    messages = build_analyzer_messages(entry, custom_persona, previous_json=previous_json, previous_error=previous_error, lessons=lessons)
    result = await acall_structured(endpoint, messages, FeedbackReportSchema, temperature=0.2, max_tokens=config.MAX_TOKENS_ANALYSIS)
    return result.data, result.error, result.usage
