"""
Send one journal entry to a served model exactly the way production does, and report whether the
reply validates against the contract, how long it took, and which response format the server took.

    python data_pipeline/scripts/smoke_endpoint.py --base-url http://localhost:8080/v1 --model smart-diary-slm
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.join(REPO_ROOT, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))

from ai_contracts.analysis import FeedbackReportSchema, analysis_messages, check_business_rules  # noqa: E402
from llm_router import LLMRouter, LLMUnavailable, RouteConfig  # noqa: E402

SAMPLE = (
    "Long day. I spent most of the morning scrolling reels instead of starting the report, maybe ninety minutes, "
    "and when I finally opened it I read the same paragraph three times. Went for a run at lunch which helped. "
    "Argued with my sister about the house again and I keep replaying what she said."
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", default="smart-diary-slm")
    parser.add_argument("--api-key", default=os.getenv("LOCAL_LLM_API_KEY", "empty"))
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--entry", default=SAMPLE)
    args = parser.parse_args()

    route = RouteConfig(provider="local", base_url=args.base_url.rstrip("/"), api_key=args.api_key, model=args.model, timeout_s=args.timeout)
    router = LLMRouter(route)
    started = time.monotonic()
    try:
        result = router.structured(FeedbackReportSchema, analysis_messages(args.entry), temperature=0.2, max_tokens=2048, rules=check_business_rules)
    except LLMUnavailable as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    elapsed = time.monotonic() - started
    report = result.parsed
    print(f"OK in {elapsed:.1f}s via {result.mode} on attempt {result.attempts}, {result.usage['completion_tokens']} completion tokens")
    if result.rule_problems:
        print("rule problems left:", "; ".join(result.rule_problems))
    print(json.dumps({
        "moodScore": report.moodScore, "sentiment": report.sentiment, "ruminationLevel": report.energyAnalysis.ruminationLevel,
        "distressFlag": report.distressFlag, "topics": [t.model_dump() for t in report.topics],
        "stimulation.load": report.stimulation.load, "cognition": report.cognition.model_dump(),
    }, indent=1))


if __name__ == "__main__":
    main()
