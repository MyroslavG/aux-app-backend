-- Add expiration fields to posts table
ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_expired BOOLEAN DEFAULT FALSE;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours');

-- Update existing posts to have expires_at set to 24 hours after created_at
UPDATE posts
SET expires_at = created_at + INTERVAL '24 hours'
WHERE expires_at IS NULL;

-- Mark any posts that should already be expired
UPDATE posts
SET is_expired = TRUE
WHERE is_expired = FALSE
AND expires_at <= NOW();

-- Create indexes for efficient expired post queries
CREATE INDEX IF NOT EXISTS idx_posts_is_expired ON posts(is_expired);
CREATE INDEX IF NOT EXISTS idx_posts_expires_at ON posts(expires_at) WHERE is_expired = FALSE;

-- Create function to automatically mark posts as expired
CREATE OR REPLACE FUNCTION mark_expired_posts()
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    UPDATE posts
    SET is_expired = TRUE
    WHERE is_expired = FALSE
    AND expires_at <= NOW();

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- Optional: Create a scheduled job using pg_cron if available
-- Uncomment the following lines if you have pg_cron extension installed:
-- SELECT cron.schedule('mark-expired-posts', '*/5 * * * *', 'SELECT mark_expired_posts()');
