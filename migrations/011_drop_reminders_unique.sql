-- Migration 011: Enforce removal of legacy reminders unique index
-- Context:
--   Earlier versions (e.g., migration 006) created a content-based unique index
--   on reminders: idx_reminders_unique (user_id, title, due_at_utc) WHERE status='active'.
--   Migration 009 intended to drop this index to rely on idempotency middleware.
--   This migration ensures the index is removed even if it reappeared or was
--   recreated out of band.

-- Be idempotent and safe: only drop if it exists.
DROP INDEX IF EXISTS idx_reminders_unique;

-- Optional: also remove any older dedup index name if present
DROP INDEX IF EXISTS idx_reminders_dedup;

