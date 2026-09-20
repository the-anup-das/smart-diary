"""Reviewer Agent (powered by Gemma)."""

import re
import json_repair
from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm

REVIEWER_SYSTEM_PROMPT = """You are an experienced creative editor and human psychology researcher.
Your task is to review a simulated personal journal entry.
Evaluate:
1. Authenticity: Does it sound like a real person writing privately, or does it sound like an AI trying to sound like a diary? (Reject cliches like "Today was a day of contemplation" or overly neat conclusions).
2. Emotional Depth: Is there sufficient emotional substance or specific situational detail for a psychologist/CBT coach to analyze?
3. Natural Voice: Does the style match the requested persona and topic?

Respond strictly in JSON format with two keys:
{
  "approved": true or false,
  "critique": "Brief 1-2 sentence explanation of why it was approved or what specific aspects the editor needs to fix."
}
"""

async def review_journal_entry(entry: str, profile: dict) -> tuple[dict, dict]:
    """Reviews the journal entry asynchronously and robustly parses the JSON."""
    user_prompt = f"""Target Persona & Style:
- Role: {profile['persona']['role']}
- Emotion: {profile['emotion']}
- Topic: {profile['topic']}
- Expected Style: {profile['style']}

Simulated Journal Entry:
\"\"\"{entry}\"\"\"

Provide your review as JSON:"""

    raw_response, usage = await acall_llm(
        model=config.REVIEWER_MODEL,
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.2,
    )
    
    # Resilient JSON parsing
    try:
        parsed = json_repair.loads(raw_response)
        if not isinstance(parsed, dict):
            raise ValueError("Parsed JSON is not a dictionary")
        # Ensure keys exist
        if "approved" not in parsed:
            parsed["approved"] = True
        return parsed, usage
    except Exception:
        # Fallback if parsing completely fails
        is_approved = "approved\": true" in raw_response.lower()
        return {"approved": is_approved, "critique": raw_response[:200]}, usage
