"""Chat with your diary — RAG over journal entries + mem0 long-term memories.

Retrieval is two-pronged:
  1. mem0/Qdrant semantic memories (durable life facts extracted at ingest time)
  2. Keyword-matched + recent journal entries straight from Postgres

Both are injected as grounded context so answers cite real dates instead of
hallucinating a life the user never wrote about.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
from database import get_db
from rate_limit import rate_limit
import models
from .auth import verify_session
from memory_service import search_memories
import openai
import os
import re

router = APIRouter()

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", None)
)

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "what", "when", "where", "how",
    "why", "who", "did", "was", "were", "have", "has", "had", "about", "tell",
    "you", "your", "will", "would", "could", "should", "can", "does", "are",
    "not", "but", "from", "them", "then", "than", "there", "here", "been",
    "feel", "felt", "last", "time", "write", "wrote", "diary", "journal", "entry",
}

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]*>?", "", text or "")


def _retrieve_entries(question: str, user_id: str, db: Session) -> list[models.JournalEntry]:
    """Pull entries that likely answer the question: keyword hits + recent days."""
    keywords = [
        w for w in re.findall(r"[a-zA-Z]{4,}", question.lower())
        if w not in STOPWORDS
    ][:8]

    matched = []
    if keywords:
        query = db.query(models.JournalEntry).filter(
            models.JournalEntry.user_id == user_id,
            models.JournalEntry.is_deleted == False,
        )
        from sqlalchemy import or_
        query = query.filter(or_(*[models.JournalEntry.content.ilike(f"%{kw}%") for kw in keywords]))
        matched = query.order_by(models.JournalEntry.date.desc()).limit(6).all()

    recent = (
        db.query(models.JournalEntry)
        .filter(
            models.JournalEntry.user_id == user_id,
            models.JournalEntry.is_deleted == False,
            models.JournalEntry.date >= datetime.utcnow() - timedelta(days=7),
        )
        .order_by(models.JournalEntry.date.desc())
        .limit(4)
        .all()
    )

    seen, combined = set(), []
    for entry in matched + recent:
        if entry.id not in seen:
            seen.add(entry.id)
            combined.append(entry)
    return combined[:8]


@router.post("/api/chat", dependencies=[Depends(rate_limit("chat", 20, 300))])
def chat_with_diary(payload: ChatRequest, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    user_messages = [m for m in payload.messages if m.role == "user"]
    if not user_messages:
        return {"reply": "Ask me anything about your journal — past moods, patterns, or what you wrote about a topic.", "sources": []}
    question = user_messages[-1].content.strip()[:2000]

    # 1. Long-term semantic memories (empty string if Qdrant is unavailable)
    memory_context = search_memories(user_id=user_id, query=question, limit=8)

    # 2. Grounding excerpts from actual entries
    entries = _retrieve_entries(question, user_id, db)
    excerpts, sources = [], []
    for entry in entries:
        date_str = entry.date.strftime("%B %d, %Y")
        text = _strip_html(entry.content)[:700]
        mood = f" (mood {entry.feedback.mood_score}/10)" if entry.feedback and entry.feedback.mood_score else ""
        excerpts.append(f"[{date_str}{mood}]\n{text}")
        sources.append({
            "id": entry.id,
            "date": entry.date.strftime("%Y-%m-%d"),
            "displayDate": date_str,
            "snippet": text[:160].strip() + "…",
        })

    today = datetime.utcnow().strftime("%B %d, %Y")
    system_prompt = (
        "You are the reflective companion inside this user's private journal. "
        f"Today is {today}. Answer their question using ONLY the diary excerpts and "
        "long-term memories provided below. Always mention the date(s) an insight came from. "
        "Be warm, concise, and honest — if the journal doesn't contain the answer, say so "
        "plainly rather than inventing anything. When you notice patterns across dates, name them.\n\n"
    )
    if memory_context:
        system_prompt += memory_context + "\n\n"
    if excerpts:
        system_prompt += "## Journal excerpts:\n\n" + "\n\n---\n\n".join(excerpts)
    else:
        system_prompt += "## Journal excerpts:\n\n(No matching entries found.)"

    # Cap the rolling window so long conversations don't balloon token spend
    history = [{"role": m.role, "content": m.content} for m in payload.messages[-10:]]

    response = client.chat.completions.create(
        model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": system_prompt}] + history,
        temperature=0.4,
        max_tokens=700,
    )

    return {
        "reply": response.choices[0].message.content,
        "sources": sources,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        },
    }
