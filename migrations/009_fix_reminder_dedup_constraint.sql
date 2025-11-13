-- Fix reminder deduplication constraint conflict with idempotency middleware
--
-- The idempotency middleware handles exact-once semantics based on idempotency keys.
-- The database unique constraint on (user_id, title, due_at_utc) is too restrictive
-- and prevents legitimate use cases where different idempotency keys should create
-- separate reminders even with the same content.
--
-- This migration removes the content-based deduplication constraint and relies
-- solely on the idempotency middleware for duplicate prevention.

DROP INDEX IF EXISTS idx_reminders_unique;
