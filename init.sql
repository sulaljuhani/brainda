-- Initial schema for Stage 0
-- More tables will be added in later stages

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (single user for MVP)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT, -- NULL for API token only auth
    api_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Devices table (for push notifications)
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL, -- web, ios, android
    push_token TEXT,
    push_endpoint TEXT, -- for Web Push
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feature flags
CREATE TABLE feature_flags (
    key TEXT PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_devices_user ON devices(user_id);
CREATE INDEX idx_devices_token ON devices(push_token) WHERE push_token IS NOT NULL;

-- Insert default feature flags
INSERT INTO feature_flags (key, enabled, description) VALUES
('chat', true, 'Enable chat interface'),
('reminders', false, 'Enable reminders (Stage 2)'),
('documents', false, 'Enable document ingestion (Stage 3)');

-- ============================================================
-- Stage 1 schema: notes, file sync state, audit log, messages
-- ============================================================

-- Notes table
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT,
    tags TEXT[] DEFAULT '{}',
    md_path TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- File sync state (tracks Markdown files for embeddings)
CREATE TABLE IF NOT EXISTS file_sync_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    last_modified_at TIMESTAMPTZ NOT NULL,
    last_embedded_at TIMESTAMPTZ,
    embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2:1',
    vector_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, file_path)
);

-- Audit log (for debugging and tracking changes)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    action TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages (optional, for history)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_file_sync_path ON file_sync_state(user_id, file_path);
CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(user_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notes_unique_title ON notes(user_id, lower(title));
CREATE INDEX IF NOT EXISTS idx_file_sync_user_path ON file_sync_state(user_id, file_path);
CREATE INDEX IF NOT EXISTS idx_file_sync_embedding_model ON file_sync_state(embedding_model);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages(user_id, created_at);
