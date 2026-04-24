from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field
from database import get_db
import models
from .auth import verify_session
import openai
import os
import re
import hashlib

router = APIRouter()

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", None)
)

class GrammarFix(BaseModel):
    original: str
    correction: str
    explanation: str

class CognitiveReframe(BaseModel):
    negativeThought: str
    reframe: str

class TopicWeight(BaseModel):
    topic: str = Field(description="Lowercase topic name (e.g. 'work', 'health', 'family', 'relationships', 'personal_growth', 'finances', 'creativity').")
    weight: float = Field(description="Percentage weight as a float (0.0 to 1.0). All weights should sum to 1.0.")

class FeedbackReportSchema(BaseModel):
    moodScore: int = Field(ge=1, le=10, description="Score the emotional state from 1 (Despair) to 10 (Euphoric).")
    sentiment: str = Field(description="A single word describing the core sentiment (Stressed, Joyful, Neutral, Anxious, Focused, Calm, etc).")
    grammarScore: int = Field(ge=1, le=10, description="Score the English grammar quality.")
    grammarFixes: list[GrammarFix] = Field(description="List of corrections. Empty array if perfect.")
    openLoops: list[str] = Field(description="List of actionable tasks, worries, or unresolved issues from the text.")
    cognitiveReframes: list[CognitiveReframe] = Field(description="CBT positive reframes for negative thoughts.")
    topics: list[TopicWeight] = Field(description="Percentage breakdown of the entry's primary focus areas. List of topic/weight pairs summing to 1.0.")
    selfFocusScore: int = Field(ge=1, le=10, description="Score from 1 (Focused on others/environment) to 10 (Extremely self-focused/I-centric).")
    selfFocusFeedback: str = Field(description="Brief, gentle psychological insight about their focus balance.")
    repetitiveWords: list[str] = Field(description="List of words or short phrases overused in this entry (3-5 items).")
    repetitiveWordingFeedback: str = Field(description="Brief coaching tip on how to vary their vocabulary.")

def _tokenize(text: str) -> set[str]:
    """Extract lowercase alphabetic words from text."""
    return set(re.findall(r'[a-zA-Z]{2,}', text.lower()))

def _compute_vocab_stats(user_id: str, current_text: str, current_entry_id: str, db: Session):
    """Compute vocabulary metrics by diffing current entry against all prior entries."""
    current_words = _tokenize(current_text)
    
    # Fetch all prior entries for this user (excluding current)
    prior_entries = db.query(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.id != current_entry_id
    ).all()
    
    historical_words = set()
    for entry in prior_entries:
        raw = re.sub(r'<[^>]*>?', '', entry.content or "")
        historical_words |= _tokenize(raw)
    
    new_words = sorted(current_words - historical_words)
    all_vocab = historical_words | current_words
    
    return {
        "word_count": len(re.findall(r'[a-zA-Z]{2,}', current_text)),
        "unique_word_count": len(current_words),
        "new_words": new_words[:50],  # Cap at 50 to avoid huge payloads
        "total_vocabulary": len(all_vocab)
    }

def _build_response(feedback, cached: bool = False):
    """Standard response builder for feedback data."""
    return {
        "success": True,
        "cached": cached,
        "feedback": {
            "id": feedback.id,
            "moodScore": feedback.mood_score,
            "sentiment": feedback.sentiment,
            "grammarScore": feedback.grammar_score,
            "grammarFixes": feedback.grammar_fixes,
            "openLoops": feedback.open_loops,
            "cognitiveReframes": feedback.cognitive_reframes,
            "topics": feedback.topics,
            "wordCount": feedback.word_count,
            "uniqueWordCount": feedback.unique_word_count,
            "newWords": feedback.new_words,
            "selfFocusScore": feedback.self_focus_score,
            "selfFocusFeedback": feedback.self_focus_feedback,
            "repetitiveWording": feedback.repetitive_wording,
        }
    }

@router.post("/api/analyze")
def analyze_entry(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    preferences = user.preferences or {} if user else {}
    
    if preferences.get("pause_ai", False):
        return {"success": True, "paused": True, "feedback": None}
    
    entry = db.query(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.date >= today_start,
        models.JournalEntry.date <= today_end,
        models.JournalEntry.is_deleted == False
    ).first()
    
    raw_text = re.sub(r'<[^>]*>?', '', entry.content) if entry else ""
    
    if not entry or len(raw_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Entry is too short for meaningful analysis. Write a bit more!")
    
    # Compute SHA-256 hash of the stripped text
    content_hash = hashlib.sha256(raw_text.strip().encode('utf-8')).hexdigest()
    
    # Check if we already have a cached analysis for this exact content
    existing_feedback = db.query(models.FeedbackReport).filter(
        models.FeedbackReport.journal_entry_id == entry.id
    ).first()
    
    if existing_feedback and existing_feedback.content_hash == content_hash:
        print(f"Cache HIT: returning stored analysis (hash: {content_hash[:12]}...)", flush=True)
        return _build_response(existing_feedback, cached=True)
    
    print(f"Cache MISS: calling OpenAI (hash: {content_hash[:12]}...)", flush=True)
    
    # Compute vocabulary stats
    vocab_stats = _compute_vocab_stats(user_id, raw_text, entry.id, db)
    
    try:
        system_prompt = (
            "You are an empathetic, clinical AI psychologist and highly advanced grammar/writing coach observing a diary. "
            "Parse their entry directly into the strict JSON parameters requested. "
            "Deploy Cognitive Behavioral Therapy to reframe explicit negative thoughts. "
            "For topics, identify the primary life areas discussed and assign percentage weights summing to 1.0.\n\n"
            "SPECIAL FOCUS (Writing Mirror):\n"
            "1. Self-Focus: Analyze if the user is talking excessively about 'I/me/my' or ruminating inward. "
            "A score of 1 means they are observing the world/others; 10 means they are entirely self-absorbed. "
            "Provide gentle feedback on balancing this focus.\n"
            "2. Repetitive Wording: Identify words or phrases used too frequently. Suggest more descriptive or varied language."
        )
        custom_persona = preferences.get("custom_persona_prompt", "")
        if custom_persona:
            system_prompt += f"\n\nUSER'S CUSTOM INSTRUCTIONS: {custom_persona}"
            
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": raw_text
                }
            ],
            response_format=FeedbackReportSchema,
        )
        
        parsed = response.choices[0].message.parsed
        
        feedback_data = {
            "mood_score": parsed.moodScore,
            "sentiment": parsed.sentiment,
            "grammar_score": parsed.grammarScore,
            "grammar_fixes": [f.model_dump() for f in parsed.grammarFixes],
            "open_loops": parsed.openLoops,
            "cognitive_reframes": [c.model_dump() for c in parsed.cognitiveReframes],
            "content_hash": content_hash,
            "topics": {t.topic: t.weight for t in parsed.topics},
            "word_count": vocab_stats["word_count"],
            "unique_word_count": vocab_stats["unique_word_count"],
            "new_words": vocab_stats["new_words"],
            "self_focus_score": parsed.selfFocusScore,
            "self_focus_feedback": parsed.selfFocusFeedback,
            "repetitive_wording": {
                "words": parsed.repetitiveWords,
                "feedback": parsed.repetitiveWordingFeedback
            }
        }
        
        if existing_feedback:
            for key, value in feedback_data.items():
                setattr(existing_feedback, key, value)
            db.commit()
            db.refresh(existing_feedback)
            feedback = existing_feedback
        else:
            feedback = models.FeedbackReport(
                journal_entry_id=entry.id,
                **feedback_data
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
        
        # Persist open loops as tracked entities (deduplicate by hash)
        for loop_text in parsed.openLoops:
            loop_hash = hashlib.sha256(loop_text.strip().lower().encode('utf-8')).hexdigest()[:16]
            existing_loop = db.query(models.OpenLoop).filter(
                models.OpenLoop.user_id == user_id,
                models.OpenLoop.text_hash == loop_hash,
                models.OpenLoop.status.in_(["open", "pinned"])
            ).first()
            if not existing_loop:
                db.add(models.OpenLoop(
                    user_id=user_id,
                    text=loop_text.strip(),
                    text_hash=loop_hash,
                    source_entry_id=entry.id,
                ))
        db.commit()
        
        return _build_response(feedback)
    except Exception as e:
        print("Analysis Error:", str(e), flush=True)
        raise HTTPException(status_code=500, detail=f"OpenAI Exception: {str(e)}")

class DailyIntentionsSchema(BaseModel):
    intentions: list[str] = Field(description="List of 3 journaling prompts.")

TIME_OF_DAY_CONFIG = {
    "morning": {
        "persona": "You are a serene morning journaling assistant. Generate exactly 3 insightful, energising journaling prompts to help the user set clear intentions and start their day with purpose.",
        "cache_key": "morning",
    },
    "afternoon": {
        "persona": "You are a midday check-in journaling coach. Generate exactly 3 reflective journaling prompts to help the user assess their progress, refocus energy, and stay grounded through the rest of the day.",
        "cache_key": "afternoon",
    },
    "evening": {
        "persona": "You are a calming evening journaling guide. Generate exactly 3 warm, reflective journaling prompts to help the user wind down, appreciate the day's moments, and process their emotions before nightfall.",
        "cache_key": "evening",
    },
    "night": {
        "persona": "You are a gentle night journaling companion. Generate exactly 3 peaceful, introspective journaling prompts to help the user release the day's weight, find gratitude, and ease into restful sleep.",
        "cache_key": "night",
    },
}

@router.get("/api/analyze/intentions")
def get_intentions(
    time_of_day: str = "morning",
    user_id: str = Depends(verify_session),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Normalise and fallback
    tod = time_of_day.lower() if time_of_day.lower() in TIME_OF_DAY_CONFIG else "morning"
    config = TIME_OF_DAY_CONFIG[tod]

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    prefs = user.preferences or {}

    # Cache key is per-slot-per-day e.g. "daily_intentions_evening"
    cache_field = f"daily_intentions_{config['cache_key']}"
    cached = prefs.get(cache_field, {})
    if cached.get("date") == date_str and "prompts" in cached:
        return {"intentions": cached["prompts"], "cached": True, "time_of_day": tod}

    # Fetch Open Loops for personalisation
    open_loops_objects = (
        db.query(models.OpenLoop)
        .filter(models.OpenLoop.user_id == user_id, models.OpenLoop.status.in_(["open", "pinned"]))
        .order_by(models.OpenLoop.status.desc(), models.OpenLoop.detected_at.asc())
        .limit(3)
        .all()
    )
    loop_texts = [l.text for l in open_loops_objects]

    system_instruction = config["persona"]
    if loop_texts:
        system_instruction += f" Where relevant, weave in these unresolved thoughts/tasks the user has been carrying: {', '.join(loop_texts)}."

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_instruction}],
            response_format=DailyIntentionsSchema,
            temperature=0.7
        )
        prompts = response.choices[0].message.parsed.intentions

        new_prefs = dict(prefs)
        new_prefs[cache_field] = {"date": date_str, "prompts": prompts}
        user.preferences = new_prefs
        db.commit()

        return {"intentions": prompts, "cached": False, "time_of_day": tod}
    except Exception as e:
        print("Intentions generation failed:", e)
        fallbacks = {
            "morning": [
                "What intention do I want to set for today?",
                "What am I looking forward to most this morning?",
                "What would make today feel meaningful?",
            ],
            "afternoon": [
                "How has my energy shifted since this morning?",
                "What's one thing I can let go of to refocus?",
                "What small win can I celebrate from the first half of today?",
            ],
            "evening": [
                "What moments from today am I grateful for?",
                "How did I show up for myself or others today?",
                "What do I want to feel before I sleep tonight?",
            ],
            "night": [
                "What thought do I want to release before I sleep?",
                "What is one thing that went well today, however small?",
                "What gentle intention do I want to carry into tomorrow?",
            ],
        }
        return {"intentions": fallbacks[tod], "cached": False, "time_of_day": tod, "error": str(e)}
