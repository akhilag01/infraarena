# Voice Arena

A minimalist voice TTS comparison platform where users chat with two alternating TTS models and vote on their preferences. Features an ELO ranking system to track model performance.

## Features

- **Dual TTS Comparison**: Two TTS models alternate responses in a single conversation
- **Multiple Providers**: ElevenLabs, OpenAI, Deepgram, Cartesia
- **ELO Ranking System**: Track model performance based on user votes
- **Minimalist UI**: Clean, modern interface inspired by Sesame
- **Real-time Voting**: Vote every 3 prompts on preferred voice
- **Leaderboard**: View rankings and statistics for all models

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

3. Add your API keys to `.env`:
```
OPENAI_API_KEY=your_openai_key
ELEVENLABS_API_KEY=your_elevenlabs_key
DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key
```

**Note for Team**: Contact the team lead for the shared development API keys via Slack/Discord. Keys are not stored in the repository for security.

4. Run the application:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

5. Open http://localhost:8000 in your browser

## Architecture

- **Backend**: FastAPI with SQLAlchemy for database management
- **Frontend**: Vanilla JavaScript with modern CSS
- **TTS Providers**: Multi-provider support with unified interface
- **Database**: SQLite (configurable to PostgreSQL)
- **Ranking**: ELO rating system for competitive model comparison

## Models Supported

All models use comparable voice profiles for fair comparison:

- **ElevenLabs (eleven_v3, eleven_multilingual_v2)**: 
  - Voice: "Sarah" (EXAVITQu4vr4xnSDxMaL)
  - Settings: Balanced stability (0.5), high clarity (0.75), neutral style
  - Clear, professional American English female voice

- **OpenAI (tts-1)**: 
  - Voice: "Nova"
  - Speed: 1.0 (normal)
  - Friendly, conversational American English female voice

- **Deepgram (aura-2-thalia-en)**: 
  - Model: Aura Asteria
  - Warm, expressive American English female voice

- **Cartesia (sonic-3)**: 
  - Voice ID: British English Female (156fb8d2-335b-4950-9cb3-a2d33befec77)
  - Neutral, professional British English female voice

### Voice Selection Strategy

All voices are:
- **Female** for consistency
- **Native English speakers** (American/British accents)
- **Neutral/Professional tone** (not overly dramatic or monotone)
- **Similar speaking pace** (normal speed, ~150-180 WPM)
- **Conversational quality** (suitable for dialogue, not robotic)

This ensures comparisons focus on **voice quality, naturalness, and clarity** rather than confounding variables like gender, accent variation, or speaking style.

## About LiveKit

While this implementation uses direct API calls for simplicity, LiveKit would be excellent for production use cases requiring:
- Real-time bidirectional audio streaming
- Low-latency voice communication
- WebRTC infrastructure
- Multi-party conversations
- Mobile app support

For this demo, direct HTTP APIs provide sufficient performance while keeping the implementation simple.
