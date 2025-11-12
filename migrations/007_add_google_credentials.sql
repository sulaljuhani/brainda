-- Stage 7: Google Calendar OAuth credentials storage

CREATE TABLE IF NOT EXISTS google_credentials (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    encrypted_credentials TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_google_credentials_updated_at
    ON google_credentials(updated_at DESC);
