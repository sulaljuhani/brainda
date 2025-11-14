-- Migration 012: Reinstate reminders unique constraint for active duplicates
-- Rationale:
--   Tests require the database to prevent creation of exact duplicate reminders
--   (same user_id, title, due_at_utc) when status is 'active'. Earlier
--   migrations removed this constraint to rely solely on middleware, but
--   we reintroduce a partial unique index to enforce integrity at the DB layer.

-- Be idempotent and safe
CREATE UNIQUE INDEX IF NOT EXISTS idx_reminders_unique_active
ON reminders(user_id, title, due_at_utc)
WHERE status = 'active';

