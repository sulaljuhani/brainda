-- Migration 013: Add idempotency_key_ref to reminders and scope unique constraint
-- Rationale:
--   - Stage 2 requires the DB to prevent duplicate active reminders with the same
--     (user_id, title, due_at_utc) when requests do NOT use Idempotency-Key.
--   - Stage 5 requires allowing separate reminders for identical payloads when
--     different Idempotency-Keys are used.
--   We add a nullable column to record the creating Idempotency-Key (if any), and
--   scope the unique constraint to rows where idempotency_key_ref IS NULL.

-- Add nullable reference column
ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS idempotency_key_ref TEXT NULL;

-- Replace previous unique index with a conditional one that only applies when
-- no Idempotency-Key was used to create the reminder.
DROP INDEX IF EXISTS idx_reminders_unique_active;
CREATE UNIQUE INDEX IF NOT EXISTS idx_reminders_unique_active_no_idem
ON reminders(user_id, title, due_at_utc)
WHERE status = 'active' AND idempotency_key_ref IS NULL;

