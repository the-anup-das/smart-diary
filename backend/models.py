from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String)
    preferences = Column(JSON, default={})
    
    entries = relationship("JournalEntry", back_populates="user", cascade="all, delete-orphan")

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('ix_journal_entries_user_is_deleted_date', 'user_id', 'is_deleted', 'date'),
    )
    
    user = relationship("User", back_populates="entries")
    feedback = relationship("FeedbackReport", back_populates="entry", uselist=False, cascade="all, delete-orphan")

class FeedbackReport(Base):
    __tablename__ = "feedback_reports"
    id = Column(String, primary_key=True, default=generate_uuid)
    journal_entry_id = Column(String, ForeignKey("journal_entries.id", ondelete="CASCADE"), unique=True, nullable=False)
    mood_score = Column(Integer)
    sentiment = Column(String)
    grammar_score = Column(Integer)
    grammar_fixes = Column(JSON)
    open_loops = Column(JSON)
    cognitive_reframes = Column(JSON)
    content_hash = Column(String, nullable=True)
    topics = Column(JSON, nullable=True)
    word_count = Column(Integer, nullable=True)
    unique_word_count = Column(Integer, nullable=True)
    new_words = Column(JSON, nullable=True)
    
    # Writing Style Insights
    self_focus_score = Column(Integer, nullable=True) # 1-10 (1=World focused, 10=Self focused)
    self_focus_feedback = Column(Text, nullable=True)
    repetitive_wording = Column(JSON, nullable=True) # {"words": ["word1", "word2"], "feedback": "..."}
    detected_decision = Column(String, nullable=True) # Topic of a decision detected in the entry
    emotion_labels = Column(JSON, nullable=True) # 1-3 precise emotion words
    distress_flag = Column(Boolean, default=False) # acute-crisis signal -> support card

    # Find Your Energy
    energy_data = Column(JSON, nullable=True)

    # Focus Reset: reward-seeking / overstimulation signals extracted from the entry
    stimulation_data = Column(JSON, nullable=True)
    
    # Token Usage
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    entry = relationship("JournalEntry", back_populates="feedback")

class OpenLoop(Base):
    __tablename__ = "open_loops"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    text_hash = Column(String, nullable=False, index=True)
    status = Column(String, default="open", index=True)  # open, resolved, dismissed, pinned
    source_entry_id = Column(String, ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    user = relationship("User")

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic = Column(String, nullable=False)
    status = Column(String, default="active") # active, awaiting_outcome, archived
    framework = Column(String, nullable=True) # matrix, 10_10_10, etc.
    factors = Column(JSON, nullable=True) # User defined factors
    options = Column(JSON, nullable=True) # The paths/options
    primary_option_id = Column(String, nullable=True)
    expected_outcome = Column(Text, nullable=True)
    actual_outcome = Column(Text, nullable=True)
    review_date = Column(DateTime, nullable=True)
    analysis_result = Column(JSON, nullable=True)  # Persisted agent output
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User")

class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=True)
    messages = Column(JSON, nullable=True)  # [{role, content, sources?}]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

class AIFeedback(Base):
    __tablename__ = "ai_feedback"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)  # reflection | chat | weekly_review
    ref_id = Column(String, nullable=True)  # entry id / conversation id / week key
    vote = Column(Integer, nullable=False)  # 1 = helpful, -1 = not helpful
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class CalmSession(Base):
    """One run of the 3-Minute Reset (see routers/calm.py).

    A session is created when the user starts the practice, either from the
    overthinking card shown after an entry is analysed ("entry") or from the
    Energy page ("manual"). Progress is patched in as the user moves through
    the three one-minute steps so an abandoned tab still leaves a record.
    """
    __tablename__ = "calm_sessions"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_id = Column(String, ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    source = Column(String, default="manual")           # "entry" | "manual"
    rumination_level = Column(String, nullable=True)    # snapshot of energy_data.rumination_level at start
    rumination_type = Column(String, nullable=True)     # past_regret | future_worry | social_comparison | self_judgment | information_overload | mixed
    loop_thought = Column(Text, nullable=True)          # the thought the writer keeps circling, paraphrased by the planner
    plan = Column(JSON, nullable=True)                  # generated minute-three script (visualisation, affirmations, ...)
    personalized = Column(Boolean, default=False)       # False when the generic script was used
    source_hash = Column(String, nullable=True)         # content_hash of the entry the plan was built from (lets us reuse it)
    mind_before = Column(Integer, nullable=True)        # 1 (still) .. 5 (racing), asked before the practice
    mind_after = Column(Integer, nullable=True)         # same scale, asked after
    steps_completed = Column(Integer, default=0)        # 0..3: breathing, stillness, visualisation
    duration_seconds = Column(Integer, default=0)
    note = Column(Text, nullable=True)                  # optional one-line reflection written after the practice
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")

class FocusPlan(Base):
    """A Focus Reset programme (see routers/focus.py): one behaviour, one abstinence window, self-binding rules."""
    __tablename__ = "focus_plans"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    behaviour = Column(String, nullable=False)
    category = Column(String, nullable=True)
    objectives = Column(Text, nullable=True)     # what the behaviour does for the person
    problems = Column(Text, nullable=True)       # what it costs them
    abstinence_days = Column(Integer, default=7)
    start_date = Column(String, nullable=False)  # YYYY-MM-DD in the person's local time
    status = Column(String, default="active")    # active | completed | abandoned
    rules = Column(JSON, nullable=True)          # self-binding rules, list of strings
    replacements = Column(JSON, nullable=True)   # replacement activities, list of strings
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")

class FocusUrge(Base):
    """One logged urge, surfed or acted on."""
    __tablename__ = "focus_urges"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String, ForeignKey("focus_plans.id", ondelete="SET NULL"), nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow, index=True)
    intensity = Column(Integer, nullable=True)   # 1..5
    acted = Column(Boolean, default=False)
    trigger = Column(String, nullable=True)
    note = Column(Text, nullable=True)

class FocusCheckin(Base):
    """Daily check-in during a plan: urges felt, whether the person gave in, sleep."""
    __tablename__ = "focus_checkins"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String, ForeignKey("focus_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String, nullable=False)        # YYYY-MM-DD local
    urges = Column(Integer, default=0)
    gave_in = Column(Boolean, default=False)
    sleep_ok = Column(Boolean, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
