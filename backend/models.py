from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
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
    
    entries = relationship("JournalEntry", back_populates="user", cascade="all, delete-orphan")

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
    
    entry = relationship("JournalEntry", back_populates="feedback")

class OpenLoop(Base):
    __tablename__ = "open_loops"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String, nullable=False, index=True)
    status = Column(String, default="open")  # open, resolved, dismissed, pinned
    source_entry_id = Column(String, ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    user = relationship("User")
