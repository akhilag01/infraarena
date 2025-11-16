from enum import Enum


class VoteOutcome(Enum):
    A = "A"
    B = "B"
    TIE = "tie"
    BOTH_BAD = "both_bad"


class TTSModelName(str, Enum):
    """Enum for all available TTS model names with their providers."""

    # OpenAI models
    TTS_1 = "tts-1"

    # ElevenLabs models
    ELEVEN_V3 = "eleven_v3"
    ELEVEN_MULTILINGUAL_V2 = "eleven_multilingual_v2"

    # Deepgram models
    AURA_2_THALIA_EN = "aura-2-thalia-en"

    # Cartesia models
    SONIC_3 = "sonic-3"

    # Replicate models
    SUNO_BARK = "suno-bark"
    SESAME_CSM_1B = "sesame-csm-1b"
    MINIMAX_SPEECH_02 = "minimax-speech-02"
    
    # Gradio/HuggingFace models
    ORPHEUS_TTS = "orpheus-tts"
    
    # Kokoro
    KOKORO_82M = "kokoro-82m"
