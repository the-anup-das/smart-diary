"""Compatibility re-export. The schema lives in backend/ai_contracts/analysis.py; see data_pipeline/contracts.py."""
from data_pipeline.contracts import (  # noqa: F401
    FeedbackReportSchema,
    EnergyAnalysisSchema,
    EnergyItem,
    EnergyMicroAction,
    GrammarFix,
    CognitiveReframe,
    TopicWeight,
    StimulationBehaviour,
    StimulationSignalsSchema,
    CognitionSignalsSchema,
)
