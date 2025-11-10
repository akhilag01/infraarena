import sys
import os
from pathlib import Path

# Add voicearena directory to path
voicearena_path = Path(__file__).parent.parent / 'voicearena'
sys.path.insert(0, str(voicearena_path))

# Set working directory for static files
try:
    os.chdir(str(voicearena_path))
except Exception as e:
    print(f"Warning: Could not change directory: {e}")

try:
    from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import Optional
    import random
    import uuid
    import io
    
    from tts_service import TTSService
    from elo import calculate_elo, calculate_elo_tie, calculate_elo_both_bad
    from supabase_client import get_supabase, get_user_from_token
    from openai import OpenAI
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise

# Initialize app
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

# In-memory storage (Note: This will reset on each cold start in serverless)
conversation_store = {}
models_cache = None

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

def get_models():
    """Get TTS models from Supabase instead of SQLite"""
    global models_cache
    if models_cache is None:
        supabase = get_supabase()
        response = supabase.table('tts_models').select('*').execute()
        models_cache = response.data
    return models_cache

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/start-session")
async def start_session():
    supabase = get_supabase()
    models = get_models()
    if len(models) < 2:
        raise HTTPException(status_code=500, detail="Not enough TTS models available")
    
    selected_models = random.sample(models, 2)
    session_id = str(uuid.uuid4())
    
    # Store in Supabase
    supabase.table('sessions').insert({
        'session_id': session_id,
        'model_a_id': selected_models[0]['id'],
        'model_b_id': selected_models[1]['id']
    }).execute()
    
    conversation_store[session_id] = {
        "messages": [],
        "model_a": selected_models[0]['name'],
        "model_b": selected_models[1]['name'],
        "model_a_provider": selected_models[0]['provider'],
        "model_b_provider": selected_models[1]['provider'],
        "model_a_id": selected_models[0]['id'],
        "model_b_id": selected_models[1]['id'],
        "prompt_count": 0
    }
    
    return {
        "session_id": session_id,
        "message": "Session started! Ask me anything."
    }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if request.session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    conv = conversation_store[request.session_id]
    
    models = get_models()
    if len(models) < 2:
        raise HTTPException(status_code=500, detail="Not enough TTS models available")
    
    selected_models = random.sample(models, 2)
    
    conv["model_a"] = selected_models[0]['name']
    conv["model_b"] = selected_models[1]['name']
    conv["model_a_provider"] = selected_models[0]['provider']
    conv["model_b_provider"] = selected_models[1]['provider']
    conv["model_a_id"] = selected_models[0]['id']
    conv["model_b_id"] = selected_models[1]['id']
    
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
async def vote(request: VoteRequest):
    supabase = get_supabase()
    if request.session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    conv = conversation_store[request.session_id]
    
    # Get current ELO ratings from Supabase
    model_a_data = supabase.table('tts_models').select('*').eq('id', conv["model_a_id"]).single().execute()
    model_b_data = supabase.table('tts_models').select('*').eq('id', conv["model_b_id"]).single().execute()
    
    model_a = model_a_data.data
    model_b = model_b_data.data
    
    if request.winner == "A":
        new_a_elo, new_b_elo = calculate_elo(model_a['elo_rating'], model_b['elo_rating'])
        winner_id, loser_id = model_a['id'], model_b['id']
        supabase.table('tts_models').update({'wins': model_a['wins'] + 1}).eq('id', model_a['id']).execute()
        supabase.table('tts_models').update({'losses': model_b['losses'] + 1}).eq('id', model_b['id']).execute()
    elif request.winner == "B":
        new_b_elo, new_a_elo = calculate_elo(model_b['elo_rating'], model_a['elo_rating'])
        winner_id, loser_id = model_b['id'], model_a['id']
        supabase.table('tts_models').update({'wins': model_b['wins'] + 1}).eq('id', model_b['id']).execute()
        supabase.table('tts_models').update({'losses': model_a['losses'] + 1}).eq('id', model_a['id']).execute()
    elif request.winner == "tie":
        new_a_elo, new_b_elo = calculate_elo_tie(model_a['elo_rating'], model_b['elo_rating'])
        winner_id, loser_id = None, None
    elif request.winner == "both_bad":
        new_a_elo, new_b_elo = calculate_elo_both_bad(model_a['elo_rating'], model_b['elo_rating'])
        winner_id, loser_id = None, None
        supabase.table('tts_models').update({'losses': model_a['losses'] + 1}).eq('id', model_a['id']).execute()
        supabase.table('tts_models').update({'losses': model_b['losses'] + 1}).eq('id', model_b['id']).execute()
    else:
        raise HTTPException(status_code=400, detail="Invalid winner selection")
    
    # Update ELO ratings
    supabase.table('tts_models').update({
        'elo_rating': new_a_elo,
        'total_votes': model_a['total_votes'] + 1
    }).eq('id', model_a['id']).execute()
    
    supabase.table('tts_models').update({
        'elo_rating': new_b_elo,
        'total_votes': model_b['total_votes'] + 1
    }).eq('id', model_b['id']).execute()
    
    # Store vote
    session_data = supabase.table('sessions').select('id').eq('session_id', request.session_id).single().execute()
    supabase.table('votes').insert({
        'session_id': session_data.data['id'],
        'winner_model_id': winner_id,
        'loser_model_id': loser_id,
        'vote_type': request.winner,
        'model_a_id': model_a['id'],
        'model_b_id': model_b['id'],
        'model_a_elo_before': model_a['elo_rating'],
        'model_b_elo_before': model_b['elo_rating'],
        'model_a_elo_after': new_a_elo,
        'model_b_elo_after': new_b_elo,
        'prompt_number': conv["prompt_count"]
    }).execute()
    
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
async def get_leaderboard():
    supabase = get_supabase()
    response = supabase.table('tts_models').select('*').order('elo_rating', desc=True).execute()
    models = response.data
    
    return [
        {
            "name": model['name'],
            "provider": model['provider'],
            "elo": round(model['elo_rating'], 2),
            "wins": model['wins'],
            "losses": model['losses'],
            "total_votes": model['total_votes']
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

# Auth endpoints
@app.post("/api/auth/signup")
async def signup(auth_request: AuthRequest):
    supabase = get_supabase()
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
    supabase = get_supabase()
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
    supabase = get_supabase()
    try:
        response = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://infrafield.app"
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
    supabase = get_supabase()
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="No authorization header")
        
        token = authorization.replace("Bearer ", "")
        supabase.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Serve static files
@app.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    file_location = Path(voicearena_path) / file_path
    if file_location.exists():
        return FileResponse(file_location)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/")
async def read_root():
    index_path = Path(voicearena_path) / "index.html"
    return FileResponse(index_path)

# Export for Vercel using Mangum
from mangum import Mangum
handler = Mangum(app, lifespan="off")
