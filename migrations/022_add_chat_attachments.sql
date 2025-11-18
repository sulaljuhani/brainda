-- Add attachments column to chat_messages
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS attachments JSONB DEFAULT '[]'::jsonb;

-- Create index for querying messages with attachments
CREATE INDEX IF NOT EXISTS idx_chat_messages_attachments
ON chat_messages USING gin (attachments);

-- Create chat_files table for tracking uploaded files
CREATE TABLE IF NOT EXISTS chat_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES chat_conversations(id) ON DELETE CASCADE,
    message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,

    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,

    -- Processing metadata
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    processed_at TIMESTAMPTZ,
    error_message TEXT,

    -- Extracted content
    extracted_text TEXT,
    embedding_id UUID,  -- Reference to Qdrant point if embedded

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_chat_files_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_files_conversation FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_files_message FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_files_user_id ON chat_files(user_id);
CREATE INDEX idx_chat_files_conversation_id ON chat_files(conversation_id);
CREATE INDEX idx_chat_files_message_id ON chat_files(message_id);
CREATE INDEX idx_chat_files_status ON chat_files(status);
