from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from database import get_db
import models
from .auth import verify_session
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

router = APIRouter()

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class FeedbackImport(BaseModel):
    moodScore: Optional[int] = None
    sentiment: Optional[str] = None
    topics: Optional[Any] = None
    cognitiveReframes: Optional[Any] = None
    grammarFixes: Optional[Any] = None
    openLoops: Optional[Any] = None

class EntryImport(BaseModel):
    id: str
    date: Optional[str] = None
    content: str
    feedback: Optional[FeedbackImport] = None

class OpenLoopImport(BaseModel):
    id: str
    text: str
    status: str
    detected_at: Optional[str] = None

class ImportPayload(BaseModel):
    entries: List[EntryImport]
    openLoops: List[OpenLoopImport]

@router.get("/api/users/me")
def get_me(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "preferences": user.preferences or {}
    }

@router.put("/api/users/me")
def update_me(data: UserUpdate, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.name is not None:
        user.name = data.name
    if data.email is not None:
        if data.email != user.email:
            existing = db.query(models.User).filter(models.User.email == data.email).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email
    if data.preferences is not None:
        user.preferences = data.preferences
    
    db.commit()
    db.refresh(user)
    return {"success": True}

@router.delete("/api/users/me")
def delete_me(response: Response, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    response.delete_cookie("session")
    return {"success": True}

@router.get("/api/users/export")
def export_data(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    entries = db.query(models.JournalEntry).filter(models.JournalEntry.user_id == user_id).all()
    loops = db.query(models.OpenLoop).filter(models.OpenLoop.user_id == user_id).all()
    
    export_payload = {
        "profile": {
            "name": user.name,
            "email": user.email,
        },
        "entries": [],
        "openLoops": []
    }
    
    for entry in entries:
        fb = entry.feedback
        entry_data = {
            "id": entry.id,
            "date": entry.date.isoformat() if entry.date else None,
            "content": entry.content,
            "feedback": None
        }
        if fb:
            entry_data["feedback"] = {
                "moodScore": fb.mood_score,
                "sentiment": fb.sentiment,
                "topics": fb.topics,
                "cognitiveReframes": fb.cognitive_reframes,
                "grammarFixes": fb.grammar_fixes,
                "openLoops": fb.open_loops
            }
        export_payload["entries"].append(entry_data)
        
    for loop in loops:
        export_payload["openLoops"].append({
            "id": loop.id,
            "text": loop.text,
            "status": loop.status,
            "detected_at": loop.detected_at.isoformat() if loop.detected_at else None
        })
        
    return export_payload

@router.post("/api/users/import")
def import_data(payload: ImportPayload, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    # Map old IDs to new objects to maintain relations
    entry_id_map = {}
    
    from datetime import datetime

    for entry_data in payload.entries:
        # Check if entry already exists (by content and date roughly, or skip for now)
        # For simplicity, we just create new ones.
        
        try:
            entry_date = datetime.fromisoformat(entry_data.date) if entry_data.date else datetime.utcnow()
        except Exception:
            entry_date = datetime.utcnow()
            
        new_entry = models.JournalEntry(
            user_id=user_id,
            content=entry_data.content,
            date=entry_date
        )
        db.add(new_entry)
        db.flush() # Get the new ID
        
        entry_id_map[entry_data.id] = new_entry.id
        
        if entry_data.feedback:
            fb = entry_data.feedback
            new_fb = models.FeedbackReport(
                journal_entry_id=new_entry.id,
                mood_score=fb.moodScore,
                sentiment=fb.sentiment,
                topics=fb.topics,
                cognitive_reframes=fb.cognitiveReframes,
                grammar_fixes=fb.grammarFixes,
                open_loops=fb.openLoops
            )
            db.add(new_fb)

    for loop_data in payload.openLoops:
        try:
            detected_at = datetime.fromisoformat(loop_data.detected_at) if loop_data.detected_at else datetime.utcnow()
        except Exception:
            detected_at = datetime.utcnow()
            
        import hashlib
        text_hash = hashlib.sha256(loop_data.text.encode()).hexdigest()
        
        new_loop = models.OpenLoop(
            user_id=user_id,
            text=loop_data.text,
            text_hash=text_hash,
            status=loop_data.status,
            detected_at=detected_at
        )
        db.add(new_loop)

    db.commit()
    return {"success": True, "entries_imported": len(payload.entries), "loops_imported": len(payload.openLoops)}
