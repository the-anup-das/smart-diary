"""
memory_service.py: mem0-powered long-term memory for Smart Diary

  - Every diary entry ingested -> mem0 extracts and stores key life facts per user
  - At decision or chat time -> search memories relevant to the topic -> inject as grounded context
  - Vector store: Qdrant (self-hosted in Docker)
  - Fact extraction LLM: whatever the person's AI route resolves to (cloud or local), see llm_router.py
  - Embedder: EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL / EMBEDDING_DIMS, default OpenAI
    text-embedding-3-small. In local mode without EMBEDDING_BASE_URL the embeddings still go to OpenAI;
    the log says so once.
"""

import os
import re

from mem0 import Memory

from llm_router import cloud_route, resolve_route

_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
_memory_clients: dict[str, Memory] = {}
_warned_external_embedder = False

_FACT_PROMPT = (
    "Extract important, durable facts about this person's life from their diary entry. "
    "Focus on: values they express, fears they mention, family/relationship context, "
    "career situation, financial concerns, health, goals, recurring struggles, "
    "and significant life events or decisions. "
    "Ignore trivial day-to-day events (e.g., 'had coffee') unless they reveal patterns. "
    "Each memory should be a clear, specific, standalone statement."
)


def _collection_name(embedding_model: str) -> str:
    """One collection per embedder: vectors from different models have different sizes and meanings."""
    if embedding_model == _DEFAULT_EMBEDDING_MODEL:
        return "diary_memories"
    slug = re.sub(r"[^a-z0-9]+", "_", embedding_model.lower()).strip("_")[:40]
    return f"diary_memories_{slug}"


def build_mem0_config(preferences: dict | None = None) -> tuple[dict, str]:
    """The mem0 config for this person's route, and a key that identifies it for caching."""
    global _warned_external_embedder
    route = resolve_route(preferences)
    llm_config = {"model": route.model, "api_key": route.api_key}
    if route.base_url:
        llm_config["openai_base_url"] = route.base_url

    embedding_model = os.getenv("EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    embedding_base = (os.getenv("EMBEDDING_BASE_URL") or "").strip().rstrip("/")
    embedder_config = {"model": embedding_model, "api_key": os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY") or "empty"}
    if embedding_base:
        embedder_config["openai_base_url"] = embedding_base
    dims = os.getenv("EMBEDDING_DIMS")
    if dims:
        embedder_config["embedding_dims"] = int(dims)
    if route.provider == "local" and not embedding_base and not _warned_external_embedder:
        _warned_external_embedder = True
        print("[MemoryService] Local AI mode, but memories are still embedded with the OpenAI embedder. "
              "Set EMBEDDING_BASE_URL (for example the embed-server compose profile) to keep embeddings local.", flush=True)

    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": os.getenv("QDRANT_HOST", "qdrant"),
                "port": int(os.getenv("QDRANT_PORT", "6333")),
                "collection_name": _collection_name(embedding_model),
                **({"embedding_model_dims": int(dims)} if dims else {}),
            },
        },
        "llm": {"provider": "openai", "config": llm_config},
        "embedder": {"provider": "openai", "config": embedder_config},
        "custom_fact_extraction_prompt": _FACT_PROMPT,
    }
    key = f"{route.provider}|{route.base_url}|{route.model}|{embedding_base}|{embedding_model}"
    return config, key


def get_memory(preferences: dict | None = None) -> Memory | None:
    """The Memory client for this person's route, or None if the store is unavailable."""
    config, key = build_mem0_config(preferences)
    client = _memory_clients.get(key)
    if client is None:
        try:
            client = Memory.from_config(config)
            _memory_clients[key] = client
        except Exception as e:  # noqa: BLE001
            print(f"[MemoryService] Failed to initialize mem0: {e}", flush=True)
            return None
    return client


def ingest_diary_entry(user_id: str, entry_text: str, entry_date: str, preferences: dict | None = None) -> None:
    """
    Ingests a diary entry into the memory store.
    mem0 automatically extracts key life facts and deduplicates.
    Called after every successful diary analysis.
    """
    memory = get_memory(preferences)
    if not memory:
        return
    
    try:
        messages = [{"role": "user", "content": entry_text}]
        result = memory.add(messages, user_id=user_id, metadata={"date": entry_date})
        added = len(result.get("results", []))
        print(f"[MemoryService] Ingested entry for {user_id}: {added} memories extracted.", flush=True)
    except Exception as e:
        print(f"[MemoryService] Failed to ingest entry: {e}", flush=True)


def search_memories(user_id: str, query: str, limit: int = 8, preferences: dict | None = None) -> str:
    """
    Searches the memory store for facts relevant to a decision topic.
    Returns a formatted string ready to inject into the agent prompt.
    """
    memory = get_memory(preferences)
    if not memory:
        return ""
    
    try:
        # mem0 changed its API: older releases take user_id=, newer ones want filters={"user_id": ...}.
        try:
            results = memory.search(query, user_id=user_id, limit=limit)
        except (ValueError, TypeError) as api_change:
            if "filters" not in str(api_change):
                raise
            results = memory.search(query, filters={"user_id": user_id}, limit=limit)
        memories = results.get("results", [])
        
        if not memories:
            return ""
        
        lines = ["## Relevant memories from this user's past diary entries:"]
        for m in memories:
            score = m.get("score", 0)
            text = m.get("memory", "")
            date = m.get("metadata", {}).get("date", "")
            date_str = f" [{date}]" if date else ""
            lines.append(f"- {text}{date_str}  (relevance: {score:.2f})")
        
        return "\n".join(lines)
    except Exception as e:
        print(f"[MemoryService] Search failed: {e}", flush=True)
        return ""


def get_all_memories(user_id: str, preferences: dict | None = None) -> list:
    """Returns all stored memories for a user (for display in settings)."""
    memory = get_memory(preferences)
    if not memory:
        return []
    try:
        try:
            result = memory.get_all(user_id=user_id)
        except (ValueError, TypeError) as api_change:
            if "filters" not in str(api_change):
                raise
            result = memory.get_all(filters={"user_id": user_id})
        return result.get("results", [])
    except Exception as e:
        print(f"[MemoryService] get_all failed: {e}", flush=True)
        return []


def delete_all_memories(user_id: str, preferences: dict | None = None) -> bool:
    """Deletes all memories for a user (privacy control)."""
    memory = get_memory(preferences)
    if not memory:
        return False
    try:
        memory.delete_all(user_id=user_id)
        return True
    except Exception as e:
        print(f"[MemoryService] delete_all failed: {e}", flush=True)
        return False
