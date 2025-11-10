# Supabase Setup Instructions

## 1. Run the SQL Schema

Go to your Supabase dashboard → SQL Editor and run the contents of `supabase_schema.sql`

This will create:
- `tts_models` - Stores TTS model information and ELO ratings
- `sessions` - Tracks conversation sessions
- `votes` - Stores all votes with full context (before/after ELO, vote type, etc.)
- `user_profiles` - User profile information
- Row Level Security (RLS) policies for data protection
- Triggers for auto-creating user profiles on signup

## 2. Enable Google OAuth

1. Go to Authentication → Providers in your Supabase dashboard
2. Enable Google provider
3. Add your Google OAuth credentials:
   - Go to https://console.cloud.google.com/
   - Create a new project or select existing
   - Enable Google+ API
   - Go to Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: Web application
   - Authorized JavaScript origins: `http://localhost:8000`
   - Authorized redirect URIs: `https://lmsqcuiusxcnoipfnyzt.supabase.co/auth/v1/callback`
   - Copy Client ID and Client Secret to Supabase

## 3. Configure Email Auth

1. Go to Authentication → Email Templates
2. Customize confirmation and password reset emails if needed
3. Under Settings → Auth → Email, make sure "Enable email confirmations" is set according to your preference

## 4. Test the Setup

After running the SQL schema, you should see:
- 4 TTS models pre-populated with 1500 ELO each
- Empty sessions, votes, and user_profiles tables
- RLS policies enabled

## 5. Frontend Integration

The frontend already has authentication UI ready. Users can:
- Sign up with email/password
- Login with email/password
- Login with Google OAuth
- View their voting history
- Track their contributions to the global ELO rankings

## Database Schema Overview

### tts_models
- Stores model name, provider, ELO rating, wins/losses/total_votes
- Public read access, updates only through vote API

### sessions
- Links user_id to model pairs for each conversation
- Tracks which models were compared

### votes
- Full audit trail of every vote
- Stores:
  - Vote type (A, B, tie, both_bad)
  - ELO before and after for both models
  - User ID and session ID
  - Timestamp for historical analysis
  
### user_profiles
- Auto-created when user signs up
- Stores username, avatar_url, total_votes
- Users can only update their own profile

## Analytics Queries

Get vote history for a user:
```sql
SELECT v.*, tm_a.name as model_a_name, tm_b.name as model_b_name
FROM votes v
JOIN tts_models tm_a ON v.model_a_id = tm_a.id
JOIN tts_models tm_b ON v.model_b_id = tm_b.id
WHERE v.user_id = '<user_id>'
ORDER BY v.created_at DESC;
```

Get ELO progression over time for a model:
```sql
SELECT created_at, model_a_elo_after as elo
FROM votes
WHERE model_a_id = '<model_id>'
UNION ALL
SELECT created_at, model_b_elo_after as elo
FROM votes
WHERE model_b_id = '<model_id>'
ORDER BY created_at ASC;
```
