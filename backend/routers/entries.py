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
        models.JournalEntry.date <= today_end
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
        models.JournalEntry.date <= today_end
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
        .filter(models.JournalEntry.user_id == user_id)
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

