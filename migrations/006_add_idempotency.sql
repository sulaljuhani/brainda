-- Stage 5: Full idempotency infrastructure

-- Create extension for UUID generation if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS idempotency_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,  -- /api/v1/reminders, /api/v1/notes, etc.
    request_hash TEXT NOT NULL,  -- SHA256 of request body
    response_status INTEGER NOT NULL,  -- HTTP status code
    response_body JSONB NOT NULL,  -- Cached response
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',

    -- Composite unique constraint: one key per user+endpoint
    CONSTRAINT unique_idempotency_key UNIQUE (user_id, idempotency_key, endpoint)
);

-- Index for cleanup job
CREATE INDEX idx_idempotency_keys_expires_at ON idempotency_keys(expires_at);

-- Index for fast lookups
CREATE INDEX idx_idempotency_keys_user_key ON idempotency_keys(user_id, idempotency_key);

-- Drop old 5-minute deduplication indexes
DROP INDEX IF EXISTS idx_notes_dedup;
DROP INDEX IF EXISTS idx_reminders_dedup;

-- Simplify uniqueness constraints for data integrity
-- Notes: prevent duplicate titles per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_notes_user_title ON notes(user_id, lower(title));

-- Reminders: allow same title but not exact duplicates (same title + due_at + active status)
-- This is a safety net - idempotency middleware is the primary defense
CREATE UNIQUE INDEX IF NOT EXISTS idx_reminders_unique
ON reminders(user_id, title, due_at_utc)
WHERE status = 'active';
