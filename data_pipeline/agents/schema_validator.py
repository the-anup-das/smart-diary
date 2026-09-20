"""Schema Validator Node (programmatic, no LLM tokens).

Validates the analyzer's JSON against the production FeedbackReportSchema and the shared
business rules from backend/ai_contracts/analysis.py, so a sample only enters the dataset
when production would accept it.
"""

from typing import Optional, Tuple

from pydantic import ValidationError

from data_pipeline.contracts import FeedbackReportSchema, check_business_rules


def validate_schema(data: dict) -> Tuple[bool, Optional[str], Optional[FeedbackReportSchema]]:
    """Returns (is_valid, error_message, validated_instance)."""
    try:
        instance = FeedbackReportSchema.model_validate(data)
    except ValidationError as ve:
        error_msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in ve.errors()[:5])
        return False, error_msg, None
    except Exception as e:  # noqa: BLE001
        return False, str(e), None

    problems = check_business_rules(instance)
    if problems:
        return False, "; ".join(problems), None
    return True, None, instance
