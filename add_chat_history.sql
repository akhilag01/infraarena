-- Update sessions table to support chat history
ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS title TEXT,
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Create index for faster user chat queries
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);

-- Add RLS policies for user chat history
CREATE POLICY "Users can view their own chat sessions"
    ON sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own chat sessions"
    ON sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own chat sessions"
    ON sessions FOR UPDATE
    USING (auth.uid() = user_id);
