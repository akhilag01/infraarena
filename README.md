# Voice Arena

A real-time TTS comparison platform where users compare voice models side-by-side with progressive audio streaming. Features an ELO ranking system and sentence-level streaming for instant audio playback.

## Features

- **Real-time Audio Streaming**: Progressive audio loading with sentence-level TTS generation
- **Side-by-Side Comparison**: Compare two TTS models simultaneously with visual progress indicators
- **Multiple Providers**: ElevenLabs, OpenAI, Deepgram, Cartesia
- **ELO Ranking System**: Track model performance based on user votes
- **Progressive Loading**: YouTube-style buffering with dual progress bars (buffered vs played)
- **Three Modes**: 
  - Battle Mode: Blind comparison with hidden model names
  - Side-by-Side: Compare specific models with visible names
  - Direct Chat: Single model conversation
- **Leaderboard**: View rankings and statistics for all models
- **Authentication**: Optional user accounts with Google OAuth and email/password

## Architecture

- **Backend**: FastAPI with real-time streaming endpoints
- **Frontend**: Vanilla JavaScript with MediaSource Extensions API
- **TTS Providers**: Multi-provider support with concurrent generation
- **Database**: Supabase (PostgreSQL) for user data and voting history
- **Streaming**: Sentence-buffered LLM→TTS pipeline with HTTP streaming
- **Deployment**: Vercel serverless functions

## Local Development

### Prerequisites

- Python 3.8+
- Node.js (for Vercel CLI, optional)
- API keys for TTS providers
- Supabase account (for database and auth)

### Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Create `.env` file:**
```bash
cp .env.example .env
```

3. **Add your API keys to `.env`:**
```env
# TTS Provider Keys
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...

# Supabase (Database & Auth)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Google OAuth (optional, for auth)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

**Note for Team**: Contact the team lead for the shared development API keys via Slack/Discord. Keys are not stored in the repository for security.

4. **Run locally:**
```bash
# Option A: Python directly
cd api
python3 -m uvicorn index:app --reload --port 8000

# Option B: Vercel CLI (recommended)
vercel dev
```

5. **Open http://localhost:3000** (Vercel) or **http://localhost:8000** (Python)

## Deploying to Vercel

### Quick Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/yourusername/voice-arena)

### Manual Deploy

1. **Install Vercel CLI:**
```bash
npm i -g vercel
```

2. **Login to Vercel:**
```bash
vercel login
```

3. **Deploy:**
```bash
vercel
```

4. **Add environment variables in Vercel Dashboard:**
   - Go to your project → Settings → Environment Variables
   - Add all keys from `.env`:
     - `OPENAI_API_KEY`
     - `ELEVENLABS_API_KEY`
     - `DEEPGRAM_API_KEY`
     - `CARTESIA_API_KEY`
     - `SUPABASE_URL`
     - `SUPABASE_KEY`
     - `GOOGLE_CLIENT_ID` (optional)
     - `GOOGLE_CLIENT_SECRET` (optional)

5. **Redeploy after adding environment variables:**
```bash
vercel --prod
```

### Vercel Configuration

The project includes `vercel.json` with the following configuration:

```json
{
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "/api/index"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

- **Backend**: Python FastAPI serverless function at `/api/index.py`
- **Frontend**: Static files served from `/public/`
- **Routing**: All `/api/*` routes handled by Python, everything else serves static HTML

### Requirements

The `requirements.txt` must include all Python dependencies:
```
fastapi
python-dotenv
openai
elevenlabs
deepgram-sdk
cartesia
pydantic
httpx
python-multipart
supabase
gotrue
```

### Vercel Limitations

- **No WebSockets**: Uses HTTP streaming with `StreamingResponse` instead
- **10s timeout**: Default serverless function timeout (can be increased with Pro plan)
- **50MB limit**: Response size limit for serverless functions
- **Cold starts**: First request may be slower (~1-3s)

### Custom Domain

1. Go to project Settings → Domains
2. Add your custom domain
3. Update DNS records as instructed
4. SSL certificate auto-provisioned by Vercel

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
