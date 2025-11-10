-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- TTS Models table
CREATE TABLE IF NOT EXISTS tts_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    provider VARCHAR(255) NOT NULL,
    elo_rating FLOAT DEFAULT 1500.0,
    total_votes INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sessions table (tracks conversation sessions)
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    model_a_id UUID REFERENCES tts_models(id) NOT NULL,
    model_b_id UUID REFERENCES tts_models(id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Votes table (tracks all votes with full context)
CREATE TABLE IF NOT EXISTS votes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    winner_model_id UUID REFERENCES tts_models(id),
    loser_model_id UUID REFERENCES tts_models(id),
    vote_type VARCHAR(50) NOT NULL CHECK (vote_type IN ('A', 'B', 'tie', 'both_bad')),
    model_a_id UUID REFERENCES tts_models(id) NOT NULL,
    model_b_id UUID REFERENCES tts_models(id) NOT NULL,
    model_a_elo_before FLOAT NOT NULL,
    model_b_elo_before FLOAT NOT NULL,
    model_a_elo_after FLOAT NOT NULL,
    model_b_elo_after FLOAT NOT NULL,
    prompt_number INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User profiles table (extends auth.users with additional info)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username VARCHAR(255),
    avatar_url TEXT,
    total_votes INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_votes_user_id ON votes(user_id);
CREATE INDEX IF NOT EXISTS idx_votes_session_id ON votes(session_id);
CREATE INDEX IF NOT EXISTS idx_votes_created_at ON votes(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_tts_models_elo ON tts_models(elo_rating DESC);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_tts_models_updated_at
    BEFORE UPDATE ON tts_models
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to create user profile on signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (id, username, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'name', NEW.email),
        NEW.raw_user_meta_data->>'avatar_url'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create profile on user signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION handle_new_user();

-- Row Level Security (RLS) Policies
ALTER TABLE tts_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- TTS Models: Public read, no direct write
CREATE POLICY "TTS models are viewable by everyone"
    ON tts_models FOR SELECT
    USING (true);

-- Sessions: Users can view their own sessions, create new ones
CREATE POLICY "Users can view their own sessions"
    ON sessions FOR SELECT
    USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can create sessions"
    ON sessions FOR INSERT
    WITH CHECK (true);

-- Votes: Users can view all votes (for leaderboard), insert their own
CREATE POLICY "Votes are viewable by everyone"
    ON votes FOR SELECT
    USING (true);

CREATE POLICY "Users can create votes"
    ON votes FOR INSERT
    WITH CHECK (true);

-- User Profiles: Users can view all profiles, update only their own
CREATE POLICY "Profiles are viewable by everyone"
    ON user_profiles FOR SELECT
    USING (true);

CREATE POLICY "Users can update their own profile"
    ON user_profiles FOR UPDATE
    USING (auth.uid() = id);

-- Insert initial TTS models
INSERT INTO tts_models (name, provider, elo_rating) VALUES
    ('tts-1', 'OpenAI', 1500.0),
    ('eleven_multilingual_v2', 'ElevenLabs', 1500.0),
    ('aura-2-thalia-en', 'Deepgram', 1500.0),
    ('sonic-3', 'Cartesia', 1500.0)
ON CONFLICT (name) DO NOTHING;
