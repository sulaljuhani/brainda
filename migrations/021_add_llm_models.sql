-- Migration: Add LLM models table for multi-model support
-- Allows users to configure multiple LLM providers and switch between them

CREATE TABLE IF NOT EXISTS llm_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL, -- openai, anthropic, ollama, custom, etc.
    model_name VARCHAR(255) NOT NULL, -- e.g., gpt-4, claude-3-5-sonnet-20241022, llama3

    -- Configuration (stored as JSON for flexibility)
    config JSONB NOT NULL DEFAULT '{}', -- api_key, base_url, headers, etc. (encrypted sensitive data)

    -- Settings
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER,

    -- Metadata
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Ensure unique names per user
    CONSTRAINT llm_models_user_name_unique UNIQUE (user_id, name)
);

-- Index for fast lookups
CREATE INDEX idx_llm_models_user_id ON llm_models(user_id);
CREATE INDEX idx_llm_models_default ON llm_models(user_id, is_default) WHERE is_default = TRUE;

-- Add model_id to chat_conversations to remember which model was used
ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES llm_models(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_chat_conversations_model_id ON chat_conversations(model_id);

-- Add model_id to chat_messages for tracking
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES llm_models(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_chat_messages_model_id ON chat_messages(model_id);
