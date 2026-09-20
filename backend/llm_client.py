"""
Compatibility shim. Routing lives in llm_router.py and is resolved per request from the person's
preferences; these helpers only exist for code that still asks for a process-wide client.
"""
from llm_router import _client_for, resolve_route


def get_llm_client():
    return _client_for(resolve_route({}))


def get_model_name() -> str:
    return resolve_route({}).model
