from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

# Use Supabase PostgreSQL database
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TTSModel(Base):
    __tablename__ = "tts_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    provider = Column(String, nullable=False)
    elo_rating = Column(Float, default=1500.0)
    total_votes = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    clone_elo_rating = Column(Float, default=1200.0)
    clone_wins = Column(Integer, default=0)
    clone_losses = Column(Integer, default=0)
    clone_total_votes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    model_a_id = Column(UUID(as_uuid=True), ForeignKey("tts_models.id"), nullable=False)
    model_b_id = Column(UUID(as_uuid=True), ForeignKey("tts_models.id"), nullable=False)
    prompt_count = Column(Integer, default=0)
    title = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Vote(Base):
    __tablename__ = "votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    winner_model_id = Column(UUID(as_uuid=True), ForeignKey("tts_models.id"), nullable=True)
    loser_model_id = Column(UUID(as_uuid=True), ForeignKey("tts_models.id"), nullable=True)
    vote_type = Column(String, nullable=False)
    model_a_id = Column(UUID(as_uuid=True), ForeignKey("tts_models.id"), nullable=False)
    model_b_id = Column(UUID(as_uuid=True), ForeignKey("tts_models.id"), nullable=False)
    model_a_elo_before = Column(Float, nullable=False)
    model_b_elo_before = Column(Float, nullable=False)
    model_a_elo_after = Column(Float, nullable=False)
    model_b_elo_after = Column(Float, nullable=False)
    prompt_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class SearchModel(Base):
    __tablename__ = "search_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    provider = Column(String, nullable=False)
    elo_rating = Column(Float, default=1500.0)
    total_votes = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    model_a_id = Column(UUID(as_uuid=True), ForeignKey("search_models.id"), nullable=False)
    model_b_id = Column(UUID(as_uuid=True), ForeignKey("search_models.id"), nullable=False)
    query = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class SearchVote(Base):
    __tablename__ = "search_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("search_sessions.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    winner_model_id = Column(UUID(as_uuid=True), ForeignKey("search_models.id"), nullable=True)
    loser_model_id = Column(UUID(as_uuid=True), ForeignKey("search_models.id"), nullable=True)
    vote_type = Column(String, nullable=False)
    model_a_id = Column(UUID(as_uuid=True), ForeignKey("search_models.id"), nullable=False)
    model_b_id = Column(UUID(as_uuid=True), ForeignKey("search_models.id"), nullable=False)
    model_a_elo_before = Column(Float, nullable=False)
    model_b_elo_before = Column(Float, nullable=False)
    model_a_elo_after = Column(Float, nullable=False)
    model_b_elo_after = Column(Float, nullable=False)
    query = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

def init_db():
    # Tables already exist in Supabase - no need to create
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
