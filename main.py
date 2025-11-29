from fastapi import FastAPI, Depends, HTTPException, WebSocket, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import random
import uuid
from datetime import datetime
import io

from database import get_db, init_db, TTSModel, Session as DBSession, Vote, SearchModel, SearchSession, SearchVote
from tts_service import TTSService
from search_service import SearchService
from elo import calculate_elo
from openai import OpenAI
import os

app = FastAPI(title="Voice Arena")
tts_service = TTSService()
search_service = SearchService()  # Using updated Parallel v1beta API
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

    # Save ELO ratings before updating
    model_a_elo_before = model_a.elo_rating
    model_b_elo_before = model_b.elo_rating

    if request.winner == "A":
        winner, loser = model_a, model_b
    elif request.winner == "B":
        winner, loser = model_b, model_a
    else:
        raise HTTPException(status_code=400, detail="Invalid winner selection")

    new_winner_elo, new_loser_elo = calculate_elo(winner.elo_rating, loser.elo_rating)

    winner.elo_rating = new_winner_elo
    winner.wins += 1
    winner.total_votes += 1

    loser.elo_rating = new_loser_elo
    loser.losses += 1
    loser.total_votes += 1

    vote_record = Vote(
        session_id=db_session.id,
        winner_model_id=winner.id,
        loser_model_id=loser.id,
        vote_type=request.winner,
        model_a_id=model_a.id,
        model_b_id=model_b.id,
        model_a_elo_before=model_a_elo_before,
        model_b_elo_before=model_b_elo_before,
        model_a_elo_after=model_a.elo_rating,
        model_b_elo_after=model_b.elo_rating,
        prompt_number=conv["prompt_count"]
    )
    db.add(vote_record)
    db.commit()
    
    return {
        "message": "Vote recorded",
        "winner_elo": new_winner_elo,
        "loser_elo": new_loser_elo,
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

# Search Arena Endpoints

@app.post("/api/search/start-session")
async def start_search_session(db: Session = Depends(get_db)):
    models = db.query(SearchModel).all()
    if len(models) < 2:
        raise HTTPException(status_code=500, detail="Not enough Search models available")
    
    selected_models = random.sample(models, 2)
    session_id = str(uuid.uuid4())
    
    db_session = SearchSession(
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
        "type": "search"
    }
    
    return {
        "session_id": session_id,
        "message": "Search Session started! Ask me anything."
    }

@app.post("/api/search/chat")
async def search_chat(request: ChatRequest, db: Session = Depends(get_db)):
    if request.session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")

    conv = conversation_store[request.session_id]
    if conv.get("type") != "search":
        raise HTTPException(status_code=400, detail="Invalid session type")

    conv["messages"].append({"role": "user", "content": request.message})

    # Save query to database session
    db_session = db.query(SearchSession).filter(SearchSession.session_id == request.session_id).first()
    if db_session:
        db_session.query = request.message
        db.commit()

    # Generate responses from both search providers
    try:
        response_a = await search_service.generate_search_response(request.message, conv["model_a_provider"])
        response_b = await search_service.generate_search_response(request.message, conv["model_b_provider"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    conv["prompt_count"] += 1

    # Format responses with citations for frontend
    formatted_response_a = response_a['answer']
    if response_a.get('citations'):
        formatted_response_a += "\n\n**Sources:**\n"
        for idx, citation in enumerate(response_a['citations'], 1):
            formatted_response_a += f"{idx}. [{citation['title']}]({citation['url']})\n"

    formatted_response_b = response_b['answer']
    if response_b.get('citations'):
        formatted_response_b += "\n\n**Sources:**\n"
        for idx, citation in enumerate(response_b['citations'], 1):
            formatted_response_b += f"{idx}. [{citation['title']}]({citation['url']})\n"

    return {
        "response_a": formatted_response_a,
        "response_b": formatted_response_b,
        "model_a": conv["model_a"],
        "model_b": conv["model_b"],
        "prompt_count": conv["prompt_count"],
        "should_vote": True
    }

@app.post("/api/search/vote")
async def search_vote(request: VoteRequest, db: Session = Depends(get_db)):
    if request.session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    conv = conversation_store[request.session_id]
    
    db_session = db.query(SearchSession).filter(SearchSession.session_id == request.session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found in database")
    
    model_a = db.query(SearchModel).filter(SearchModel.id == db_session.model_a_id).first()
    model_b = db.query(SearchModel).filter(SearchModel.id == db_session.model_b_id).first()

    # Save ELO ratings before updating
    model_a_elo_before = model_a.elo_rating
    model_b_elo_before = model_b.elo_rating

    if request.winner == "A":
        winner, loser = model_a, model_b
    elif request.winner == "B":
        winner, loser = model_b, model_a
    elif request.winner == "tie": # potential future feature
         pass
    else:
        raise HTTPException(status_code=400, detail="Invalid winner selection")

    new_winner_elo, new_loser_elo = calculate_elo(winner.elo_rating, loser.elo_rating)

    winner.elo_rating = new_winner_elo
    winner.wins += 1
    winner.total_votes += 1

    loser.elo_rating = new_loser_elo
    loser.losses += 1
    loser.total_votes += 1

    # Get the last user query from messages
    query = conv["messages"][-1]["content"] if conv.get("messages") else db_session.query

    vote_record = SearchVote(
        session_id=db_session.id,
        winner_model_id=winner.id,
        loser_model_id=loser.id,
        vote_type=request.winner,
        model_a_id=model_a.id,
        model_b_id=model_b.id,
        model_a_elo_before=model_a_elo_before,
        model_b_elo_before=model_b_elo_before,
        model_a_elo_after=model_a.elo_rating,
        model_b_elo_after=model_b.elo_rating,
        query=query
    )
    db.add(vote_record)
    db.commit()
    
    return {
        "message": "Vote recorded",
        "winner_elo": new_winner_elo,
        "loser_elo": new_loser_elo,
        "model_a_name": conv["model_a"],
        "model_a_provider": conv["model_a_provider"],
        "model_b_name": conv["model_b"],
        "model_b_provider": conv["model_b_provider"]
    }

@app.get("/api/search/leaderboard")
async def get_search_leaderboard(db: Session = Depends(get_db)):
    models = db.query(SearchModel).order_by(SearchModel.elo_rating.desc()).all()
    
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

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

# Vercel serverless handler
handler = app
