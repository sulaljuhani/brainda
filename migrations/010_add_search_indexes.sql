-- Migration 010: Add indexes to improve search performance
-- This migration adds indexes for faster keyword search on documents and chunks

-- Add B-tree index on documents status for faster filtered queries
CREATE INDEX IF NOT EXISTS idx_documents_status_user
ON documents (user_id, status) WHERE status = 'indexed';

-- Add B-tree index on chunks.document_id for faster joins
CREATE INDEX IF NOT EXISTS idx_chunks_document_id
ON chunks (document_id);

-- Add index on documents filename for faster ILIKE queries
CREATE INDEX IF NOT EXISTS idx_documents_filename_lower
ON documents (lower(filename));

-- Note: For production, consider enabling pg_trgm extension for trigram-based LIKE queries:
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- Then create GIN indexes:
-- CREATE INDEX idx_documents_filename_gin ON documents USING gin (lower(filename) gin_trgm_ops);
-- CREATE INDEX idx_chunks_text_gin ON chunks USING gin (lower(text) gin_trgm_ops);
