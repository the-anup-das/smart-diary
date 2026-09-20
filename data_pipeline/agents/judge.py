"""Judge Agent (powered by Gemma)."""

import json
import json_repair
from data_pipeline import config
from data_pipeline.agents.llm_client import acall_llm

JUDGE_SYSTEM_PROMPT = """You are the Supreme Judge of training data quality for an AI Psychologist fine-tuning project.
Your sole mandate is zero-tolerance for low-quality, hallucinatory, insensitive, or mechanically broken examples.

You review:
1. The User's Journal Entry
2. The Teacher's Chain of Thought reasoning
3. The Teacher's generated JSON schema output
4. The QE Agent's report and recommendation

Grading Criteria:
- Pass: The entry is realistic, the reasoning is clinically sound, the CBT reframes are genuinely helpful, and the JSON is completely accurate.
- Fail: Any sign of clinical hallucination, toxic/inappropriate CBT reframing, mislabeling acute distress, or obvious inconsistencies between entry and scores.

Scoring Policy:
- If your verdict is PASS and QE recommended PASS: QE gets +1 point.
- If your verdict is FAIL and QE recommended PASS: QE gets -1 point (false positive penalty).
- If your verdict is PASS and QE recommended FAIL: QE gets -1 point (false negative penalty).

Respond strictly as JSON:
{
  "decision": "PASS" or "FAIL",
  "score_delta": 1 or -1,
  "reason": "Clear explanation of the final verdict and any critical quality flaws."
}
"""

async def judge_candidate(
    entry: str,
    thought_block: str,
    analysis_json: dict,
    qe_report: dict,
) -> tuple[dict, dict]:
    """Renders final verdict on training candidate asynchronously."""
    user_prompt = f"""[JOURNAL ENTRY]
\"\"\"{entry}\"\"\"

[CHAIN OF THOUGHT]
\"\"\"{thought_block}\"\"\"

[ANALYSIS JSON]
{json.dumps(analysis_json, indent=2)}

[QE AGENT REPORT]
{json.dumps(qe_report, indent=2)}

Render your final verdict as strict JSON:"""

    raw_response, usage = await acall_llm(
        model=config.JUDGE_MODEL,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.1,
    )

    try:
        parsed = json_repair.loads(raw_response)
        if not isinstance(parsed, dict) or "decision" not in parsed:
            raise ValueError("Invalid format")
        return parsed, usage
    except Exception:
        is_pass = "PASS" in raw_response.upper() and "FAIL" not in raw_response.upper()
        return {
            "decision": "PASS" if is_pass else "FAIL",
            "score_delta": 1 if is_pass else -1,
            "reason": raw_response[:200]
        }, usage
