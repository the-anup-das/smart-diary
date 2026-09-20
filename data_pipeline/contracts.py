"""
Bridge to the backend's analysis contract.

The pipeline, the evaluator and production must agree byte for byte on the schema and the
system prompt, so there is exactly one copy, in `backend/ai_contracts/analysis.py`. This shim
puts the backend folder on sys.path and re-exports that module.
"""
import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from ai_contracts.analysis import *  # noqa: E402,F401,F403
from ai_contracts.analysis import __all__  # noqa: E402,F401
