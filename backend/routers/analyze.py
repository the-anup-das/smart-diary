from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
from pydantic import BaseModel, Field
from database import get_db
import models
from .auth import verify_session
import openai
import os
import re
import hashlib
import threading
from memory_service import ingest_diary_entry

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

class EnergyMicroAction(BaseModel):
    id: str = Field(description="A unique UUID string for this action.")
    text: str = Field(description="A short, actionable micro-action to recharge energy.")

class EnergyItem(BaseModel):
    item: str
    reframe: str = Field(description="A short, one-sentence empowering reframe or tip for this specific item.")

class EnergyAnalysisSchema(BaseModel):
    chargers: list[str] = Field(description="Things that recharged the user's energy in this entry (e.g., sleep, exercise, positive events).")
    drainers: list[str] = Field(description="Things that drained the user's energy in this entry (e.g., poor diet, arguments, stress).")
    controllables: list[EnergyItem] = Field(description="Factors in the entry that are within the user's control.")
    uncontrollables: list[EnergyItem] = Field(description="Factors in the entry that are outside the user's control.")
    ruminationLevel: str = Field(description="'low', 'moderate', or 'high'")
    ruminationCoaching: str = Field(description="One gentle coaching line about their overthinking.")
    microActions: list[EnergyMicroAction] = Field(description="Exactly 3 actionable micro-actions personalized to their dominant topics and drainers.")
    tomorrowFocus: str = Field(description="A 1-2 sentence strategy to build or protect energy for the next day, based on today's drainers.")

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
    detectedDecision: str | None = Field(default=None, description="If the user is struggling with a specific decision (e.g., 'Should I quit my job?'), summarize the topic here. Otherwise null.")
    energyAnalysis: EnergyAnalysisSchema = Field(description="Analysis of the user's energy, control, and actionable steps.")


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

def perform_ai_analysis(text: str, preferences: dict = {}) -> tuple[FeedbackReportSchema, dict]:
    """
    Core AI logic extracted for testing and evaluation.
    Returns (parsed_data, usage_dict)
    """
    system_prompt = (
        "You are an empathetic AI psychologist and writing coach. Parse entries into strict JSON. "
        "Use CBT to reframe negatives. Life areas must sum to 1.0 weight.\n\n"
        "Focus:\n"
        "1. Self-Focus: Score 1 (external) to 10 (self-absorbed). Provide gentle balance feedback.\n"
        "2. Repetitive Wording: Identify overused words. Suggest variety.\n"
        "3. Energy: Extract chargers/drainers. Identify controllables vs uncontrollables. "
        "Provide a 1-sentence reframe/tip for each. Give a rumination coaching line. "
        "Generate 3 topic-tailored micro-actions and a 'tomorrowFocus' strategy."
    )
    custom_persona = preferences.get("custom_persona_prompt", "")
    if custom_persona:
        system_prompt += f"\n\nUSER'S CUSTOM INSTRUCTIONS: {custom_persona}"
        
    response = client.beta.chat.completions.parse(
        model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": text
            }
        ],
        response_format=FeedbackReportSchema,
    )
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens
    }
    return response.choices[0].message.parsed, usage

def _build_response(feedback, cached: bool = False):
    """Standard response builder for feedback data."""
    return {
        "success": True,
        "cached": cached,
        "feedback": {
            "id": feedback.id,
            "moodScore": feedback.mood_score,
            "energyData": feedback.energy_data,
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
            "detectedDecision": feedback.detected_decision,
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
        parsed, usage = perform_ai_analysis(raw_text, preferences)
        print(f"Parsed analysis successfully: {parsed.sentiment} (Tokens: {usage['total_tokens']})", flush=True)
        
        # Process Micro-actions persistence
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        micro_actions_cache_key = f"energy_micro_actions_{date_str}"
        cached_actions_data = preferences.get(micro_actions_cache_key, {})
        
        existing_actions = cached_actions_data.get("actions", [])
        completed_actions = [a for a in existing_actions if a.get("completed")]
        completed_action_ids = {a.get("id") for a in completed_actions}
        
        new_actions = []
        for act in parsed.energyAnalysis.microActions:
            if act.id not in completed_action_ids:
                 new_actions.append({"id": act.id, "text": act.text, "completed": False})
                 
        final_actions = completed_actions + new_actions
        
        # Update preferences with merged actions
        new_prefs = dict(preferences)
        new_prefs[micro_actions_cache_key] = {"actions": final_actions}
        user.preferences = new_prefs
        
        # Battery Formula
        num_chargers = len(parsed.energyAnalysis.chargers)
        num_drainers = len(parsed.energyAnalysis.drainers)
        charger_ratio = num_chargers / (num_chargers + num_drainers) if (num_chargers + num_drainers) > 0 else 0.5
        
        num_controllables = len(parsed.energyAnalysis.controllables)
        num_uncontrollables = len(parsed.energyAnalysis.uncontrollables)
        agency_ratio = num_controllables / (num_controllables + num_uncontrollables) if (num_controllables + num_uncontrollables) > 0 else 0.5
        
        coherence_score = parsed.grammarScore / 10.0
        engagement_bonus = min(vocab_stats["word_count"] / 300.0, 1.0)
        completed_bonus = min(len(completed_actions) * 3, 15)
        
        battery_level = (
            (parsed.moodScore / 10.0) * 35
            + charger_ratio * 20
            + agency_ratio * 15
            + ((10 - parsed.selfFocusScore) / 10.0) * 15
            + coherence_score * 10
            + engagement_bonus * 5
        ) + completed_bonus
        
        # Topic Stress Amplifier
        high_stakes = ["finances", "mental_health", "family", "relationships"]
        if parsed.topics:
            dominant_topic = max(parsed.topics, key=lambda t: t.weight)
            if dominant_topic.topic in high_stakes and parsed.moodScore < 5:
                battery_level *= 0.93
                
        battery_level = max(0, min(100, battery_level))
        
        energy_data = {
            "battery_level": round(battery_level, 1),
            "chargers": parsed.energyAnalysis.chargers,
            "drainers": parsed.energyAnalysis.drainers,
            "controllables": [c.model_dump() for c in parsed.energyAnalysis.controllables],
            "uncontrollables": [u.model_dump() for u in parsed.energyAnalysis.uncontrollables],
            "rumination_level": parsed.energyAnalysis.ruminationLevel,
            "rumination_coaching": parsed.energyAnalysis.ruminationCoaching,
            "micro_actions": final_actions,
            "tomorrow_focus": getattr(parsed.energyAnalysis, 'tomorrowFocus', "Focus on resting and resetting for a fresh start tomorrow.")
        }

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
            },
            "detected_decision": parsed.detectedDecision,
            "energy_data": energy_data,
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "total_tokens": usage["total_tokens"]
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
                    category="general",
                    status="open"
                ))
        db.commit()
        
        # Trigger background memory ingestion
        entry_date_str = str(entry.created_at.date()) if entry.created_at else "unknown"
        threading.Thread(
            target=ingest_diary_entry,
            args=(user_id, raw_text, entry_date_str),
            daemon=True
        ).start()
        
        return _build_response(feedback)
    except Exception as e:
        import traceback
        print("Analysis Error Traceback:", traceback.format_exc(), flush=True)
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

@router.get("/api/energy/today")
def get_energy_today(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    entry = db.query(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.date >= today_start,
        models.JournalEntry.date <= today_end,
        models.JournalEntry.is_deleted == False
    ).first()
    
    if not entry:
        return {"success": False, "detail": "No entry today"}
        
    feedback = db.query(models.FeedbackReport).filter(
        models.FeedbackReport.journal_entry_id == entry.id
    ).first()
    
    if not feedback or not feedback.energy_data:
        return {"success": False, "detail": "No energy data found for today"}
        
    energy_data = dict(feedback.energy_data)
    
    # Sync micro-actions from cache to maintain completion state across reloads
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user and user.preferences:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        cache_key = f"energy_micro_actions_{date_str}"
        if cache_key in user.preferences:
            cached_actions = user.preferences[cache_key].get("actions", [])
            if cached_actions:
                old_completed = sum(1 for a in energy_data.get("micro_actions", []) if a.get("completed", False))
                new_completed = sum(1 for a in cached_actions if a.get("completed", False))
                
                # Update battery level optimistically if actions were completed after analysis
                bonus_diff = (new_completed - old_completed) * 3
                energy_data["micro_actions"] = cached_actions
                energy_data["battery_level"] = min(100, max(0, energy_data.get("battery_level", 0) + bonus_diff))
                
    return {"success": True, "energy_data": energy_data}

@router.patch("/api/energy/actions/{action_id}")
def toggle_micro_action(action_id: str, user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    preferences = user.preferences or {}
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    cache_key = f"energy_micro_actions_{date_str}"
    
    actions_data = preferences.get(cache_key, {})
    actions = actions_data.get("actions", [])
    
    action_found = False
    for action in actions:
        if action.get("id") == action_id:
            action["completed"] = not action.get("completed", False)
            action_found = True
            break
            
    if not action_found:
        raise HTTPException(status_code=404, detail="Action not found or expired")
        
    new_prefs = dict(preferences)
    new_prefs[cache_key] = {"actions": actions}
    user.preferences = new_prefs
    flag_modified(user, "preferences")
    db.commit()
    
    return {"success": True, "actions": actions}

@router.get("/api/energy/domain-history")
def get_domain_history(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    seven_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - __import__('datetime').timedelta(days=7)
    
    reports = db.query(models.FeedbackReport).join(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id,
        models.JournalEntry.date >= seven_days_ago,
        models.JournalEntry.is_deleted == False
    ).all()
    
    domain_agg = {}
    for report in reports:
        if report.topics:
            for topic, weight in report.topics.items():
                domain_agg[topic] = domain_agg.get(topic, 0) + weight
                
    total_weight = sum(domain_agg.values())
    
    history = []
    if total_weight > 0:
        for topic, weight in domain_agg.items():
            history.append({
                "topic": topic.replace("_", " ").title(),
                "percentage": round((weight / total_weight) * 100)
            })
            
    # Sort by highest percentage
    history = sorted(history, key=lambda x: x["percentage"], reverse=True)
    
    return {"success": True, "history": history}

@router.get("/api/user/usage")
def get_user_usage(user_id: str = Depends(verify_session), db: Session = Depends(get_db)):
    # Aggregate all feedback reports for this user
    stats = db.query(
        func.sum(models.FeedbackReport.prompt_tokens).label("prompt"),
        func.sum(models.FeedbackReport.completion_tokens).label("completion"),
        func.sum(models.FeedbackReport.total_tokens).label("total"),
        func.count(models.FeedbackReport.id).label("count")
    ).join(models.JournalEntry).filter(
        models.JournalEntry.user_id == user_id
    ).first()
    
    # Pricing for GPT-4o-mini (as of April 2024)
    # Input: $0.15 / 1M tokens
    # Output: $0.60 / 1M tokens
    input_cost = (stats.prompt or 0) * (0.15 / 1_000_000)
    output_cost = (stats.completion or 0) * (0.60 / 1_000_000)
    total_cost = input_cost + output_cost
    
    return {
        "success": True,
        "usage": {
            "prompt_tokens": stats.prompt or 0,
            "completion_tokens": stats.completion or 0,
            "total_tokens": stats.total or 0,
            "analysis_count": stats.count or 0,
            "estimated_cost_usd": round(total_cost, 4)
        }
    }
