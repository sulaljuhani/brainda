-- Stage 1: Fix for deduplication index (again)

-- Drop the failing index
DROP INDEX IF EXISTS idx_notes_dedup;

-- Create an immutable function to calculate the 5-minute interval
CREATE OR REPLACE FUNCTION floor_5_minutes(ts timestamptz)
RETURNS timestamptz AS $$
BEGIN
    RETURN date_trunc('hour', ts) + floor(EXTRACT(minute FROM ts) / 5) * '5 minutes'::interval;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Recreate the index using the immutable function
CREATE UNIQUE INDEX idx_notes_dedup
ON notes (
    user_id,
    title,
    floor_5_minutes(created_at)
);
