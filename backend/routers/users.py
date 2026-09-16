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
    energyData: Optional[Any] = None
    stimulationData: Optional[Any] = None
    cognitionData: Optional[Any] = None

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

class CalmSessionImport(BaseModel):
    entry_id: Optional[str] = None
    source: Optional[str] = "manual"
    rumination_level: Optional[str] = None
    rumination_type: Optional[str] = None
    loop_thought: Optional[str] = None
    plan: Optional[Any] = None
    personalized: Optional[bool] = False
    mind_before: Optional[int] = None
    mind_after: Optional[int] = None
    steps_completed: Optional[int] = 0
    duration_seconds: Optional[int] = 0
    note: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

class FocusCheckinImport(BaseModel):
    date: str
    urges: Optional[int] = 0
    gave_in: Optional[bool] = False
    sleep_ok: Optional[bool] = None
    note: Optional[str] = None
    created_at: Optional[str] = None

class FocusPlanImport(BaseModel):
    id: Optional[str] = None
    behaviour: str
    category: Optional[str] = None
    objectives: Optional[str] = None
    problems: Optional[str] = None
    abstinence_days: Optional[int] = 7
    start_date: str
    status: Optional[str] = "active"
    rules: Optional[Any] = None
    replacements: Optional[Any] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    checkins: Optional[List[FocusCheckinImport]] = None

class FocusUrgeImport(BaseModel):
    plan_id: Optional[str] = None
    logged_at: Optional[str] = None
    intensity: Optional[int] = None
    acted: Optional[bool] = False
    trigger: Optional[str] = None
    note: Optional[str] = None

class MindLogImport(BaseModel):
    date: str
    builder: str
    source: Optional[str] = "manual"
    created_at: Optional[str] = None

class ImportPayload(BaseModel):
    entries: List[EntryImport]
    openLoops: List[OpenLoopImport]
    calmSessions: Optional[List[CalmSessionImport]] = None
    focusPlans: Optional[List[FocusPlanImport]] = None
    focusUrges: Optional[List[FocusUrgeImport]] = None
    mindLogs: Optional[List[MindLogImport]] = None
    preferences: Optional[Dict[str, Any]] = None

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
        "preferences": dict(user.preferences or {}),
        "entries": [],
        "openLoops": [],
        "calmSessions": [],
        "focusPlans": [],
        "focusUrges": [],
        "mindLogs": [],
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
                "openLoops": fb.open_loops,
                "energyData": fb.energy_data,
                "stimulationData": fb.stimulation_data,
                "cognitionData": fb.cognition_data,
            }
        export_payload["entries"].append(entry_data)
        
    for loop in loops:
        export_payload["openLoops"].append({
            "id": loop.id,
            "text": loop.text,
            "status": loop.status,
            "detected_at": loop.detected_at.isoformat() if loop.detected_at else None
        })
        
    calm_sessions = db.query(models.CalmSession).filter(models.CalmSession.user_id == user_id).all()
    for s in calm_sessions:
        export_payload["calmSessions"].append({
            "entry_id": s.entry_id,
            "source": s.source,
            "rumination_level": s.rumination_level,
            "rumination_type": s.rumination_type,
            "loop_thought": s.loop_thought,
            "plan": s.plan,
            "personalized": bool(s.personalized),
            "mind_before": s.mind_before,
            "mind_after": s.mind_after,
            "steps_completed": s.steps_completed,
            "duration_seconds": s.duration_seconds,
            "note": s.note,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        })

    def _iso(ts):
        return ts.isoformat() if ts else None

    checkins_by_plan: Dict[str, list] = {}
    for c in db.query(models.FocusCheckin).filter(models.FocusCheckin.user_id == user_id).order_by(models.FocusCheckin.date).all():
        checkins_by_plan.setdefault(c.plan_id, []).append({
            "date": c.date, "urges": c.urges, "gave_in": bool(c.gave_in), "sleep_ok": c.sleep_ok, "note": c.note, "created_at": _iso(c.created_at),
        })
    for p in db.query(models.FocusPlan).filter(models.FocusPlan.user_id == user_id).order_by(models.FocusPlan.created_at).all():
        export_payload["focusPlans"].append({
            "id": p.id, "behaviour": p.behaviour, "category": p.category, "objectives": p.objectives, "problems": p.problems,
            "abstinence_days": p.abstinence_days, "start_date": p.start_date, "status": p.status, "rules": p.rules or [],
            "replacements": p.replacements or [], "created_at": _iso(p.created_at), "completed_at": _iso(p.completed_at),
            "checkins": checkins_by_plan.get(p.id, []),
        })
    for u in db.query(models.FocusUrge).filter(models.FocusUrge.user_id == user_id).order_by(models.FocusUrge.logged_at).all():
        export_payload["focusUrges"].append({
            "plan_id": u.plan_id, "logged_at": _iso(u.logged_at), "intensity": u.intensity, "acted": bool(u.acted), "trigger": u.trigger, "note": u.note,
        })
    for m in db.query(models.MindLog).filter(models.MindLog.user_id == user_id).order_by(models.MindLog.date).all():
        export_payload["mindLogs"].append({"date": m.date, "builder": m.builder, "source": m.source or "manual", "created_at": _iso(m.created_at)})

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
                open_loops=fb.openLoops,
                energy_data=fb.energyData,
                stimulation_data=fb.stimulationData,
                cognition_data=fb.cognitionData,
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

    def _parse(ts):
        try:
            return datetime.fromisoformat(ts) if ts else None
        except Exception:
            return None

    for s in (payload.calmSessions or []):
        db.add(models.CalmSession(
            user_id=user_id,
            entry_id=entry_id_map.get(s.entry_id) if s.entry_id else None,
            source=s.source or "manual",
            rumination_level=s.rumination_level,
            rumination_type=s.rumination_type,
            loop_thought=s.loop_thought,
            plan=s.plan,
            personalized=bool(s.personalized),
            mind_before=s.mind_before,
            mind_after=s.mind_after,
            steps_completed=s.steps_completed or 0,
            duration_seconds=s.duration_seconds or 0,
            note=s.note,
            started_at=_parse(s.started_at) or datetime.utcnow(),
            completed_at=_parse(s.completed_at),
        ))

    # Focus plans keep their check-ins. Only one plan may be active; any further active one is recorded as abandoned.
    has_active = db.query(models.FocusPlan).filter(models.FocusPlan.user_id == user_id, models.FocusPlan.status == "active").first() is not None
    plan_id_map: Dict[str, str] = {}
    for p in (payload.focusPlans or []):
        status_value = p.status or "active"
        if status_value == "active":
            if has_active:
                status_value = "abandoned"
            has_active = True
        new_plan = models.FocusPlan(
            user_id=user_id, behaviour=p.behaviour, category=p.category, objectives=p.objectives, problems=p.problems,
            abstinence_days=p.abstinence_days or 7, start_date=p.start_date, status=status_value,
            rules=p.rules or [], replacements=p.replacements or [],
            created_at=_parse(p.created_at) or datetime.utcnow(), completed_at=_parse(p.completed_at),
        )
        db.add(new_plan)
        db.flush()
        if p.id:
            plan_id_map[p.id] = new_plan.id
        for c in (p.checkins or []):
            db.add(models.FocusCheckin(
                user_id=user_id, plan_id=new_plan.id, date=c.date, urges=c.urges or 0, gave_in=bool(c.gave_in),
                sleep_ok=c.sleep_ok, note=c.note, created_at=_parse(c.created_at) or datetime.utcnow(),
            ))
    for u in (payload.focusUrges or []):
        db.add(models.FocusUrge(
            user_id=user_id, plan_id=plan_id_map.get(u.plan_id) if u.plan_id else None,
            logged_at=_parse(u.logged_at) or datetime.utcnow(), intensity=u.intensity, acted=bool(u.acted), trigger=u.trigger, note=u.note,
        ))

    existing_logs = {(m.date, m.builder, m.source or "manual") for m in db.query(models.MindLog).filter(models.MindLog.user_id == user_id).all()}
    mind_logs_imported = 0
    for m in (payload.mindLogs or []):
        key = (m.date, m.builder, m.source or "manual")
        if key in existing_logs:
            continue
        existing_logs.add(key)
        db.add(models.MindLog(user_id=user_id, date=m.date, builder=m.builder, source=m.source or "manual", created_at=_parse(m.created_at) or datetime.utcnow()))
        mind_logs_imported += 1

    # Preferences from the backup fill in what this account has not set; nothing already chosen is overwritten.
    if payload.preferences:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            merged = dict(payload.preferences)
            merged.update(user.preferences or {})
            user.preferences = merged

    db.commit()
    return {
        "success": True,
        "entries_imported": len(payload.entries),
        "loops_imported": len(payload.openLoops),
        "calm_sessions_imported": len(payload.calmSessions or []),
        "focus_plans_imported": len(payload.focusPlans or []),
        "focus_urges_imported": len(payload.focusUrges or []),
        "mind_logs_imported": mind_logs_imported,
    }

class MoodCheckin(BaseModel):
    mood: int  # 1-10, how the user feels *before* writing

@router.post("/api/users/checkin")
def mood_checkin(payload: MoodCheckin, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    """Record arrival mood for today — compared against the post-writing AI
    mood score to show whether journaling actually lifts the writer."""
    if not 1 <= payload.mood <= 10:
        raise HTTPException(status_code=422, detail="mood must be between 1 and 10")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from datetime import datetime
    prefs = dict(user.preferences or {})
    moods = dict(prefs.get("arrival_moods", {}))
    moods[datetime.utcnow().strftime("%Y-%m-%d")] = payload.mood
    # Keep only the most recent 30 days
    prefs["arrival_moods"] = dict(sorted(moods.items())[-30:])
    user.preferences = prefs
    db.commit()
    return {"success": True}
