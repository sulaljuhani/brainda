-- Stage 1: Notes, file sync, and audit log

-- Notes table
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT,
    tags TEXT[] DEFAULT '{}',
    md_path TEXT UNIQUE, -- relative to vault root, e.g. 'notes/test.md'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- File sync state (tracks Markdown files for embeddings)
CREATE TABLE IF NOT EXISTS file_sync_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL, -- relative to vault, e.g. 'notes/test.md'
    content_hash TEXT NOT NULL, -- SHA256 of content
    last_modified_at TIMESTAMPTZ NOT NULL,
    last_embedded_at TIMESTAMPTZ,
    embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2:1',
    vector_id TEXT, -- Qdrant point ID
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, file_path)
);

-- Audit log (for debugging and tracking changes)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    entity_type TEXT NOT NULL, -- 'note', 'reminder', etc.
    entity_id UUID NOT NULL,
    action TEXT NOT NULL, -- 'create', 'update', 'delete'
    old_value JSONB,
    new_value JSONB,
    source TEXT, -- 'api', 'worker', 'sync', 'obsidian'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages (optional, for history)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    metadata JSONB, -- tool calls, citations, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- CRITICAL: Deduplication constraints
-- Prevents duplicate notes from retries (5-minute window)
-- This index is created in 002_fix_dedup_index.sql

-- One sync state per file per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_file_sync_path
ON file_sync_state(user_id, file_path);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_file_sync_user_path ON file_sync_state(user_id, file_path);
CREATE INDEX IF NOT EXISTS idx_file_sync_embedding_model ON file_sync_state(embedding_model);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages(user_id, created_at);
