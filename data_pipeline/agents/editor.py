"""Editor: revises a draft to address the reviewer's critique without changing who is writing."""
from __future__ import annotations

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm
from data_pipeline.endpoints import Endpoint

EDITOR_SYSTEM_PROMPT = """You revise private journal entries. You get a draft and a reviewer's critique.
Address the critique directly while keeping the same person, emotion, events and requested style.
- Keep the first person.
- Replace generic or model-sounding phrases with concrete details; keep the requested messiness if the style calls for it.
- Return only the revised entry text."""


async def edit_journal_entry(entry: str, critique: str, profile: dict, *, endpoint: Endpoint) -> tuple[str, dict]:
    user = (
        f"Draft:\n\"\"\"{entry}\"\"\"\n\nReviewer critique:\n{critique}\n\n"
        f"Who is writing: {profile['persona']['role']}, feeling {profile['emotion']}, style: {profile['style']}.\n\nRevised entry:"
    )
    messages = [{"role": "system", "content": EDITOR_SYSTEM_PROMPT}, {"role": "user", "content": user}]
    revised, usage = await acall_llm(endpoint, messages, temperature=0.7, max_tokens=config.MAX_TOKENS_ENTRY)
    return revised.strip().strip('"'), usage
