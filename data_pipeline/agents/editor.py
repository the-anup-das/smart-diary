"""Editor Agent (powered by Qwen)."""

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm

EDITOR_SYSTEM_PROMPT = """You are a master creative writer and prose editor.
You are given a rough draft of a personal journal entry and a critique from a senior reviewer.
Your job is to revise the journal entry to directly address the critique while keeping the core persona, emotion, and story intact.
Rules:
- Keep the first-person perspective ('I').
- Fix any artificial/AI-sounding phrases, cliches, or lack of concrete details.
- Output ONLY the revised journal entry. No explanations or notes.
"""

async def edit_journal_entry(entry: str, critique: str, profile: dict) -> tuple[str, dict]:
    """Edits the draft based on critique asynchronously."""
    user_prompt = f"""Original Draft:
\"\"\"{entry}\"\"\"

Reviewer Critique:
{critique}

Persona Context:
{profile['persona']['role']} experiencing {profile['emotion']}.

Return the revised journal entry text now:"""

    revised, usage = await acall_llm(
        model=config.EDITOR_MODEL,
        system_prompt=EDITOR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,
    )
    return revised.strip(), usage
