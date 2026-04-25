from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from pydantic import BaseModel
from database import get_db
import models
from .auth import verify_session
import re

router = APIRouter()

def _get_date_range(range_str: str):
    """Compute start date based on the range filter."""
    now = datetime.utcnow()
    if range_str == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_str == "week":
        return now - timedelta(days=7)
    elif range_str == "month":
        return now - timedelta(days=30)
    elif range_str == "year":
        return now - timedelta(days=365)
    else:  # "all"
        return datetime(2000, 1, 1)

def _get_previous_range(range_str: str):
    """Compute start/end date for the PREVIOUS period (for trend comparison)."""
    now = datetime.utcnow()
    if range_str == "day":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_str == "week":
        start = now - timedelta(days=14)
        end = now - timedelta(days=7)
    elif range_str == "month":
        start = now - timedelta(days=60)
        end = now - timedelta(days=30)
    elif range_str == "year":
        start = now - timedelta(days=730)
        end = now - timedelta(days=365)
    else:
        return None, None
    return start, end

@router.get("/api/insights")
def get_insights(
    range: str = Query(default="week", pattern="^(day|week|month|year|all)$"),
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db)
):
    start_date = _get_date_range(range)
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    prefs = user.preferences or {} if user else {}
    targets = prefs.get("targets", {
        "daily_words": 200,
        "target_mood": 7,
        "weekly_vocab": 10,
        "consistency_streak": 5,
        "weekly_loops": 3,
        "weekly_reframes": 3,
        "sentiment_diversity": 3
    })
    
    # Fetch all entries with feedback in the date range
    entries = (
        db.query(models.JournalEntry)
        .filter(
            models.JournalEntry.user_id == user_id,
            models.JournalEntry.date >= start_date,
            models.JournalEntry.is_deleted == False
        )
        .order_by(models.JournalEntry.date.asc())
        .all()
    )
    
    # Build timeline data
    timeline = []
    sentiments = {}
    topic_totals = {}
    total_mood = 0
    total_grammar = 0
    analyzed_count = 0
    total_reframes = 0
    all_new_words = []
    total_self_focus = 0
    writing_style_highlights = []
    
    for entry in entries:
        fb = entry.feedback
        if not fb:
            continue
        
        analyzed_count += 1
        total_mood += (fb.mood_score or 0)
        total_grammar += (fb.grammar_score or 0)
        
        if fb.cognitive_reframes:
            total_reframes += len(fb.cognitive_reframes)
        
        # Sentiment distribution
        sent = fb.sentiment or "Unknown"
        sentiments[sent] = sentiments.get(sent, 0) + 1
        
        # Topic aggregation
        if fb.topics:
            for topic, weight in fb.topics.items():
                topic_totals[topic] = topic_totals.get(topic, 0) + weight
        
        # Collect new words
        if fb.new_words:
            all_new_words.extend(fb.new_words)
            
        # Writing Style
        if fb.self_focus_score is not None:
            total_self_focus += fb.self_focus_score
        
        if fb.repetitive_wording and fb.repetitive_wording.get("words"):
            writing_style_highlights.append({
                "date": entry.date.strftime("%Y-%m-%d"),
                "words": fb.repetitive_wording["words"],
                "feedback": fb.repetitive_wording.get("feedback", ""),
                "self_focus_feedback": fb.self_focus_feedback
            })
        
        timeline.append({
            "date": entry.date.strftime("%Y-%m-%d"),
            "moodScore": fb.mood_score,
            "grammarScore": fb.grammar_score,
            "sentiment": fb.sentiment,
            "wordCount": fb.word_count or 0,
            "uniqueWordCount": fb.unique_word_count or 0,
            "newWordCount": len(fb.new_words) if fb.new_words else 0,
        })
    
    # Normalize topic aggregation to percentages
    topic_total_sum = sum(topic_totals.values()) or 1
    topic_aggregation = {k: round(v / topic_total_sum, 3) for k, v in sorted(topic_totals.items(), key=lambda x: -x[1])}
    
    # Compute streak (consecutive days with entries, counting backwards from today)
    streak = 0
    all_user_entries = db.query(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.is_deleted == False
    ).all()
    if all_user_entries:
        check_date = datetime.utcnow().date()
        entry_dates = set(e.date.date() for e in all_user_entries)
        while check_date in entry_dates:
            streak += 1
            check_date -= timedelta(days=1)
    
    # Total vocabulary across ALL entries
    all_words = set()
    for entry in all_user_entries:
        raw = re.sub(r'<[^>]*>?', '', entry.content or "")
        all_words |= set(re.findall(r'[a-zA-Z]{2,}', raw.lower()))
    
    # --- Mood trend vs. previous period ---
    mood_trend = None
    prev_start, prev_end = _get_previous_range(range)
    if prev_start and prev_end and analyzed_count > 0:
        prev_entries = (
            db.query(models.JournalEntry)
            .filter(
                models.JournalEntry.user_id == user_id,
                models.JournalEntry.date >= prev_start,
                models.JournalEntry.date < prev_end
            )
            .all()
        )
        prev_mood_total = 0
        prev_count = 0
        for pe in prev_entries:
            if pe.feedback and pe.feedback.mood_score:
                prev_mood_total += pe.feedback.mood_score
                prev_count += 1
        if prev_count > 0:
            prev_avg = prev_mood_total / prev_count
            curr_avg = total_mood / analyzed_count
            mood_trend = round(curr_avg - prev_avg, 1)
    
    # --- Top new words (unique, most recent first, capped at 10) ---
    seen = set()
    top_new_words = []
    for w in reversed(all_new_words):
        wl = w.lower()
        if wl not in seen and len(wl) > 3:  # skip tiny words
            seen.add(wl)
            top_new_words.append(w)
            if len(top_new_words) >= 10:
                break
    
    # --- Open loops (tracked entities) ---
    open_loops = (
        db.query(models.OpenLoop)
        .filter(
            models.OpenLoop.user_id == user_id,
            models.OpenLoop.status.in_(["open", "pinned"])
        )
        .order_by(
            # pinned first, then oldest first
            models.OpenLoop.status.desc(),
            models.OpenLoop.detected_at.asc()
        )
        .limit(15)
        .all()
    )
    
    now = datetime.utcnow()
    open_loops_data = []
    for loop in open_loops:
        age_days = (now - loop.detected_at).days
        if age_days >= 7:
            urgency = "urgent"
        elif age_days >= 3:
            urgency = "aging"
        else:
            urgency = "fresh"
        open_loops_data.append({
            "id": loop.id,
            "text": loop.text,
            "status": loop.status,
            "urgency": urgency,
            "ageDays": age_days,
            "detectedAt": loop.detected_at.strftime("%Y-%m-%d"),
        })
    
    # Count totals
    total_open = db.query(models.OpenLoop).filter(
        models.OpenLoop.user_id == user_id,
        models.OpenLoop.status.in_(["open", "pinned"])
    ).count()
    total_resolved = db.query(models.OpenLoop).filter(
        models.OpenLoop.user_id == user_id,
        models.OpenLoop.status.in_(["resolved", "dismissed"])
    ).count()
    
    top_sentiment = max(sentiments, key=sentiments.get) if sentiments else "—"
    
    return {
        "summary": {
            "totalEntries": len(entries),
            "analyzedEntries": analyzed_count,
            "avgMood": round(total_mood / analyzed_count, 1) if analyzed_count else 0,
            "avgGrammar": round(total_grammar / analyzed_count, 1) if analyzed_count else 0,
            "moodTrend": mood_trend,
            "totalVocabulary": len(all_words),
            "topSentiment": top_sentiment,
            "currentStreak": streak,
        },
        "timeline": timeline,
        "topicAggregation": topic_aggregation,
        "sentimentDistribution": sentiments,
        "topNewWords": top_new_words,
        "openLoops": {
            "items": open_loops_data,
            "totalOpen": total_open,
            "totalResolved": total_resolved,
        },
        "targets": {
            "daily_words": { "current": sum(e["wordCount"] for e in timeline if e["date"] == datetime.utcnow().strftime("%Y-%m-%d")), "target": targets["daily_words"] },
            "target_mood": { "current": round(total_mood / analyzed_count, 1) if analyzed_count else 0, "target": targets["target_mood"] },
            "weekly_vocab": { "current": len(set(all_new_words)), "target": targets["weekly_vocab"] },
            "consistency_streak": { "current": streak, "target": targets["consistency_streak"] },
            "weekly_loops": { "current": total_resolved, "target": targets["weekly_loops"] },
            "weekly_reframes": { "current": total_reframes, "target": targets["weekly_reframes"] },
            "sentiment_diversity": { "current": len([s for s in sentiments if s != "—" and s != "Neutral"]), "target": targets["sentiment_diversity"] },
        },
        "writingStyle": {
            "avgSelfFocus": round(total_self_focus / analyzed_count, 1) if analyzed_count else 0,
            "highlights": writing_style_highlights[-5:] # Latest 5 highlights
        }
    }


# --- Open Loop Actions ---
class LoopAction(BaseModel):
    action: str  # "resolve", "dismiss", "pin", "reopen"

@router.get("/api/open-loops")
def get_open_loops(
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db)
):
    open_loops = (
        db.query(models.OpenLoop)
        .filter(
            models.OpenLoop.user_id == user_id,
            models.OpenLoop.status.in_(["open", "pinned"])
        )
        .order_by(
            models.OpenLoop.status.desc(),
            models.OpenLoop.detected_at.asc()
        )
        .limit(5)
        .all()
    )
    return {"items": [{"id": loop.id, "text": loop.text, "status": loop.status} for loop in open_loops]}


@router.patch("/api/open-loops/{loop_id}")
def update_open_loop(
    loop_id: str,
    data: LoopAction,
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db)
):
    loop = db.query(models.OpenLoop).filter(
        models.OpenLoop.id == loop_id,
        models.OpenLoop.user_id == user_id
    ).first()
    if not loop:
        raise HTTPException(status_code=404, detail="Loop not found")
    
    if data.action == "resolve":
        loop.status = "resolved"
        loop.resolved_at = datetime.utcnow()
    elif data.action == "dismiss":
        loop.status = "dismissed"
        loop.resolved_at = datetime.utcnow()
    elif data.action == "pin":
        loop.status = "pinned"
        loop.resolved_at = None
    elif data.action == "reopen":
        loop.status = "open"
        loop.resolved_at = None
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    db.commit()
    return {"success": True, "id": loop.id, "status": loop.status}
