"""Quality Engineering (QE) Agent (powered by Qwen)."""

import json
import json_repair
from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm

QE_SYSTEM_PROMPT = """You are a meticulous Quality Engineering (QE) Agent specializing in AI psychology and data quality.
Your mission is to inspect synthetic training data pairs and generate a comprehensive quality report.

Inspection Criteria:
1. Alignment: Does the analysis accurately reflect the emotional nuances described in the journal entry without inventing unmentioned facts?
2. CBT Quality: Are the cognitive reframes truly constructive, empowering, and grounded in cognitive behavioral therapy principles?
3. Safety Verification: Was the distressFlag set accurately? (True ONLY for genuine suicidal ideation/acute despair, FALSE for venting or everyday stress).
4. CoT Reasonableness: Does the <thought> block provide sound psychological deduction before concluding on scores?

Output strictly as JSON:
{
  "pass_recommendation": true or false,
  "confidence_score": float (0.0 to 1.0),
  "strengths": ["list of positive aspects"],
  "weaknesses": ["list of issues or red flags"],
  "summary": "Concise 1-2 sentence overall evaluation"
}
"""

async def evaluate_data_triplet(
    entry: str,
    thought_block: str,
    analysis_json: dict,
    qe_score: int = 0,
    past_rejections: list = None,
) -> tuple[dict, dict]:
    """Evaluates the entry, reasoning, and JSON asynchronously."""
    history_context = ""
    if past_rejections:
        recent = past_rejections[-3:]
        history_context = f"\n[LEARNING CONTEXT] Your current score is {qe_score}. Past examples the Judge rejected had these issues:\n- " + "\n- ".join(recent) + "\nAvoid recommending examples that exhibit similar defects."

    user_prompt = f"""{history_context}

[USER JOURNAL ENTRY]
\"\"\"{entry}\"\"\"

[ANALYZER CHAIN OF THOUGHT]
\"\"\"{thought_block}\"\"\"

[ANALYZER JSON OUTPUT]
{json.dumps(analysis_json, indent=2)}

Provide your QE quality report now as strict JSON:"""

    raw_response, usage = await acall_llm(
        model=config.QE_MODEL,
        system_prompt=QE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.2,
    )

    try:
        parsed = json_repair.loads(raw_response)
        if not isinstance(parsed, dict) or "pass_recommendation" not in parsed:
            raise ValueError("Invalid format")
        return parsed, usage
    except Exception:
        is_pass = "pass_recommendation\": true" in raw_response.lower()
        return {
            "pass_recommendation": is_pass,
            "confidence_score": 0.8 if is_pass else 0.4,
            "strengths": [],
            "weaknesses": [raw_response[:150]],
            "summary": "Parsed via fallback"
        }, usage
