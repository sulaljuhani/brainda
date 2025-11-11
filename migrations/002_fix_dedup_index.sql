-- Stage 1: Fix for deduplication index

-- Drop the failing index
DROP INDEX IF EXISTS idx_notes_dedup;

-- This index is created in 003_fix_dedup_index_again.sql
