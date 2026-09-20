"""Writer Agent (powered by Qwen)."""

from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm

WRITER_SYSTEM_PROMPT = """You are a creative human simulator. Your job is to write an authentic, realistic personal journal entry.
Write in FIRST PERSON ('I').
DO NOT write like an AI trying to sound poetic unless specifically requested. Write with realistic human messiness:
- Include concrete details from the person's day (specific interactions, physical sensations, fleeting thoughts).
- Respect the requested emotional tone, writing style, and approximate length.
- DO NOT start with "Dear Diary". Start directly into the thought or scene.
- Return ONLY the journal entry text. No meta-commentary, introductory remarks, or quotes.
"""

async def generate_journal_entry(profile: dict) -> tuple[str, dict]:
    """Generates a raw journal entry asynchronously."""
    persona = profile["persona"]
    edge_case = profile.get("edge_case")
    length = profile["length"]
    
    edge_instructions = ""
    if edge_case:
        edge_instructions = f"\nSPECIAL SCENARIO TO INTEGRATE: {edge_case['description']}"

    user_prompt = f"""Write a personal journal entry with the following constraints:
- Persona: {persona['role']} (Age group: {persona['age_group']}). Context: {persona['context']}
- Primary Topic: {profile['topic']}
- Emotional State: {profile['emotion']}
- Writing Style: {profile['style']}
- Word Count: between {length['min_words']} and {length['max_words']} words.{edge_instructions}

Write the journal entry now:"""

    entry, usage = await acall_llm(
        model=config.WRITER_MODEL,
        system_prompt=WRITER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.85,
    )
    return entry, usage
