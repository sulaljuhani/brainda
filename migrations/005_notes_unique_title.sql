-- Stage 1: tighten note deduplication to be case-insensitive per user

BEGIN;

-- Remove older duplicates, keeping the most recent copy for each title.
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, lower(title)
            ORDER BY created_at DESC, id DESC
        ) AS rn
    FROM notes
)
DELETE FROM notes
WHERE id IN (
    SELECT id FROM ranked WHERE rn > 1
);

-- Replace the windowed dedup index with strict uniqueness.
DROP INDEX IF EXISTS idx_notes_dedup;
DROP FUNCTION IF EXISTS floor_5_minutes(timestamptz);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notes_unique_title
ON notes (user_id, lower(title));

COMMIT;
