"""Schema Validator Node (Programmatic - no LLM tokens).
Validates the Analyzer's JSON output against the strict Pydantic FeedbackReportSchema.
"""

from typing import Tuple, Optional
from pydantic import ValidationError
from data_pipeline.schemas.feedback_schema import FeedbackReportSchema

def validate_schema(data: dict) -> Tuple[bool, Optional[str], Optional[FeedbackReportSchema]]:
    """
    Validates a dictionary against FeedbackReportSchema.
    Returns (is_valid, error_message, validated_schema_instance)
    """
    try:
        instance = FeedbackReportSchema.model_validate(data)
        
        # Check topic weights sum close to 1.0
        if instance.topics:
            total_weight = sum(t.weight for t in instance.topics)
            if not (0.90 <= total_weight <= 1.10):
                return False, f"Topic weights sum to {total_weight:.2f}, must be ~1.0", None
                
        # Check energy microActions has exactly 3 items
        if len(instance.energyAnalysis.microActions) != 3:
            return False, f"microActions count is {len(instance.energyAnalysis.microActions)}, required exactly 3", None

        return True, None, instance
    except ValidationError as ve:
        error_msg = "; ".join([f"{e['loc']}: {e['msg']}" for e in ve.errors()[:3]])
        return False, error_msg, None
    except Exception as e:
        return False, str(e), None
