"""Writer: produces the journal entry for a diversity profile. It never sees the custom persona
instruction, which is an analysis-side setting, only the person, mood, topic, style and length."""
from __future__ import annotations

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm
from data_pipeline.endpoints import Endpoint

WRITER_SYSTEM_PROMPT = """You write authentic, private journal entries as a real person would.
Write in the first person. Do not sound like a model trying to be poetic unless the style asks for it.
- Include concrete details from the day: specific interactions, places, physical sensations, passing thoughts.
- Respect the requested emotion, style and approximate length. Messy styles stay messy; do not tidy them.
- Do not start with "Dear Diary" and do not end with a neat lesson.
- Return only the entry text, no title, no quotes, no commentary."""


def build_writer_messages(profile: dict, lessons: list[str] | None = None) -> list[dict]:
    persona, length = profile["persona"], profile["length"]
    edge = profile.get("edge_case")
    edge_line = f"\n- Scenario to weave in naturally: {edge['description']}" if edge else ""
    lessons_block = ""
    if lessons:
        lessons_block = "\n\nPatterns that got earlier entries rejected, avoid them:\n" + "\n".join(f"- {lesson}" for lesson in lessons)
    user = (
        "Write a personal journal entry with these constraints:\n"
        f"- Person: {persona['role']} ({persona['age_group']}). Context: {persona['context']}\n"
        f"- Main topic: {profile['topic']}\n- Emotional state: {profile['emotion']}\n- Writing style: {profile['style']}\n"
        f"- Length: between {length['min_words']} and {length['max_words']} words.{edge_line}{lessons_block}\n\nWrite the entry now:"
    )
    return [{"role": "system", "content": WRITER_SYSTEM_PROMPT}, {"role": "user", "content": user}]


async def generate_journal_entry(profile: dict, *, endpoint: Endpoint, lessons: list[str] | None = None) -> tuple[str, dict]:
    entry, usage = await acall_llm(endpoint, build_writer_messages(profile, lessons), temperature=0.85, max_tokens=config.MAX_TOKENS_ENTRY)
    return entry.strip().strip('"'), usage
