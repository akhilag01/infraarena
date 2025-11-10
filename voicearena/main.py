from fastapi import FastAPI, Depends, HTTPException, WebSocket, UploadFile, File, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import random
import uuid
from datetime import datetime
import io

from database import get_db, init_db, TTSModel, Session as DBSession, Vote
from tts_service import TTSService
from elo import calculate_elo, calculate_elo_tie, calculate_elo_both_bad
from supabase_client import supabase, get_user_from_token
from openai import OpenAI
import os

app = FastAPI(title="Voice Arena")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tts_service = TTSService()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

conversation_store = {}

class StartSessionRequest(BaseModel):
    pass

class ChatRequest(BaseModel):
    session_id: str
    message: str

class VoteRequest(BaseModel):
    session_id: str
    winner: str

class AuthRequest(BaseModel):
    email: str
    password: str

class AuthTokenRequest(BaseModel):
    token: str

class GoogleAuthRequest(BaseModel):
    id_token: str

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/start-session")
async def start_session(db: Session = Depends(get_db)):
    models = db.query(TTSModel).all()
    if len(models) < 2:
        raise HTTPException(status_code=500, detail="Not enough TTS models available")
    
    selected_models = random.sample(models, 2)
    session_id = str(uuid.uuid4())
    
    db_session = DBSession(
        session_id=session_id,
        model_a_id=selected_models[0].id,
        model_b_id=selected_models[1].id
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    conversation_store[session_id] = {
        "messages": [],
        "model_a": selected_models[0].name,
        "model_b": selected_models[1].name,
        "model_a_provider": selected_models[0].provider,
        "model_b_provider": selected_models[1].provider,
        "prompt_count": 0,
        "current_speaker": "A"
    }
    
    return {
        "session_id": session_id,
        "message": "Session started! Ask me anything."
    }

@app.post("/api/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    if request.session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    conv = conversation_store[request.session_id]
    conv["messages"].append({"role": "user", "content": request.message})
    
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=conv["messages"]
    )
    
    assistant_message = response.choices[0].message.content
    conv["messages"].append({"role": "assistant", "content": assistant_message})
    
    audio_a = await tts_service.generate_speech(assistant_message, conv["model_a"])
    audio_b = await tts_service.generate_speech(assistant_message, conv["model_b"])
    
    conv["prompt_count"] += 1
    
    return {
        "text": assistant_message,
        "audio_a": audio_a.hex(),
        "audio_b": audio_b.hex(),
        "prompt_count": conv["prompt_count"],
        "should_vote": True
    }

@app.post("/api/vote")
async def vote(request: VoteRequest, db: Session = Depends(get_db)):
    if request.session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    conv = conversation_store[request.session_id]
    
    db_session = db.query(DBSession).filter(DBSession.session_id == request.session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found in database")
    
    model_a = db.query(TTSModel).filter(TTSModel.id == db_session.model_a_id).first()
    model_b = db.query(TTSModel).filter(TTSModel.id == db_session.model_b_id).first()
    
    if request.winner == "A":
        new_a_elo, new_b_elo = calculate_elo(model_a.elo_rating, model_b.elo_rating)
        model_a.wins += 1
        model_b.losses += 1
        winner_id, loser_id = model_a.id, model_b.id
    elif request.winner == "B":
        new_b_elo, new_a_elo = calculate_elo(model_b.elo_rating, model_a.elo_rating)
        model_b.wins += 1
        model_a.losses += 1
        winner_id, loser_id = model_b.id, model_a.id
    elif request.winner == "tie":
        new_a_elo, new_b_elo = calculate_elo_tie(model_a.elo_rating, model_b.elo_rating)
        winner_id, loser_id = None, None
    elif request.winner == "both_bad":
        new_a_elo, new_b_elo = calculate_elo_both_bad(model_a.elo_rating, model_b.elo_rating)
        model_a.losses += 1
        model_b.losses += 1
        winner_id, loser_id = None, None
    else:
        raise HTTPException(status_code=400, detail="Invalid winner selection")
    
    model_a.elo_rating = new_a_elo
    model_b.elo_rating = new_b_elo
    model_a.total_votes += 1
    model_b.total_votes += 1
    
    vote_record = Vote(
        session_id=db_session.id,
        winner_model_id=winner_id,
        loser_model_id=loser_id,
        prompt_number=conv["prompt_count"]
    )
    db.add(vote_record)
    db.commit()
    
    return {
        "message": "Vote recorded",
        "winner_elo": new_a_elo,
        "loser_elo": new_b_elo,
        "model_a_name": conv["model_a"],
        "model_a_provider": conv["model_a_provider"],
        "model_b_name": conv["model_b"],
        "model_b_provider": conv["model_b_provider"]
    }

@app.get("/api/leaderboard")
async def get_leaderboard(db: Session = Depends(get_db)):
    models = db.query(TTSModel).order_by(TTSModel.elo_rating.desc()).all()
    
    return [
        {
            "name": model.name,
            "provider": model.provider,
            "elo": round(model.elo_rating, 2),
            "wins": model.wins,
            "losses": model.losses,
            "total_votes": model.total_votes
        }
        for model in models
    ]

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        audio_data = await file.read()
        
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.webm"
        
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        
        return {"text": transcript.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def read_root():
    return FileResponse("index.html")

# Helper function to get current user from Authorization header
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        return None
    
    try:
        token = authorization.replace("Bearer ", "")
        user = get_user_from_token(token)
        return user
    except Exception as e:
        print(f"Error getting current user: {e}")
        return None

# Authentication endpoints
@app.post("/api/auth/signup")
async def signup(auth_request: AuthRequest):
    try:
        response = supabase.auth.sign_up({
            "email": auth_request.email,
            "password": auth_request.password
        })
        return {
            "user": response.user,
            "session": response.session
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
async def login(auth_request: AuthRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": auth_request.email,
            "password": auth_request.password
        })
        return {
            "user": response.user,
            "session": response.session,
            "access_token": response.session.access_token
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/auth/google")
async def google_auth():
    try:
        response = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "http://localhost:8000"
            }
        })
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/verify")
async def verify_token(token_request: AuthTokenRequest):
    try:
        user = get_user_from_token(token_request.token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user": user}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None)):
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="No authorization header")
        
        token = authorization.replace("Bearer ", "")
        supabase.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
