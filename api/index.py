import os
import random
import uuid
import io
import httpx
import asyncio
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from elevenlabs import ElevenLabs
from supabase import create_client, Client
from arena.types import TTSModelName

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
        print(f"[TTSService] generate_speech called with model: {model_name}")
        
        # Convert string to enum if necessary
        if isinstance(model_name, str):
            try:
                model_name = TTSModelName(model_name)
                print(f"[TTSService] Converted to enum: {model_name}")
            except ValueError as e:
                print(f"[TTSService] ERROR: Failed to convert '{model_name}' to enum: {e}")
                raise ValueError(f"Unknown model: {model_name}")

        if model_name == TTSModelName.TTS_1:
            print("[TTSService] Using OpenAI TTS")
            return await self._openai_tts(text)
        elif model_name in [TTSModelName.ELEVEN_V3, TTSModelName.ELEVEN_MULTILINGUAL_V2]:
            print(f"[TTSService] Using ElevenLabs TTS with model: {model_name.value}")
            return await self._elevenlabs_tts(text, model_name.value)
        elif model_name == TTSModelName.AURA_2_THALIA_EN:
            print("[TTSService] Using Deepgram TTS")
            return await self._deepgram_tts(text)
        elif model_name == TTSModelName.SONIC_3:
            print("[TTSService] Using Cartesia TTS")
            return await self._cartesia_tts(text)
        elif model_name == TTSModelName.MINIMAX_SPEECH_02:
            print("[TTSService] Using MiniMax Speech-02 TTS")
            return await self._minimax_speech_tts(text)
        # Uncomment to enable Replicate models (requires Pro plan for 180s timeout)
        # elif model_name == TTSModelName.SUNO_BARK:
        #     print("[TTSService] Using Suno Bark TTS")
        #     return await self._replicate_bark_tts(text)
        # elif model_name == TTSModelName.SESAME_CSM_1B:
        #     print("[TTSService] Using Sesame CSM-1B TTS")
        #     return await self._replicate_csm_tts(text)
        else:
            print(f"[TTSService] ERROR: No handler for model: {model_name}")
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
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            print("[ElevenLabs] ERROR: ELEVENLABS_API_KEY not set!")
            raise ValueError("ELEVENLABS_API_KEY environment variable not set")
        
        actual_model = "eleven_turbo_v2_5" if model == "eleven_v3" else model
        voice_id = "EXAVITQu4vr4xnSDxMaL"
        
        print(f"[ElevenLabs] Starting TTS")
        print(f"[ElevenLabs] Model: {model} -> {actual_model}")
        print(f"[ElevenLabs] Text ({len(text)} chars): {text[:100]}...")
        print(f"[ElevenLabs] API Key: {api_key[:10]}...{api_key[-4:]}")
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg"
                }
                payload = {
                    "text": text,
                    "model_id": actual_model,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75
                    }
                }
                
                print(f"[ElevenLabs] POST to {url}")
                print(f"[ElevenLabs] Payload: {payload}")
                
                response = await client.post(url, json=payload, headers=headers)
                
                print(f"[ElevenLabs] Response status: {response.status_code}")
                print(f"[ElevenLabs] Response headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    error_text = response.text[:500] if len(response.text) > 500 else response.text
                    print(f"[ElevenLabs] ERROR Response: {error_text}")
                    raise Exception(f"ElevenLabs API error: {response.status_code} - {error_text}")
                
                audio_bytes = response.content
                print(f"[ElevenLabs] Success! Received {len(audio_bytes)} bytes of audio")
                return audio_bytes
                
        except httpx.TimeoutException as e:
            print(f"[ElevenLabs] TIMEOUT ERROR: {e}")
            raise
        except httpx.RequestError as e:
            print(f"[ElevenLabs] REQUEST ERROR: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            print(f"[ElevenLabs] UNEXPECTED ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
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
    
    async def _replicate_bark_tts(self, text: str) -> bytes:
        api_token = os.getenv("REPLICATE_API_TOKEN")
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN not set")
        
        print(f"[Suno Bark] Starting TTS for text: {text[:50]}...")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.replicate.com/v1/predictions",
                headers={
                    "Authorization": f"Token {api_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "version": "b76242b40d67c76ab6742e987628a2a9ac019e11d56ab96c4e91ce03b79b2787",
                    "input": {"prompt": text}
                }
            )
            
            if response.status_code != 201:
                raise Exception(f"Replicate API error: {response.status_code}")
            
            prediction = response.json()
            prediction_url = prediction["urls"]["get"]
            
            for _ in range(60):
                await asyncio.sleep(2)
                status_response = await client.get(
                    prediction_url,
                    headers={"Authorization": f"Token {api_token}"}
                )
                status = status_response.json()
                
                if status["status"] == "succeeded":
                    audio_url = status["output"]
                    audio_response = await client.get(audio_url)
                    print(f"[Suno Bark] Success! {len(audio_response.content)} bytes")
                    return audio_response.content
                elif status["status"] == "failed":
                    raise Exception(f"Bark generation failed: {status.get('error')}")
            
            raise Exception("Bark generation timed out")
    
    async def _replicate_csm_tts(self, text: str) -> bytes:
        api_token = os.getenv("REPLICATE_API_TOKEN")
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN not set")
        
        print(f"[Sesame CSM] Starting TTS for text: {text[:50]}...")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.replicate.com/v1/predictions",
                headers={
                    "Authorization": f"Token {api_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "version": "3e59b10a9894c54ae5f2fc0347e3a2f5c82f0574407e53a7d9f76ec7c502ad03",
                    "input": {"text": text}
                }
            )
            
            if response.status_code != 201:
                raise Exception(f"Replicate API error: {response.status_code}")
            
            prediction = response.json()
            prediction_url = prediction["urls"]["get"]
            
            for _ in range(60):
                await asyncio.sleep(2)
                status_response = await client.get(
                    prediction_url,
                    headers={"Authorization": f"Token {api_token}"}
                )
                status = status_response.json()
                
                if status["status"] == "succeeded":
                    audio_url = status["output"]
                    audio_response = await client.get(audio_url)
                    print(f"[Sesame CSM] Success! {len(audio_response.content)} bytes")
                    return audio_response.content
                elif status["status"] == "failed":
                    raise Exception(f"CSM generation failed: {status.get('error')}")
            
            raise Exception("CSM generation timed out")
    
    async def _minimax_speech_tts(self, text: str) -> bytes:
        api_token = os.getenv("REPLICATE_API_TOKEN")
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN not set")
        
        print(f"[MiniMax Speech-02] Starting TTS for text: {text[:50]}...")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.replicate.com/v1/models/minimax/speech-02-turbo/predictions",
                headers={
                    "Authorization": f"Token {api_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "input": {
                        "text": text,
                        "emotion": "auto",
                        "voice_id": "Deep_Voice_Man",
                        "language_boost": "English",
                        "english_normalization": True
                    }
                }
            )
            
            if response.status_code != 201:
                raise Exception(f"Replicate API error: {response.status_code} - {response.text}")
            
            prediction = response.json()
            prediction_url = prediction["urls"]["get"]
            
            for _ in range(60):
                await asyncio.sleep(2)
                status_response = await client.get(
                    prediction_url,
                    headers={"Authorization": f"Token {api_token}"}
                )
                status = status_response.json()
                
                if status["status"] == "succeeded":
                    audio_url = status["output"]
                    if isinstance(audio_url, dict) and "url" in audio_url:
                        audio_url = audio_url["url"]
                    audio_response = await client.get(audio_url)
                    print(f"[MiniMax Speech-02] Success! {len(audio_response.content)} bytes")
                    return audio_response.content
                elif status["status"] == "failed":
                    raise Exception(f"MiniMax generation failed: {status.get('error')}")
            
            raise Exception("MiniMax generation timed out")

# Initialize app
app = FastAPI(title="Voice Arena")

# Log startup
print("=" * 80)
print("VOICE ARENA API STARTING UP")
print(f"TTSModelName enum imported successfully: {TTSModelName}")
print("=" * 80)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No caching - always fetch fresh data from Supabase

# Request models
class StartSessionRequest(BaseModel):
    pass

class ChatRequest(BaseModel):
    session_id: str
    message: str
    mode: Optional[str] = 'battle'
    model_id: Optional[str] = None
    model_a_id: Optional[str] = None
    model_b_id: Optional[str] = None

class VoteRequest(BaseModel):
    session_id: str
    winner: str

class AuthRequest(BaseModel):
    email: str
    password: str

class AuthTokenRequest(BaseModel):
    token: str

def get_models():
    # Always fetch fresh data - no caching to ensure ELO ratings are up-to-date
    supabase = get_supabase()
    response = supabase.table('tts_models').select('*').execute()
    # Filter out disabled Replicate models (Suno Bark and Sesame CSM) due to cold start issues
    disabled_models = ['suno-bark', 'sesame-csm-1b']
    filtered_models = [m for m in response.data if m.get('name') not in disabled_models]
    return filtered_models

def get_tts_service():
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service

@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/models")
async def get_models_list():
    models = get_models()
    return {"models": models}

@app.post("/api/start-session")
async def start_session(authorization: str = Header(None)):
    print("=" * 50)
    print("START SESSION REQUEST RECEIVED")
    print("=" * 50)
    
    supabase = get_supabase()
    print(f"Supabase client initialized: {supabase is not None}")
    
    models = get_models()
    print(f"Fetched {len(models)} models from database")
    
    if len(models) < 2:
        print("ERROR: Not enough TTS models available")
        raise HTTPException(status_code=500, detail="Not enough TTS models available")
    
    selected_models = random.sample(models, 2)
    session_id = str(uuid.uuid4())
    
    # Get user ID from token if authenticated
    user_id = None
    if authorization:
        token = authorization.replace("Bearer ", "")
        try:
            response = supabase.auth.get_user(token)
            if response and response.user:
                user_id = response.user.id
        except Exception as e:
            print(f"Error getting user from token: {e}")
            pass
    
    session_data = {
        'session_id': session_id,
        'model_a_id': selected_models[0]['id'],
        'model_b_id': selected_models[1]['id'],
        'messages': [],
        'prompt_count': 0,
        'user_id': user_id,
        'title': 'New Chat'
    }
    
    print(f"Creating session with data: {session_data}")
    
    try:
        result = supabase.table('sessions').insert(session_data).execute()
        print(f"Session created successfully: {result.data}")
        
        if not result.data:
            raise Exception("Insert returned no data - possible RLS policy blocking")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error creating session: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Check if it's an RLS error
        if "policy" in error_msg.lower() or "permission" in error_msg.lower():
            raise HTTPException(status_code=500, detail="Database permission error - RLS policy may be blocking. Please disable RLS on sessions table.")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to create session: {error_msg}")
    
    return {
        "session_id": session_id,
        "message": "Session started! Ask me anything."
    }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    supabase = get_supabase()
    
    # Get session from Supabase
    session_data = supabase.table('sessions').select('*').eq('session_id', request.session_id).single().execute()
    if not session_data.data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = session_data.data
    models = get_models()
    
    # Mode handling
    mode = request.mode or 'battle'
    
    if mode == 'direct':
        if not request.model_id:
            raise HTTPException(status_code=400, detail="model_id required for direct mode")
        selected_models = [m for m in models if m['id'] == request.model_id]
        if not selected_models:
            raise HTTPException(status_code=404, detail="Model not found")
        selected_models = [selected_models[0]]
    elif mode == 'side-by-side':
        if request.model_a_id and request.model_b_id:
            model_a = next((m for m in models if m['id'] == request.model_a_id), None)
            model_b = next((m for m in models if m['id'] == request.model_b_id), None)
            if not model_a or not model_b:
                raise HTTPException(status_code=404, detail="One or both models not found")
            selected_models = [model_a, model_b]
        else:
            if len(models) < 2:
                raise HTTPException(status_code=500, detail="Not enough TTS models available")
            selected_models = random.sample(models, 2)
    else:
        if len(models) < 2:
            raise HTTPException(status_code=500, detail="Not enough TTS models available")
        selected_models = random.sample(models, 2)
    
    # Get current messages
    messages = session.get('messages', [])
    messages.append({"role": "user", "content": request.message})
    
    # Generate AI response with streaming
    openai_client = get_openai_client()
    
    async def stream_response():
        # Stream text response from OpenAI
        assistant_message = ""
        stream = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                assistant_message += content
                yield json.dumps({"type": "text_delta", "content": content}) + "\n"
        
        # Send complete text
        yield json.dumps({"type": "text", "content": assistant_message}) + "\n"
        messages.append({"role": "assistant", "content": assistant_message})
        
        # Send model info first so frontend knows which models are being used
        if mode == 'direct':
            yield json.dumps({
                "type": "model_info",
                "model_a": selected_models[0].get('display_name') or selected_models[0]['name']
            }) + "\n"
        else:
            yield json.dumps({
                "type": "model_info",
                "model_a": selected_models[0].get('display_name') or selected_models[0]['name'],
                "model_b": selected_models[1].get('display_name') or selected_models[1]['name']
            }) + "\n"
        
        # Generate TTS audio
        tts_service = get_tts_service()
        
        if mode == 'direct':
            audio = await tts_service.generate_speech(assistant_message, selected_models[0]['name'])
            yield json.dumps({"type": "audio_a", "content": audio.hex()}) + "\n"
        else:
            tasks = {
                'audio_a': asyncio.create_task(tts_service.generate_speech(assistant_message, selected_models[0]['name'])),
                'audio_b': asyncio.create_task(tts_service.generate_speech(assistant_message, selected_models[1]['name']))
            }
            
            pending = set(tasks.values())
            task_names = {v: k for k, v in tasks.items()}
            
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    audio_data = await task
                    audio_key = task_names[task]
                    yield json.dumps({"type": audio_key, "content": audio_data.hex()}) + "\n"
        
        # Update session in Supabase
        new_prompt_count = session.get('prompt_count', 0) + 1
        update_data = {
            'messages': messages,
            'prompt_count': new_prompt_count,
            'model_a_id': selected_models[0]['id'],
            'model_b_id': selected_models[1]['id'] if len(selected_models) > 1 else None
        }
        
        # Set title to first message if this is the first prompt
        if new_prompt_count == 1:
            title = request.message[:50] + ('...' if len(request.message) > 50 else '')
            update_data['title'] = title
        
        supabase.table('sessions').update(update_data).eq('session_id', request.session_id).execute()
        
        # Send metadata
        yield json.dumps({
            "type": "metadata",
            "prompt_count": new_prompt_count,
            "should_vote": mode in ['battle', 'side-by-side']
        }) + "\n"
    
    return StreamingResponse(stream_response(), media_type="application/x-ndjson")

@app.post("/api/vote")
async def vote(request: VoteRequest):
    supabase = get_supabase()
    
    # Get session from Supabase
    session_data = supabase.table('sessions').select('*').eq('session_id', request.session_id).single().execute()
    if not session_data.data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = session_data.data
    
    model_a_data = supabase.table('tts_models').select('*').eq('id', session["model_a_id"]).single().execute()
    model_b_data = supabase.table('tts_models').select('*').eq('id', session["model_b_id"]).single().execute()
    
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
    
    supabase.table('votes').insert({
        'session_id': session['id'],
        'winner_model_id': winner_id,
        'loser_model_id': loser_id,
        'vote_type': request.winner,
        'model_a_id': model_a['id'],
        'model_b_id': model_b['id'],
        'model_a_elo_before': model_a['elo_rating'],
        'model_b_elo_before': model_b['elo_rating'],
        'model_a_elo_after': new_a_elo,
        'model_b_elo_after': new_b_elo,
        'prompt_number': session.get("prompt_count", 0)
    }).execute()
    
    return {
        "message": "Vote recorded",
        "winner_elo": new_a_elo,
        "loser_elo": new_b_elo,
        "model_a_name": model_a['name'],
        "model_a_provider": model_a['provider'],
        "model_b_name": model_b['name'],
        "model_b_provider": model_b['provider']
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

@app.post("/api/chat/stream-realtime")
async def stream_chat_realtime(request: ChatRequest, authorization: Optional[str] = Header(None)):
    """
    Real-time streaming endpoint with sentence-buffered TTS generation.
    Flow: LLM tokens → Sentence buffer → TTS generation → Audio chunks → Client
    
    Architecture:
    - LLM stream produces text tokens
    - Sentence buffer accumulates tokens until sentence boundary
    - TTS workers process complete sentences concurrently
    - Audio chunks stream to client as soon as generated
    """
    async def generate():
        try:
            supabase = get_supabase()
            
            # Get session
            session_data = supabase.table('sessions').select('*').eq('session_id', request.session_id).single().execute()
            if not session_data.data:
                yield json.dumps({"type": "error", "message": "Session not found"}) + "\n"
                return
            
            session = session_data.data
            models = get_models()
            
            # Select models based on mode
            if request.mode == 'direct':
                if not request.model_id:
                    yield json.dumps({"type": "error", "message": "model_id required for direct mode"}) + "\n"
                    return
                selected_models = [m for m in models if m['id'] == request.model_id]
                if not selected_models:
                    yield json.dumps({"type": "error", "message": "Model not found"}) + "\n"
                    return
            elif request.mode == 'side-by-side':
                if request.model_a_id and request.model_b_id:
                    model_a = next((m for m in models if m['id'] == request.model_a_id), None)
                    model_b = next((m for m in models if m['id'] == request.model_b_id), None)
                    if not model_a or not model_b:
                        yield json.dumps({"type": "error", "message": "One or both models not found"}) + "\n"
                        return
                    selected_models = [model_a, model_b]
                else:
                    selected_models = random.sample(models, 2)
            else:  # battle mode
                selected_models = random.sample(models, 2)
            
            # Get conversation history
            messages = session.get('messages', [])
            messages.append({"role": "user", "content": request.message})
            
            # Initialize streaming components
            openai_client = get_openai_client()
            tts_service = get_tts_service()
            
            assistant_message = ""
            sentence_buffer = ""
            sentence_terminators = {'.', '!', '?', '\n', ',', ';', ':'}
            audio_chunk_id = 0
            min_chunk_length = 20
            
            # Separate sentence queues for each TTS worker
            sentence_queues = {}
            
            # Output queue for streaming audio chunks immediately
            output_queue = asyncio.Queue()
            
            # TTS worker for processing sentences
            async def tts_worker(model_name, audio_label, sentence_queue):
                print(f"[TTS Worker {audio_label}] Started for model: {model_name}")
                while True:
                    item = await sentence_queue.get()
                    if item is None:  # Sentinel
                        print(f"[TTS Worker {audio_label}] Received stop signal")
                        sentence_queue.task_done()
                        break
                    
                    text, chunk_id = item
                    print(f"[TTS Worker {audio_label}] Processing chunk {chunk_id}: {text[:50]}...")
                    try:
                        print(f"[TTS Worker {audio_label}] Calling generate_speech for {model_name}...")
                        audio_bytes = await asyncio.wait_for(
                            tts_service.generate_speech(text, model_name),
                            timeout=180.0
                        )
                        
                        if audio_bytes and len(audio_bytes) > 0:
                            print(f"[TTS Worker {audio_label}] Generated {len(audio_bytes)} bytes for chunk {chunk_id}")
                            
                            await output_queue.put({
                                "type": "audio_chunk",
                                "label": audio_label,
                                "chunk_id": chunk_id,
                                "data": audio_bytes.hex()
                            })
                            
                            print(f"[TTS Worker {audio_label}] Queued chunk {chunk_id} to output")
                        else:
                            print(f"[TTS Worker {audio_label}] WARNING: Empty audio for chunk {chunk_id}")
                        
                    except asyncio.TimeoutError:
                        print(f"[TTS Worker {audio_label}] TIMEOUT for chunk {chunk_id} (model: {model_name})")
                        await output_queue.put({
                            "type": "tts_error",
                            "label": audio_label,
                            "error": f"Timeout generating audio for {model_name}"
                        })
                    except asyncio.CancelledError:
                        print(f"[TTS Worker {audio_label}] CANCELLED")
                        break
                    except Exception as e:
                        error_msg = f"{type(e).__name__}: {str(e)}"
                        print(f"[TTS Worker {audio_label}] ERROR for chunk {chunk_id} (model: {model_name}): {error_msg}")
                        import traceback
                        traceback.print_exc()
                        await output_queue.put({
                            "type": "tts_error",
                            "label": audio_label,
                            "error": error_msg
                        })
                    finally:
                        sentence_queue.task_done()
                
                print(f"[TTS Worker {audio_label}] Stopped")
            
            # Start TTS worker(s) with separate queues
            tts_tasks = []
            if request.mode == 'direct':
                sentence_queues['a'] = asyncio.Queue()
                tts_tasks.append(asyncio.create_task(tts_worker(selected_models[0]['name'], 'a', sentence_queues['a'])))
                print(f"[Main] Started 1 worker for direct mode")
            else:
                sentence_queues['a'] = asyncio.Queue()
                sentence_queues['b'] = asyncio.Queue()
                tts_tasks.append(asyncio.create_task(tts_worker(selected_models[0]['name'], 'a', sentence_queues['a'])))
                tts_tasks.append(asyncio.create_task(tts_worker(selected_models[1]['name'], 'b', sentence_queues['b'])))
                print(f"[Main] Started 2 workers: a={selected_models[0]['name']}, b={selected_models[1]['name']}")
            
            # Send model info FIRST before any audio chunks
            if request.mode == 'direct':
                yield json.dumps({
                    "type": "model_info",
                    "model_a": selected_models[0].get('display_name') or selected_models[0]['name']
                }) + "\n"
            else:
                yield json.dumps({
                    "type": "model_info",
                    "model_a": selected_models[0].get('display_name') or selected_models[0]['name'],
                    "model_b": selected_models[1].get('display_name') or selected_models[1]['name']
                }) + "\n"
            
            print("[Main] Sent model_info to client")
            
            # Stream LLM tokens and extract sentences
            stream = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    assistant_message += content
                    sentence_buffer += content
                    
                    # Send text delta to client immediately
                    yield json.dumps({"type": "text_delta", "content": content}) + "\n"
                    
                    # Check for sentence boundaries
                    if any(term in content for term in sentence_terminators):
                        sentences = []
                        temp_buffer = ""
                        for char in sentence_buffer:
                            temp_buffer += char
                            if char in sentence_terminators and len(temp_buffer.strip()) >= min_chunk_length:
                                sentences.append(temp_buffer.strip())
                                temp_buffer = ""
                        
                        for sentence in sentences:
                            if sentence and len(sentence) >= min_chunk_length:
                                print(f"[Main] Queuing chunk {audio_chunk_id}: {sentence[:50]}...")
                                for label, queue in sentence_queues.items():
                                    await queue.put((sentence, audio_chunk_id))
                                audio_chunk_id += 1
                        
                        sentence_buffer = temp_buffer
                        
                    # Yield any audio chunks that are ready
                    while not output_queue.empty():
                        audio_chunk = await output_queue.get()
                        if audio_chunk.get('type') == 'tts_error':
                            print(f"[Main] Yielding TTS error: label={audio_chunk['label']}, error={audio_chunk['error']}")
                        else:
                            print(f"[Main] Yielding audio chunk: label={audio_chunk['label']}, chunk_id={audio_chunk.get('chunk_id')}")
                        yield json.dumps(audio_chunk) + "\n"
                        output_queue.task_done()
            
            # Process remaining buffer
            if sentence_buffer.strip():
                for queue in sentence_queues.values():
                    await queue.put((sentence_buffer.strip(), audio_chunk_id))
            
            # Stop TTS workers
            for queue in sentence_queues.values():
                await queue.put(None)
            
            # Send complete text
            yield json.dumps({"type": "text", "content": assistant_message}) + "\n"
            messages.append({"role": "assistant", "content": assistant_message})
            
            # Wait for all TTS workers to complete
            print(f"[Main] Waiting for {len(tts_tasks)} workers to complete...")
            await asyncio.gather(*tts_tasks)
            print(f"[Main] All workers completed. Output queue size: {output_queue.qsize()}")
            
            # Stream remaining audio chunks
            chunk_count = 0
            while not output_queue.empty():
                audio_chunk = await output_queue.get()
                if audio_chunk.get('type') == 'tts_error':
                    print(f"[Main] Yielding final TTS error: label={audio_chunk['label']}, error={audio_chunk['error']}")
                else:
                    print(f"[Main] Yielding final audio chunk: label={audio_chunk['label']}, chunk_id={audio_chunk.get('chunk_id')}")
                yield json.dumps(audio_chunk) + "\n"
                output_queue.task_done()
                chunk_count += 1
            
            print(f"[Main] Streamed {chunk_count} final audio chunks")
            
            # Update session
            new_prompt_count = session.get('prompt_count', 0) + 1
            update_data = {
                'messages': messages,
                'prompt_count': new_prompt_count,
                'model_a_id': selected_models[0]['id'],
                'model_b_id': selected_models[1]['id'] if len(selected_models) > 1 else None
            }
            
            if new_prompt_count == 1:
                title = request.message[:50] + ('...' if len(request.message) > 50 else '')
                update_data['title'] = title
            
            supabase.table('sessions').update(update_data).eq('session_id', request.session_id).execute()
            
            # Send metadata
            yield json.dumps({
                "type": "metadata",
                "prompt_count": new_prompt_count,
                "should_vote": request.mode in ['battle', 'side-by-side']
            }) + "\n"
            
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
    
    return StreamingResponse(generate(), media_type="application/x-ndjson")

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    
    try:
        # Receive initial message with session_id, message, mode, etc.
        data = await websocket.receive_json()
        
        session_id = data.get('session_id')
        message = data.get('message')
        mode = data.get('mode', 'battle')
        model_id = data.get('model_id')
        model_a_id = data.get('model_a_id')
        model_b_id = data.get('model_b_id')
        
        supabase = get_supabase()
        
        # Get session from Supabase
        session_data = supabase.table('sessions').select('*').eq('session_id', session_id).single().execute()
        if not session_data.data:
            await websocket.send_json({"type": "error", "message": "Session not found"})
            await websocket.close()
            return
        
        session = session_data.data
        models = get_models()
        
        # Select models based on mode
        if mode == 'direct':
            if not model_id:
                await websocket.send_json({"type": "error", "message": "model_id required for direct mode"})
                await websocket.close()
                return
            selected_models = [m for m in models if m['id'] == model_id]
            if not selected_models:
                await websocket.send_json({"type": "error", "message": "Model not found"})
                await websocket.close()
                return
        elif mode == 'side-by-side':
            if model_a_id and model_b_id:
                model_a = next((m for m in models if m['id'] == model_a_id), None)
                model_b = next((m for m in models if m['id'] == model_b_id), None)
                if not model_a or not model_b:
                    await websocket.send_json({"type": "error", "message": "One or both models not found"})
                    await websocket.close()
                    return
                selected_models = [model_a, model_b]
            else:
                selected_models = random.sample(models, 2)
        else:  # battle mode
            selected_models = random.sample(models, 2)
        
        # Get messages
        messages = session.get('messages', [])
        messages.append({"role": "user", "content": message})
        
        # Generate AI response with streaming
        openai_client = get_openai_client()
        assistant_message = ""
        
        stream = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                assistant_message += content
                await websocket.send_json({"type": "text_delta", "content": content})
        
        # Send complete text
        await websocket.send_json({"type": "text", "content": assistant_message})
        messages.append({"role": "assistant", "content": assistant_message})
        
        # Send model info
        if mode == 'direct':
            await websocket.send_json({
                "type": "model_info",
                "model_a": selected_models[0].get('display_name') or selected_models[0]['name']
            })
        else:
            await websocket.send_json({
                "type": "model_info",
                "model_a": selected_models[0].get('display_name') or selected_models[0]['name'],
                "model_b": selected_models[1].get('display_name') or selected_models[1]['name']
            })
        
        # Generate TTS audio (revert to working approach - full audio at once)
        tts_service = get_tts_service()
        
        if mode == 'direct':
            audio = await tts_service.generate_speech(assistant_message, selected_models[0]['name'])
            yield json.dumps({"type": "audio_a", "content": audio.hex()}) + "\n"
        else:
            # Generate both audios in parallel
            tasks = {
                'audio_a': asyncio.create_task(tts_service.generate_speech(assistant_message, selected_models[0]['name'])),
                'audio_b': asyncio.create_task(tts_service.generate_speech(assistant_message, selected_models[1]['name']))
            }
            
            pending = set(tasks.values())
            task_names = {v: k for k, v in tasks.items()}
            
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    audio_data = await task
                    audio_key = task_names[task]
                    yield json.dumps({"type": audio_key, "content": audio_data.hex()}) + "\n"
        
        # Update session in Supabase
        new_prompt_count = session.get('prompt_count', 0) + 1
        update_data = {
            'messages': messages,
            'prompt_count': new_prompt_count,
            'model_a_id': selected_models[0]['id'],
            'model_b_id': selected_models[1]['id'] if len(selected_models) > 1 else None
        }
        
        if new_prompt_count == 1:
            title = message[:50] + ('...' if len(message) > 50 else '')
            update_data['title'] = title
        
        supabase.table('sessions').update(update_data).eq('session_id', session_id).execute()
        
        # Send metadata
        await websocket.send_json({
            "type": "metadata",
            "prompt_count": new_prompt_count,
            "should_vote": mode in ['battle', 'side-by-side']
        })
        
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

@app.post("/api/auth/signup")
async def signup(auth_request: AuthRequest):
    supabase = get_supabase()
    try:
        response = supabase.auth.sign_up({
            "email": auth_request.email,
            "password": auth_request.password
        })
        
        if response.user:
            return {
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "user_metadata": response.user.user_metadata
                },
                "message": "Signup successful! Please check your email to confirm."
            }
        else:
            raise HTTPException(status_code=400, detail="Signup failed")
    except Exception as e:
        print(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
async def login(auth_request: AuthRequest):
    supabase = get_supabase()
    try:
        response = supabase.auth.sign_in_with_password({
            "email": auth_request.email,
            "password": auth_request.password
        })
        
        if response.session and response.user:
            return {
                "access_token": response.session.access_token,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "user_metadata": response.user.user_metadata
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Login failed")
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/auth/google")
async def google_auth():
    supabase = get_supabase()
    try:
        # Use infrafield.app as the primary domain
        response = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://infrafield.app"
            }
        })
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class CodeExchangeRequest(BaseModel):
    code: str

@app.post("/api/auth/exchange-code")
async def exchange_code(request: CodeExchangeRequest):
    supabase = get_supabase()
    try:
        # Exchange the code for a session
        response = supabase.auth.exchange_code_for_session({"auth_code": request.code})
        
        if response and response.session:
            return {
                "access_token": response.session.access_token,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email,
                    "user_metadata": response.user.user_metadata
                }
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to exchange code")
    except Exception as e:
        print(f"Error exchanging code: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/verify")
async def verify_token(token_request: AuthTokenRequest):
    supabase = get_supabase()
    try:
        response = supabase.auth.get_user(token_request.token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Return user data in a serializable format
        user = response.user
        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "user_metadata": user.user_metadata,
                "created_at": str(user.created_at) if hasattr(user, 'created_at') else None
            }
        }
    except Exception as e:
        print(f"Error verifying token: {e}")
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/api/chat-history")
async def get_chat_history(authorization: str = Header(None)):
    supabase = get_supabase()
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = response.user.id
        print(f"Fetching chat history for user: {user_id}")
        
        # Get user's chat sessions ordered by last updated
        sessions = supabase.table('sessions').select('*').eq('user_id', user_id).order('updated_at', desc=True).execute()
        
        print(f"Found {len(sessions.data)} sessions for user {user_id}")
        
        return {"sessions": sessions.data}
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat-session/{session_id}")
async def get_chat_session(session_id: str, authorization: str = Header(None)):
    supabase = get_supabase()
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = response.user.id
        
        # Get session - ensure it belongs to the user
        session_data = supabase.table('sessions').select('*').eq('session_id', session_id).eq('user_id', user_id).single().execute()
        
        if not session_data.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session_data.data
    except Exception as e:
        print(f"Error fetching chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/chat-session/{session_id}")
async def delete_chat_session(session_id: str, authorization: str = Header(None)):
    supabase = get_supabase()
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = response.user.id
        
        # Delete session - ensure it belongs to the user
        supabase.table('sessions').delete().eq('session_id', session_id).eq('user_id', user_id).execute()
        
        return {"message": "Session deleted successfully"}
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
