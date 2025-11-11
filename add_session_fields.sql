-- Add fields to sessions table to store conversation state
ALTER TABLE sessions 
ADD COLUMN IF NOT EXISTS messages JSONB DEFAULT '[]',
ADD COLUMN IF NOT EXISTS prompt_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Add trigger to update updated_at
CREATE OR REPLACE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
