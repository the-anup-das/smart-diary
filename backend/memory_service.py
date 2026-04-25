"""
memory_service.py — mem0-powered long-term memory for Smart Diary

Architecture:
  - Every diary entry ingested → mem0 extracts and stores key life facts per user
  - At decision time → search memories relevant to the topic → inject as grounded context
  - Vector store: Qdrant (self-hosted in Docker)
  - Embedder: OpenAI text-embedding-3-small
  - LLM for extraction: gpt-4o-mini
"""

import os
from mem0 import Memory

# Configure mem0 with self-hosted Qdrant and OpenAI
_MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": os.getenv("QDRANT_HOST", "qdrant"),
            "port": int(os.getenv("QDRANT_PORT", "6333")),
            "collection_name": "diary_memories",
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": os.getenv("CHAT_MODEL", "gpt-4o-mini"),
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
    },
    # Custom instructions so mem0 extracts life-relevant facts, not trivial details
    "custom_fact_extraction_prompt": (
        "Extract important, durable facts about this person's life from their diary entry. "
        "Focus on: values they express, fears they mention, family/relationship context, "
        "career situation, financial concerns, health, goals, recurring struggles, "
        "and significant life events or decisions. "
        "Ignore trivial day-to-day events (e.g., 'had coffee') unless they reveal patterns. "
        "Each memory should be a clear, specific, standalone statement."
    )
}

# Lazy-initialize so import doesn't fail if Qdrant is unreachable at boot
_memory_client: Memory | None = None

def get_memory() -> Memory | None:
    """Returns the initialized Memory client, or None if unavailable."""
    global _memory_client
    if _memory_client is None:
        try:
            _memory_client = Memory.from_config(_MEM0_CONFIG)
        except Exception as e:
            print(f"[MemoryService] Failed to initialize mem0: {e}", flush=True)
            return None
    return _memory_client


def ingest_diary_entry(user_id: str, entry_text: str, entry_date: str) -> None:
    """
    Ingests a diary entry into the memory store.
    mem0 automatically extracts key life facts and deduplicates.
    Called after every successful diary analysis.
    """
    memory = get_memory()
    if not memory:
        return
    
    try:
        messages = [{"role": "user", "content": entry_text}]
        result = memory.add(messages, user_id=user_id, metadata={"date": entry_date})
        added = len(result.get("results", []))
        print(f"[MemoryService] Ingested entry for {user_id}: {added} memories extracted.", flush=True)
    except Exception as e:
        print(f"[MemoryService] Failed to ingest entry: {e}", flush=True)


def search_memories(user_id: str, query: str, limit: int = 8) -> str:
    """
    Searches the memory store for facts relevant to a decision topic.
    Returns a formatted string ready to inject into the agent prompt.
    """
    memory = get_memory()
    if not memory:
        return ""
    
    try:
        results = memory.search(query, user_id=user_id, limit=limit)
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


def get_all_memories(user_id: str) -> list:
    """Returns all stored memories for a user (for display in settings)."""
    memory = get_memory()
    if not memory:
        return []
    try:
        result = memory.get_all(user_id=user_id)
        return result.get("results", [])
    except Exception as e:
        print(f"[MemoryService] get_all failed: {e}", flush=True)
        return []


def delete_all_memories(user_id: str) -> bool:
    """Deletes all memories for a user (privacy control)."""
    memory = get_memory()
    if not memory:
        return False
    try:
        memory.delete_all(user_id=user_id)
        return True
    except Exception as e:
        print(f"[MemoryService] delete_all failed: {e}", flush=True)
        return False
