import os
import random
import uuid
import io
import httpx
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from elevenlabs import ElevenLabs
from supabase import create_client, Client

# Initialize clients lazily
_supabase_client = None
_openai_client = None
_elevenlabs_client = None
_tts_service = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not set")
        _supabase_client = create_client(supabase_url, supabase_key)
    return _supabase_client

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client

# ELO calculation functions
def calculate_elo(winner_rating: float, loser_rating: float, k_factor: int = 32):
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))
    new_winner_rating = winner_rating + k_factor * (1 - expected_winner)
    new_loser_rating = loser_rating + k_factor * (0 - expected_loser)
    return new_winner_rating, new_loser_rating

def calculate_elo_tie(rating_a: float, rating_b: float, k_factor: int = 32):
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    new_rating_a = rating_a + k_factor * (0.5 - expected_a)
    new_rating_b = rating_b + k_factor * (0.5 - expected_b)
    return new_rating_a, new_rating_b

def calculate_elo_both_bad(rating_a: float, rating_b: float, k_factor: int = 32):
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    new_rating_a = rating_a + k_factor * (0 - expected_a)
    new_rating_b = rating_b + k_factor * (0 - expected_b)
    return new_rating_a, new_rating_b

# TTS Service
class TTSService:
    def __init__(self):
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        self.cartesia_api_key = os.getenv("CARTESIA_API_KEY")
    
    async def generate_speech(self, text: str, model_name: str) -> bytes:
        if model_name == "tts-1":
            return await self._openai_tts(text)
        elif model_name in ["eleven_v3", "eleven_multilingual_v2"]:
            return await self._elevenlabs_tts(text, model_name)
        elif model_name == "aura-2-thalia-en":
            return await self._deepgram_tts(text)
        elif model_name == "sonic-3":
            return await self._cartesia_tts(text)
        else:
            raise ValueError(f"Unknown model: {model_name}")
    
    async def _openai_tts(self, text: str) -> bytes:
        client = get_openai_client()
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            speed=1.0
        )
        return response.content
    
    async def _elevenlabs_tts(self, text: str, model: str) -> bytes:
        global _elevenlabs_client
        if _elevenlabs_client is None:
            _elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        
        audio_generator = _elevenlabs_client.text_to_speech.convert(
            text=text,
            voice_id="EXAVITQu4vr4xnSDxMaL",
            model_id="eleven_turbo_v2_5" if model == "eleven_v3" else model,
            voice_settings={
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        )
        
        audio_bytes = b""
        for chunk in audio_generator:
            audio_bytes += chunk
        return audio_bytes
    
    async def _deepgram_tts(self, text: str) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepgram.com/v1/speak?model=aura-asteria-en",
                headers={
                    "Authorization": f"Token {self.deepgram_api_key}",
                    "Content-Type": "application/json"
                },
                json={"text": text}
            )
            return response.content
    
    async def _cartesia_tts(self, text: str) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.cartesia.ai/tts/bytes",
                headers={
                    "X-API-Key": self.cartesia_api_key,
                    "Cartesia-Version": "2024-06-10"
                },
                json={
                    "model_id": "sonic-english",
                    "transcript": text,
                    "voice": {
                        "mode": "id",
                        "id": "156fb8d2-335b-4950-9cb3-a2d33befec77"
                    },
                    "output_format": {
                        "container": "mp3",
                        "encoding": "mp3",
                        "sample_rate": 44100
                    },
                    "language": "en"
                }
            )
            return response.content

# Initialize app
app = FastAPI(title="Voice Arena")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
conversation_store = {}
models_cache = None

# Request models
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

def get_models():
    global models_cache
    if models_cache is None:
        supabase = get_supabase()
        response = supabase.table('tts_models').select('*').execute()
        models_cache = response.data
    return models_cache

def get_tts_service():
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service

@app.get("/")
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
    
    openai_client = get_openai_client()
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=conv["messages"]
    )
    
    assistant_message = response.choices[0].message.content
    conv["messages"].append({"role": "assistant", "content": assistant_message})
    
    tts_service = get_tts_service()
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
    
    supabase.table('tts_models').update({
        'elo_rating': new_a_elo,
        'total_votes': model_a['total_votes'] + 1
    }).eq('id', model_a['id']).execute()
    
    supabase.table('tts_models').update({
        'elo_rating': new_b_elo,
        'total_votes': model_b['total_votes'] + 1
    }).eq('id', model_b['id']).execute()
    
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
        
        openai_client = get_openai_client()
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        
        return {"text": transcript.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    supabase = get_supabase()
    try:
        user = supabase.auth.get_user(token_request.token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user": user.user}
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
