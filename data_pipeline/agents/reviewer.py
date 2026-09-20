"""Reviewer: judges the entry text before any labelling. Fails closed on an unreadable reply."""
from __future__ import annotations

from pydantic import BaseModel, Field

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_structured
from data_pipeline.endpoints import Endpoint


class ReviewVerdict(BaseModel):
    approved: bool
    critique: str = Field(description="One or two sentences: why it was approved, or exactly what the editor must fix.")


REVIEWER_SYSTEM_PROMPT = """You are an experienced editor and a researcher of how people actually write in private journals.
Review a simulated journal entry.
1. Authenticity: does it read like a real person writing privately, or like a model imitating a diary? Reject clichés ("Today was a day of contemplation"), tidy lessons at the end, and lists of feelings without events.
2. Substance: is there enough specific situational detail for a coach to work with?
3. Voice: does the style match the requested persona, emotion and topic, including the requested messiness or polish?
Return only a JSON object with "approved" (true or false) and "critique"."""


LESSONS_HEADER = "Entries you approved earlier were later rejected by the judge for these reasons. Be stricter about them:"


def build_reviewer_messages(entry: str, profile: dict, lessons: list[str] | None = None) -> list[dict]:
    user = (
        "Target persona and style:\n"
        f"- Role: {profile['persona']['role']}\n- Emotion: {profile['emotion']}\n- Topic: {profile['topic']}\n"
        f"- Expected style: {profile['style']}\n\nSimulated journal entry:\n\"\"\"{entry}\"\"\"\n\nReview it as JSON."
    )
    system = REVIEWER_SYSTEM_PROMPT
    if lessons:
        system += "\n\n" + LESSONS_HEADER + "\n" + "\n".join(f"- {lesson}" for lesson in lessons)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def review_journal_entry(entry: str, profile: dict, *, endpoint: Endpoint, lessons: list[str] | None = None) -> tuple[dict, dict]:
    messages = build_reviewer_messages(entry, profile, lessons)
    result = await acall_structured(endpoint, messages, ReviewVerdict, temperature=0.2, max_tokens=config.MAX_TOKENS_REVIEW)
    if result.parsed is None:
        return {"approved": False, "critique": f"reviewer output unreadable ({result.error}); tighten the entry's concrete detail"}, result.usage
    return result.parsed.model_dump(), result.usage
