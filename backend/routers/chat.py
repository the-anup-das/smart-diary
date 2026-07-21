"""Chat with your diary — RAG over journal entries + mem0 long-term memories.

Retrieval is two-pronged:
  1. mem0/Qdrant semantic memories (durable life facts extracted at ingest time)
  2. Keyword-matched + recent journal entries straight from Postgres

Responses stream token-by-token. The wire format is one JSON meta line
(`{"conversation_id", "sources"}`) followed by raw text deltas; the frontend
splits on the first newline. Conversations persist per user in
chat_conversations and can be resumed, listed, and deleted.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
from database import get_db
from rate_limit import rate_limit
import models
from .auth import verify_session
from memory_service import search_memories
import openai
import json
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

MAX_HISTORY_MESSAGES = 10


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None


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


def _get_conversation(db: Session, user_id: str, conversation_id: str) -> models.ChatConversation:
    convo = db.query(models.ChatConversation).filter(
        models.ChatConversation.id == conversation_id,
        models.ChatConversation.user_id == user_id,
    ).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.get("/api/chat/conversations")
def list_conversations(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    convos = (
        db.query(models.ChatConversation)
        .filter(models.ChatConversation.user_id == user_id)
        .order_by(models.ChatConversation.updated_at.desc())
        .limit(50)
        .all()
    )
    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title or "Untitled",
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "message_count": len(c.messages or []),
            }
            for c in convos
        ]
    }


@router.get("/api/chat/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    convo = _get_conversation(db, user_id, conversation_id)
    return {"id": convo.id, "title": convo.title, "messages": convo.messages or []}


@router.delete("/api/chat/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    convo = _get_conversation(db, user_id, conversation_id)
    db.delete(convo)
    db.commit()
    return {"success": True}


@router.post("/api/chat", dependencies=[Depends(rate_limit("chat", 20, 300))])
def chat_with_diary(payload: ChatRequest, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    question = payload.question.strip()[:2000]
    if not question:
        raise HTTPException(status_code=422, detail="Ask a question about your journal.")

    if payload.conversation_id:
        convo = _get_conversation(db, user_id, payload.conversation_id)
    else:
        convo = models.ChatConversation(
            user_id=user_id,
            title=question[:80],
            messages=[],
        )
        db.add(convo)
        db.commit()
        db.refresh(convo)

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

    # Rolling window over persisted history keeps token spend bounded
    prior = [
        {"role": m["role"], "content": m["content"]}
        for m in (convo.messages or [])[-(MAX_HISTORY_MESSAGES - 1):]
    ]
    llm_messages = (
        [{"role": "system", "content": system_prompt}]
        + prior
        + [{"role": "user", "content": question}]
    )

    def token_stream():
        reply_parts = []
        yield json.dumps({"conversation_id": convo.id, "sources": sources}) + "\n"
        try:
            stream = client.chat.completions.create(
                model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
                messages=llm_messages,
                temperature=0.4,
                max_tokens=700,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    reply_parts.append(delta)
                    yield delta
        except Exception as e:
            error_text = "\n\n(The journal couldn't finish answering — please try again.)"
            print(f"[chat] stream failed: {e}")
            reply_parts.append(error_text)
            yield error_text
        finally:
            # Persist the exchange once the stream ends (also on partial failure)
            convo.messages = (convo.messages or []) + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": "".join(reply_parts), "sources": sources},
            ]
            convo.updated_at = datetime.utcnow()
            db.commit()

    return StreamingResponse(token_stream(), media_type="text/plain; charset=utf-8")
