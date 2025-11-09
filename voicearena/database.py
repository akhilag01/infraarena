from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voice_arena.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TTSModel(Base):
    __tablename__ = "tts_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    provider = Column(String)
    elo_rating = Column(Float, default=1500.0)
    total_votes = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    model_a_id = Column(Integer, ForeignKey("tts_models.id"))
    model_b_id = Column(Integer, ForeignKey("tts_models.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    votes = relationship("Vote", back_populates="session")

class Vote(Base):
    __tablename__ = "votes"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    winner_model_id = Column(Integer, ForeignKey("tts_models.id"))
    loser_model_id = Column(Integer, ForeignKey("tts_models.id"))
    prompt_number = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session", back_populates="votes")

def init_db():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        models = [
            TTSModel(name="eleven_v3", provider="ElevenLabs"),
            TTSModel(name="eleven_multilingual_v2", provider="ElevenLabs"),
            TTSModel(name="tts-1", provider="OpenAI"),
            TTSModel(name="aura-2-thalia-en", provider="Deepgram"),
            TTSModel(name="sonic-3", provider="Cartesia"),
        ]
        
        for model in models:
            existing = db.query(TTSModel).filter(TTSModel.name == model.name).first()
            if not existing:
                db.add(model)
        
        db.commit()
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
