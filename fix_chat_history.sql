-- Fix chat history functionality
-- Only add what's missing since columns already exist

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop and recreate trigger
DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own chat sessions" ON sessions;
DROP POLICY IF EXISTS "Users can create their own chat sessions" ON sessions;
DROP POLICY IF EXISTS "Users can update their own chat sessions" ON sessions;

-- Enable RLS on sessions table
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for user chat history
CREATE POLICY "Users can view their own chat sessions"
    ON sessions FOR SELECT
    USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can create their own chat sessions"
    ON sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can update their own chat sessions"
    ON sessions FOR UPDATE
    USING (auth.uid() = user_id OR user_id IS NULL);

-- Allow users to delete their own sessions
CREATE POLICY "Users can delete their own chat sessions"
    ON sessions FOR DELETE
    USING (auth.uid() = user_id);
