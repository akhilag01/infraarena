import os
import httpx
from openai import OpenAI
from elevenlabs import ElevenLabs
from typing import Optional

class TTSService:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        self.cartesia_api_key = os.getenv("CARTESIA_API_KEY")
    
    async def generate_speech(self, text: str, model_name: str) -> bytes:
        if model_name == "tts-1":
            return await self._openai_tts(text)
        elif model_name == "eleven_v3":
            return await self._elevenlabs_tts(text, "eleven_turbo_v2_5")
        elif model_name == "eleven_multilingual_v2":
            return await self._elevenlabs_tts(text, "eleven_multilingual_v2")
        elif model_name == "aura-2-thalia-en":
            return await self._deepgram_tts(text)
        elif model_name == "sonic-3":
            return await self._cartesia_tts(text)
        else:
            raise ValueError(f"Unknown model: {model_name}")
    
    async def _openai_tts(self, text: str) -> bytes:
        response = self.openai_client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            speed=1.0
        )
        return response.content
    
    async def _elevenlabs_tts(self, text: str, model: str) -> bytes:
        audio_generator = self.elevenlabs_client.text_to_speech.convert(
            text=text,
            voice_id="EXAVITQu4vr4xnSDxMaL",
            model_id=model,
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
