-- Allow updates to TTS models table for ELO rating updates
-- This is needed because the API needs to update elo_rating, wins, losses, and total_votes
CREATE POLICY "Allow updates to TTS models"
    ON tts_models FOR UPDATE
    USING (true)
    WITH CHECK (true);
