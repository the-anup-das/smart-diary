from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from database import get_db
import models
from .auth import verify_session

router = APIRouter()

class EntryUpdate(BaseModel):
    content: str

@router.get("/api/entries/today")
def get_today_entry(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    entry = db.query(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.date >= today_start,
        models.JournalEntry.date <= today_end,
        models.JournalEntry.is_deleted == False
    ).first()
    
    if not entry:
        return {"content": ""}
    return {"content": entry.content}

@router.post("/api/entries")
def upsert_entry(data: EntryUpdate, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    entry = db.query(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.date >= today_start,
        models.JournalEntry.date <= today_end,
        models.JournalEntry.is_deleted == False
    ).first()
    
    if entry:
        entry.content = data.content
        entry.updated_at = datetime.utcnow()
        db.commit()
    else:
        new_entry = models.JournalEntry(user_id=user_id, content=data.content)
        db.add(new_entry)
        db.commit()
        entry = new_entry
        
    return {"success": True, "id": entry.id}

@router.get("/api/entries/history")
def get_entry_history(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    """Return all entries with feedback summaries for the history timeline."""
    import re
    entries = (
        db.query(models.JournalEntry)
        .filter(models.JournalEntry.user_id == user_id, models.JournalEntry.is_deleted == False)
        .order_by(models.JournalEntry.date.desc())
        .all()
    )
    
    result = []
    for entry in entries:
        # Strip HTML for preview
        raw = re.sub(r'<[^>]*>?', '', entry.content or "")
        preview = raw[:200].strip()
        word_count = len(re.findall(r'[a-zA-Z]{2,}', raw))
        
        fb = entry.feedback
        result.append({
            "id": entry.id,
            "date": entry.date.strftime("%Y-%m-%d"),
            "preview": preview,
            "wordCount": word_count,
            "content": entry.content,
            "feedback": {
                "moodScore": fb.mood_score,
                "sentiment": fb.sentiment,
                "grammarScore": fb.grammar_score,
                "topics": fb.topics,
                "openLoops": fb.open_loops,
                "grammarFixes": fb.grammar_fixes,
                "cognitiveReframes": fb.cognitive_reframes,
            } if fb else None,
        })
    
    return {"entries": result}

@router.get("/api/entries/context")
def get_entry_context(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    """Fetch lightweight context for the layout (e.g. latest mood score for theming)."""
    # Find the most recent entry that has a feedback score
    latest_with_feedback = (
        db.query(models.JournalEntry)
        .filter(models.JournalEntry.user_id == user_id, models.JournalEntry.is_deleted == False)
        .join(models.FeedbackReport)
        .filter(models.FeedbackReport.mood_score.isnot(None))
        .order_by(models.JournalEntry.date.desc())
        .first()
    )
    
    mood_score = 7 # Default to "Good/Green" if no history
    if latest_with_feedback and latest_with_feedback.feedback:
        mood_score = latest_with_feedback.feedback.mood_score
        
    return {"latest_mood": mood_score}

from datetime import timedelta

@router.get("/api/entries/echoes")
def get_entry_echoes(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    """Finds an older entry that shares a similar mood/topic with recent entries."""
    recent_limit = datetime.utcnow() - timedelta(days=3)
    recent_entries = (
        db.query(models.JournalEntry)
        .filter(models.JournalEntry.user_id == user_id, models.JournalEntry.date >= recent_limit, models.JournalEntry.is_deleted == False)
        .join(models.FeedbackReport)
        .all()
    )
    
    if not recent_entries:
        return {"echo": None}

    recent_sentiments = [e.feedback.sentiment for e in recent_entries if e.feedback and e.feedback.sentiment]
    if not recent_sentiments:
        return {"echo": None}
        
    dominant_sentiment = max(set(recent_sentiments), key=recent_sentiments.count)
    
    echo_threshold = datetime.utcnow() - timedelta(days=7)
    echo_entry = (
        db.query(models.JournalEntry)
        .filter(
            models.JournalEntry.user_id == user_id,
            models.JournalEntry.date < echo_threshold,
            models.JournalEntry.is_deleted == False
        )
        .join(models.FeedbackReport)
        .filter(models.FeedbackReport.sentiment == dominant_sentiment)
        .order_by(models.JournalEntry.date.desc())
        .first()
    )
    
    if not echo_entry:
        return {"echo": None}
        
    import re
    preview = re.sub(r'<[^>]*>?', '', echo_entry.content or "")[:300].strip() + "..."
        
    return {
        "echo": {
            "id": echo_entry.id,
            "date": echo_entry.date.strftime("%B %d, %Y"),
            "content": preview,
            "sentiment": dominant_sentiment,
            "similarity_reason": f"You also felt '{dominant_sentiment}' on this day."
        }
    }

@router.delete("/api/entries/{id}")
def soft_delete_entry(id: str, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    entry = db.query(models.JournalEntry).filter(models.JournalEntry.id == id, models.JournalEntry.user_id == user_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    entry.is_deleted = True
    entry.deleted_at = datetime.utcnow()
    db.commit()
    return {"success": True}
