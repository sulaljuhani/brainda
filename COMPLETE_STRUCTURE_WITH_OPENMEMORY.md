# 🧠 Complete Local Stack with OpenMemory - Full Detailed Structure

## 📊 Enhanced System Architecture with OpenMemory

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ AnythingLLM UI   │  │   n8n UI         │  │  Todoist App     │ │
│  │ localhost:3001   │  │ localhost:5678   │  │  (Mobile/Web)    │ │
│  │                  │  │                  │  │                  │ │
│  │ - Chat           │  │ - Workflows      │  │ - Tasks          │ │
│  │ - Documents      │  │ - Monitoring     │  │ - Quick entry    │ │
│  │ - Agent tools    │  │ - Debugging      │  │ - Notifications  │ │
│  │ - Memory search  │  │ - Chat import    │  │                  │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│         ↓                      ↓                      ↓            │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ AnythingLLM (Container)                                       │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ • RAG Engine (retrieves from Qdrant + OpenMemory)            │  │
│  │ • Custom Skills (JavaScript)                                  │  │
│  │   ├─ create-reminder.js                                       │  │
│  │   ├─ create-task.js                                           │  │
│  │   ├─ create-event.js                                          │  │
│  │   ├─ search-memory.js         (NEW - OpenMemory search)      │  │
│  │   ├─ store-memory.js          (NEW - Save to OpenMemory)     │  │
│  │   └─ import-chat-history.js   (NEW - Import ChatGPT/Claude)  │  │
│  │ • MCP Client (connects to MCP server)                         │  │
│  │ • Vector Search Client (Qdrant + OpenMemory)                  │  │
│  │ • LLM Client (connects to Ollama)                             │  │
│  │ • Document Processor (20+ formats)                            │  │
│  │ • OpenMemory Client (stores conversations)                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 ↓                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ n8n (Container)                                               │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ • Workflow Engine                                             │  │
│  │ • Core Workflows:                                             │  │
│  │   ├─ create-reminder (webhook)                                │  │
│  │   ├─ create-task (webhook)                                    │  │
│  │   ├─ create-event (webhook)                                   │  │
│  │   ├─ fire-reminders (cron: */1 * * * *)                       │  │
│  │   ├─ daily-summary (cron: 0 7 * * *)                          │  │
│  │   ├─ todoist-sync (cron: */15 * * * *)                        │  │
│  │   ├─ google-calendar-sync (cron: */15 * * * *)                │  │
│  │   ├─ expand-recurring-tasks (cron: 0 0 * * *)                 │  │
│  │   ├─ watch-vault-files (file trigger: /vault)                 │  │
│  │   ├─ watch-documents (file trigger: /documents)               │  │
│  │   └─ cleanup-old-data (cron: 0 3 * * *)                       │  │
│  │                                                                │  │
│  │ • OpenMemory Workflows (NEW):                                 │  │
│  │   ├─ import-chatgpt-export (webhook/file trigger)             │  │
│  │   ├─ import-claude-export (webhook/file trigger)              │  │
│  │   ├─ import-gemini-export (webhook/file trigger)              │  │
│  │   ├─ store-chat-turn (webhook - called after each chat)       │  │
│  │   ├─ sync-memory-to-vault (cron: 0 */6 * * *)                 │  │
│  │   └─ enrich-memories (cron: 0 2 * * *)                        │  │
│  │                                                                │  │
│  │ • Node Types: 200+ built-in integrations                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 ↓                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ MCP Server (Container)                                        │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ • Database Tools (12 total):                                  │  │
│  │   ├─ get_reminders_today()                                    │  │
│  │   ├─ get_reminders_upcoming(days)                             │  │
│  │   ├─ search_reminders(query)                                  │  │
│  │   ├─ get_events_today()                                       │  │
│  │   ├─ get_events_upcoming(days)                                │  │
│  │   ├─ get_tasks_by_status(status)                              │  │
│  │   ├─ get_tasks_due_soon(days)                                 │  │
│  │   ├─ search_notes(query)                                      │  │
│  │   ├─ get_recent_notes(limit)                                  │  │
│  │   ├─ get_reminder_categories()                                │  │
│  │   ├─ get_day_summary()                                        │  │
│  │   └─ get_week_summary()                                       │  │
│  │                                                                │  │
│  │ • Memory Tools (NEW - 5 total):                               │  │
│  │   ├─ search_memories(query, sector)                           │  │
│  │   ├─ get_recent_memories(limit)                               │  │
│  │   ├─ get_conversation_context(conversation_id)                │  │
│  │   ├─ get_memory_by_id(memory_id)                              │  │
│  │   └─ get_related_memories(memory_id)                          │  │
│  │                                                                │  │
│  │ • Connection: stdio (IPC)                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 ↓                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ OpenMemory (Container) - Long-term AI Memory ⭐               │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ • Memory Storage & Retrieval                                  │  │
│  │   ├─ Stores conversations from ChatGPT, Claude, Gemini        │  │
│  │   ├─ Stores current AnythingLLM conversations                 │  │
│  │   ├─ Auto-classifies into sectors                             │  │
│  │   └─ Multi-dimensional embedding (2-3 sectors per memory)     │  │
│  │                                                                │  │
│  │ • Memory Sectors:                                             │  │
│  │   ├─ semantic: Facts, concepts, knowledge                     │  │
│  │   ├─ episodic: Events, experiences, interactions              │  │
│  │   ├─ procedural: How-tos, workflows, processes                │  │
│  │   ├─ emotional: Sentiment, feelings, preferences              │  │
│  │   └─ reflective: Insights, meta-cognition, patterns           │  │
│  │                                                                │  │
│  │ • Search & Retrieval:                                         │  │
│  │   ├─ Composite scoring: 60% similarity + 20% salience         │  │
│  │   │                      + 10% recency + 10% links            │  │
│  │   ├─ Cross-sector search                                      │  │
│  │   ├─ Temporal queries (memories from last week)               │  │
│  │   └─ Relationship mapping (linked memories)                   │  │
│  │                                                                │  │
│  │ • Import Formats Supported:                                   │  │
│  │   ├─ ChatGPT JSON export (conversations.json)                 │  │
│  │   ├─ Claude conversation export                               │  │
│  │   ├─ Gemini chat history                                      │  │
│  │   ├─ OpenAI API format                                        │  │
│  │   └─ Generic JSON (with mapping)                              │  │
│  │                                                                │  │
│  │ • Markdown Vault Sync (Optional):                             │  │
│  │   └─ Mirrors memories to /memory_vault/*.md files             │  │
│  │                                                                │  │
│  │ • API: REST (localhost:8080)                                  │  │
│  │ • Storage: PostgreSQL (metadata) + Qdrant (vectors)           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        AI/ML LAYER                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Ollama (Container)                                            │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ • LLM Models:                                                 │  │
│  │   ├─ llama3.2:3b (chat, 2GB RAM) - RECOMMENDED               │  │
│  │   ├─ llama3.1:8b (better quality, 5GB RAM)                    │  │
│  │   ├─ phi3:mini (fast, 2GB RAM)                                │  │
│  │   └─ mistral:7b (good balance, 4GB RAM)                       │  │
│  │                                                                │  │
│  │ • Embedding Models:                                           │  │
│  │   ├─ all-minilm (384 dims, fast) - RECOMMENDED               │  │
│  │   ├─ nomic-embed-text (768 dims, better quality)              │  │
│  │   └─ mxbai-embed-large (1024 dims, best quality)              │  │
│  │                                                                │  │
│  │ • API: REST (OpenAI compatible)                               │  │
│  │ • Port: 11434                                                 │  │
│  │ • Used by: AnythingLLM, n8n, OpenMemory                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────┐│
│  │ PostgreSQL          │  │ Qdrant              │  │ Redis       ││
│  │ (Port 5434)         │  │ (Port 6333)         │  │ (Port 6379) ││
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────┤│
│  │ Brainda DB:         │  │ Collections:        │  │ • n8n queue ││
│  │ • reminders         │  │  - knowledge_base   │  │ • Cache     ││
│  │ • tasks             │  │    (docs, notes)    │  │ • Sessions  ││
│  │ • events            │  │  - memories         │  │             ││
│  │ • notes             │  │    (OpenMemory)     │  │             ││
│  │ • documents         │  │                     │  │             ││
│  │ • chunks            │  │ Vector dims: 384    │  │             ││
│  │ • categories        │  │ Distance: Cosine    │  │             ││
│  │ • file_sync         │  │                     │  │             ││
│  │                     │  │ Payloads:           │  │             ││
│  │ OpenMemory DB:      │  │ • user_id filter    │  │             ││
│  │ • memories          │  │ • content_type      │  │             ││
│  │ • memory_sectors    │  │ • sector            │  │             ││
│  │ • conversations     │  │ • salience score    │  │             ││
│  │ • memory_links      │  │ • temporal data     │  │             ││
│  │ • embeddings        │  │                     │  │             ││
│  │                     │  │                     │  │             ││
│  │ n8n DB:             │  │                     │  │             ││
│  │ • workflows         │  │                     │  │             ││
│  │ • executions        │  │                     │  │             ││
│  │ • credentials       │  │                     │  │             ││
│  └─────────────────────┘  └─────────────────────┘  └─────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  /home/user/brainda/                                                │
│  ├─ vault/              (Markdown notes, auto-watched)              │
│  ├─ documents/          (PDFs, DOCX, auto-processed)                │
│  ├─ uploads/            (User uploads)                              │
│  ├─ memory_vault/       (OpenMemory markdown mirror) ⭐             │
│  ├─ chat_exports/       (ChatGPT/Claude JSON exports) ⭐            │
│  │   ├─ chatgpt/                                                    │
│  │   │   └─ conversations.json                                      │
│  │   ├─ claude/                                                     │
│  │   │   └─ export_2025-11-19.json                                  │
│  │   └─ gemini/                                                     │
│  │       └─ conversations_2025-11-19.json                           │
│  │                                                                  │
│  └─ Docker volumes:                                                 │
│      ├─ postgres_data/                                              │
│      ├─ qdrant_data/                                                │
│      ├─ redis_data/                                                 │
│      ├─ ollama_data/                                                │
│      ├─ anythingllm_data/                                           │
│      ├─ n8n_data/                                                   │
│      └─ openmemory_data/                                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Complete File System Structure with OpenMemory

```
/home/user/brainda/
│
├── 🐳 Docker Configuration
│   ├── docker-compose.local-stack.yml    # Main compose (8 services)
│   ├── .env.local-stack                   # Environment template
│   ├── .env                               # Your config (git-ignored)
│   └── .dockerignore
│
├── 🤖 MCP Server (Database + Memory Access)
│   └── mcp-server/
│       ├── Dockerfile                     # Python 3.11 slim
│       ├── requirements.txt               # mcp, asyncpg, httpx
│       └── server.py                      # 17 tools (12 DB + 5 memory)
│
├── 🎨 AnythingLLM Custom Skills
│   └── anythingllm-custom-skills/
│       ├── create-reminder.js             # Calls n8n webhook
│       ├── create-task.js                 # Calls n8n webhook
│       ├── create-event.js                # Calls n8n webhook
│       ├── search-memory.js       ⭐ NEW # Search OpenMemory
│       ├── store-memory.js        ⭐ NEW # Save to OpenMemory
│       └── import-chat-history.js ⭐ NEW # Import ChatGPT/Claude
│
├── 🔄 n8n Workflows (JSON exports)
│   └── n8n-workflows/
│       ├── Core Workflows:
│       ├── 01-create-reminder.json        # POST /webhook/create-reminder
│       ├── 02-create-task.json            # POST /webhook/create-task
│       ├── 03-create-event.json           # POST /webhook/create-event
│       ├── 04-fire-reminders.json         # Cron: */1 * * * *
│       ├── 05-daily-summary.json          # Cron: 0 7 * * *
│       ├── 06-todoist-sync.json           # Cron: */15 * * * *
│       ├── 07-google-calendar-sync.json   # Cron: */15 * * * *
│       ├── 08-expand-recurring-tasks.json # Cron: 0 0 * * *
│       ├── 09-watch-vault.json            # File trigger: /vault
│       ├── 10-watch-documents.json        # File trigger: /documents
│       ├── 11-cleanup-old-data.json       # Cron: 0 3 * * *
│       │
│       ├── OpenMemory Workflows: ⭐ NEW
│       ├── 12-import-chatgpt-export.json  # Import ChatGPT JSON
│       ├── 13-import-claude-export.json   # Import Claude conversations
│       ├── 14-import-gemini-export.json   # Import Gemini chats
│       ├── 15-store-chat-turn.json        # Save each chat message
│       ├── 16-sync-memory-to-vault.json   # Export memories to MD
│       ├── 17-enrich-memories.json        # Add salience, links
│       └── 18-search-and-summarize.json   # Memory-enhanced RAG
│
├── 📝 Configuration Files
│   ├── mcp-config.json                    # MCP server config
│   ├── openmemory-config.json     ⭐ NEW # OpenMemory settings
│   └── tailscale/
│       └── config.json                    # Tailscale VPN
│
├── 🗄️ Database Migrations
│   └── migrations/
│       ├── 001_initial_schema.sql
│       ├── 002_add_reminders.sql
│       ├── 003_add_tasks.sql
│       ├── 004_add_events.sql
│       ├── 005_add_categories.sql
│       ├── 006_add_documents.sql
│       ├── 007_add_todoist.sql
│       ├── 008_add_indexes.sql
│       └── 009_openmemory_schema.sql ⭐ NEW # OpenMemory tables
│
├── 📚 Data Directories (Mounted as Docker Volumes)
│   ├── vault/                             # Markdown notes
│   │   ├── daily/
│   │   ├── projects/
│   │   └── references/
│   │
│   ├── documents/                         # PDFs, DOCX
│   │   ├── research/
│   │   ├── receipts/
│   │   └── manuals/
│   │
│   ├── uploads/                           # Manual uploads
│   │
│   ├── memory_vault/              ⭐ NEW # OpenMemory markdown mirror
│   │   ├── semantic/                      # Factual knowledge
│   │   │   ├── 2025-11-19-python-concepts.md
│   │   │   └── 2025-11-20-docker-commands.md
│   │   ├── episodic/                      # Events & experiences
│   │   │   ├── 2025-11-19-project-discussion.md
│   │   │   └── 2025-11-20-debugging-session.md
│   │   ├── procedural/                    # How-tos
│   │   │   ├── 2025-11-19-setup-guide.md
│   │   │   └── 2025-11-20-workflow-creation.md
│   │   ├── emotional/                     # Preferences
│   │   │   └── 2025-11-19-user-preferences.md
│   │   └── reflective/                    # Insights
│   │       └── 2025-11-19-pattern-recognition.md
│   │
│   └── chat_exports/              ⭐ NEW # External chat imports
│       ├── chatgpt/
│       │   ├── conversations.json         # Full ChatGPT export
│       │   ├── imported/                  # Processed flag files
│       │   └── archive/                   # Backup of originals
│       ├── claude/
│       │   ├── export_2025-11-19.json
│       │   ├── export_2025-11-18.json
│       │   └── imported/
│       ├── gemini/
│       │   └── conversations_2025-11-19.json
│       └── custom/                        # Generic JSON imports
│           └── other_ai_chats.json
│
├── 📖 Documentation
│   ├── README.md
│   ├── CLAUDE.md
│   ├── LOCAL_STACK_SETUP.md
│   ├── ARCHITECTURE_COMPARISON.md
│   ├── TECHNICAL_FEATURES.md
│   ├── DOCKER_SETUP.md
│   └── OPENMEMORY_GUIDE.md        ⭐ NEW # OpenMemory usage guide
│
├── 🧪 Testing
│   └── tests/
│       ├── stage_runner.sh
│       ├── common.sh
│       ├── stage*.sh
│       └── test_openmemory.sh     ⭐ NEW # Memory integration tests
│
└── 🔧 Utility Scripts
    └── scripts/
        ├── backup.sh
        ├── restore.sh
        ├── bulk_embed.py
        ├── export_workflows.sh
        ├── import_chatgpt.py      ⭐ NEW # ChatGPT JSON importer
        ├── import_claude.py       ⭐ NEW # Claude export importer
        ├── export_memories.py     ⭐ NEW # Export to markdown
        └── enrich_memories.py     ⭐ NEW # Add salience scores
```

---

## 🗄️ Enhanced Database Schema with OpenMemory

### **OpenMemory Tables (New Database: `openmemory`)**

```sql
-- Memory Core Table
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,                       -- User isolation
    content TEXT NOT NULL,                        -- The actual memory text
    memory_type TEXT DEFAULT 'explicit',          -- explicit, implicit, inferred
    source TEXT DEFAULT 'chat',                   -- chat, import, api, system
    source_reference TEXT,                        -- conversation_id, import_file, etc.
    salience_score FLOAT DEFAULT 0.5,            -- Importance: 0.0 - 1.0
    access_count INTEGER DEFAULT 0,               -- How many times retrieved
    last_accessed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB                                -- Extra context
);

CREATE INDEX idx_memories_user ON memories(user_id);
CREATE INDEX idx_memories_salience ON memories(salience_score DESC);
CREATE INDEX idx_memories_source ON memories(source);
CREATE INDEX idx_memories_created ON memories(created_at DESC);

-- Memory Sectors (Multi-dimensional classification)
CREATE TABLE memory_sectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    sector TEXT NOT NULL,                         -- semantic, episodic, procedural, emotional, reflective
    confidence FLOAT DEFAULT 1.0,                 -- Classification confidence
    embedding_id TEXT,                            -- Qdrant point ID for this sector
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(memory_id, sector)
);

CREATE INDEX idx_sectors_memory ON memory_sectors(memory_id);
CREATE INDEX idx_sectors_type ON memory_sectors(sector);

-- Conversations (Groups related memories)
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title TEXT,
    source TEXT,                                  -- anythingllm, chatgpt, claude, gemini
    external_id TEXT,                             -- Original conversation ID
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_source ON conversations(source);
CREATE INDEX idx_conversations_external ON conversations(external_id);

-- Memory Links (Relationships between memories)
CREATE TABLE memory_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    to_memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL,                      -- similar, contradicts, elaborates, caused_by, etc.
    strength FLOAT DEFAULT 0.5,                   -- Link strength: 0.0 - 1.0
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(from_memory_id, to_memory_id, link_type)
);

CREATE INDEX idx_links_from ON memory_links(from_memory_id);
CREATE INDEX idx_links_to ON memory_links(to_memory_id);
CREATE INDEX idx_links_type ON memory_links(link_type);

-- Imported Chat Metadata (Track what's been imported)
CREATE TABLE imported_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    source TEXT NOT NULL,                         -- chatgpt, claude, gemini
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,                      -- SHA-256 of file
    conversations_count INTEGER,
    memories_created INTEGER,
    imported_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, file_hash)                   -- Prevent duplicate imports
);

CREATE INDEX idx_imports_user ON imported_chats(user_id);
CREATE INDEX idx_imports_source ON imported_chats(source);
CREATE INDEX idx_imports_hash ON imported_chats(file_hash);
```

---

## 🔷 Enhanced Qdrant Collections with OpenMemory

### **Collection 1: `knowledge_base`** (Documents, Notes, Tasks)

```json
{
  "name": "knowledge_base",
  "config": {
    "params": {
      "vectors": {
        "size": 384,
        "distance": "Cosine"
      }
    }
  },
  "payload_schema": {
    "user_id": {"type": "keyword", "indexed": true},
    "content_type": {
      "type": "keyword",
      "values": ["note", "document_chunk", "reminder", "task", "event"]
    },
    "source_id": {"type": "keyword"},
    "title": {"type": "text"},
    "text": {"type": "text"},
    "created_at": {"type": "datetime"},
    "embedded_at": {"type": "datetime"}
  }
}
```

### **Collection 2: `memories`** (OpenMemory - Multi-Sector) ⭐ NEW

```json
{
  "name": "memories",
  "config": {
    "params": {
      "vectors": {
        "size": 384,
        "distance": "Cosine"
      }
    },
    "optimizers_config": {
      "indexing_threshold": 10000
    }
  },
  "payload_schema": {
    "user_id": {
      "type": "keyword",
      "indexed": true
    },
    "memory_id": {
      "type": "keyword",
      "indexed": true
    },
    "sector": {
      "type": "keyword",
      "indexed": true,
      "values": ["semantic", "episodic", "procedural", "emotional", "reflective"]
    },
    "content": {
      "type": "text"
    },
    "salience_score": {
      "type": "float",
      "indexed": true
    },
    "access_count": {
      "type": "integer"
    },
    "source": {
      "type": "keyword",
      "values": ["anythingllm", "chatgpt", "claude", "gemini", "api"]
    },
    "conversation_id": {
      "type": "keyword"
    },
    "created_at": {
      "type": "datetime",
      "indexed": true
    },
    "last_accessed_at": {
      "type": "datetime"
    },
    "tags": {
      "type": "keyword[]"
    },
    "entities": {
      "type": "keyword[]"
    },
    "linked_memory_ids": {
      "type": "keyword[]"
    }
  }
}
```

### **Example Memory Point (ChatGPT Import)**

```json
{
  "id": "chatgpt_conv123_turn5_semantic",
  "vector": [0.123, -0.456, ..., 0.789],
  "payload": {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "memory_id": "memory_uuid-456",
    "sector": "semantic",
    "content": "Python list comprehensions are faster than for loops because they're optimized at the bytecode level",
    "salience_score": 0.85,
    "access_count": 0,
    "source": "chatgpt",
    "conversation_id": "chatgpt_conv123",
    "created_at": "2025-11-19T10:30:00Z",
    "tags": ["python", "performance", "programming"],
    "entities": ["Python", "list comprehension"],
    "linked_memory_ids": []
  }
}
```

---

## 🔄 Complete Data Flow: ChatGPT Import to OpenMemory

### **Scenario: Import ChatGPT Export and Use in Current Conversations**

```
════════════════════════════════════════════════════════════════════
STEP 1: EXPORT FROM CHATGPT
════════════════════════════════════════════════════════════════════

User actions:
1. Go to ChatGPT Settings → Data Controls → Export Data
2. Wait for email with download link
3. Download conversations.json
4. Save to: /home/user/brainda/chat_exports/chatgpt/conversations.json

File structure (conversations.json):
[
  {
    "id": "conv-abc123",
    "title": "Python optimization tips",
    "create_time": 1700000000,
    "update_time": 1700001000,
    "mapping": {
      "msg-1": {
        "message": {
          "author": {"role": "user"},
          "content": {"parts": ["How can I optimize Python code?"]}
        }
      },
      "msg-2": {
        "message": {
          "author": {"role": "assistant"},
          "content": {"parts": ["Here are 5 ways to optimize Python..."]}
        }
      }
    }
  },
  ... (100s more conversations)
]

════════════════════════════════════════════════════════════════════
STEP 2: N8N DETECTS NEW FILE
════════════════════════════════════════════════════════════════════

Workflow: n8n-workflows/12-import-chatgpt-export.json

[File Trigger] - Watches /chat_exports/chatgpt/*.json
├─ Triggers on: conversations.json
└─ Mode: Poll every 5 minutes

[Hash Check] - Calculate SHA-256
├─ Calculate file hash
├─ Query: SELECT 1 FROM imported_chats WHERE file_hash = $1
└─ If exists → Skip (already imported)

[Read JSON File]
├─ Read entire conversations.json
├─ Parse JSON
└─ Output: Array of conversation objects

[Function: Extract Conversations]
Code:
```javascript
const conversations = $input.item.json;
const extracted = [];

for (const conv of conversations) {
  const messages = [];

  // Parse mapping structure
  for (const [key, value] of Object.entries(conv.mapping)) {
    if (value.message) {
      messages.push({
        role: value.message.author.role,
        content: value.message.content.parts.join('\n'),
        timestamp: value.message.create_time
      });
    }
  }

  extracted.push({
    conversation_id: conv.id,
    title: conv.title,
    created_at: new Date(conv.create_time * 1000),
    messages: messages
  });
}

return extracted.map(c => ({json: c}));
```

Output: Array of parsed conversations

[Split into Batches] - Process 10 conversations at a time
└─ Prevents timeout, memory issues

════════════════════════════════════════════════════════════════════
STEP 3: STORE IN OPENMEMORY DATABASE
════════════════════════════════════════════════════════════════════

[Loop: For Each Conversation]

  [PostgreSQL: Insert Conversation]
  SQL:
  INSERT INTO conversations (id, user_id, title, source, external_id, started_at, message_count)
  VALUES (gen_random_uuid(), $1, $2, 'chatgpt', $3, $4, $5)
  RETURNING id

  [Loop: For Each Message in Conversation]

    [Function: Extract Memory]
    Code:
    ```javascript
    const memory = {
      content: $json.content,
      user_id: $env.DEFAULT_USER_ID,
      memory_type: 'explicit',
      source: 'chatgpt',
      source_reference: $json.conversation_id,
      salience_score: 0.5  // Will be enriched later
    };
    return memory;
    ```

    [PostgreSQL: Insert Memory]
    SQL:
    INSERT INTO memories (user_id, content, source, source_reference, salience_score)
    VALUES ($1, $2, 'chatgpt', $3, 0.5)
    RETURNING id

    [Function: Classify Sectors]
    Code:
    ```javascript
    // Simple keyword-based classification (can use LLM for better results)
    const content = $json.content.toLowerCase();
    const sectors = [];

    // Semantic: Facts, definitions, explanations
    if (content.match(/is|are|means|definition|concept/)) {
      sectors.push('semantic');
    }

    // Episodic: Events, experiences, "I did", "We worked"
    if (content.match(/\b(i|we|you)\s+(did|made|worked|tried|fixed)/)) {
      sectors.push('episodic');
    }

    // Procedural: How-tos, steps, instructions
    if (content.match(/how to|step|first|then|next|install|configure/)) {
      sectors.push('procedural');
    }

    // Emotional: Preferences, feelings
    if (content.match(/prefer|like|hate|love|frustrat|enjoy/)) {
      sectors.push('emotional');
    }

    // Reflective: Insights, patterns, meta-cognition
    if (content.match(/realize|understand|pattern|insight|learn/)) {
      sectors.push('reflective');
    }

    // Default to semantic if nothing matched
    if (sectors.length === 0) sectors.push('semantic');

    return sectors.map(s => ({sector: s, memory_id: $json.memory_id}));
    ```

    [Loop: For Each Sector]

      [PostgreSQL: Insert Sector]
      SQL:
      INSERT INTO memory_sectors (memory_id, sector, confidence)
      VALUES ($1, $2, 0.8)
      RETURNING id

      [HTTP: Generate Embedding]
      POST http://ollama:11434/api/embeddings
      Body: {
        "model": "all-minilm",
        "prompt": $json.content
      }

      [HTTP: Store in Qdrant]
      PUT http://qdrant:6333/collections/memories/points
      Body: {
        "points": [{
          "id": "${memory_id}_${sector}",
          "vector": $json.embedding,
          "payload": {
            "user_id": $env.DEFAULT_USER_ID,
            "memory_id": $json.memory_id,
            "sector": $json.sector,
            "content": $json.content,
            "salience_score": 0.5,
            "source": "chatgpt",
            "conversation_id": $json.conversation_id,
            "created_at": $json.created_at
          }
        }]
      }

      [PostgreSQL: Update Sector with Embedding ID]
      UPDATE memory_sectors
      SET embedding_id = $1
      WHERE id = $2

════════════════════════════════════════════════════════════════════
STEP 4: TRACK IMPORT
════════════════════════════════════════════════════════════════════

[PostgreSQL: Record Import]
SQL:
INSERT INTO imported_chats (user_id, source, file_path, file_hash, conversations_count, memories_created)
VALUES ($1, 'chatgpt', '/chat_exports/chatgpt/conversations.json', $2, $3, $4)

[Move File to Archive]
mv /chat_exports/chatgpt/conversations.json
   /chat_exports/chatgpt/archive/conversations_2025-11-19.json

[Create Import Flag]
touch /chat_exports/chatgpt/imported/conversations.json.imported

════════════════════════════════════════════════════════════════════
STEP 5: ENRICH MEMORIES (Background Job)
════════════════════════════════════════════════════════════════════

Workflow: n8n-workflows/17-enrich-memories.json
Trigger: Daily at 2am

[PostgreSQL: Get Recent Memories]
SELECT * FROM memories
WHERE salience_score = 0.5  -- Default, not yet enriched
AND created_at > NOW() - INTERVAL '1 day'
LIMIT 100

[For Each Memory]

  [LLM: Calculate Salience]
  POST http://ollama:11434/api/generate
  Prompt:
  ```
  Rate the importance/salience of this memory from 0.0 to 1.0:

  Memory: "${content}"

  Consider:
  - Uniqueness (rare vs common knowledge)
  - Specificity (specific vs general)
  - Actionability (can be applied)
  - Emotional weight

  Return only a number between 0.0 and 1.0:
  ```

  [Update Salience Score]
  UPDATE memories SET salience_score = $1 WHERE id = $2

  [Update Qdrant Payload]
  POST http://qdrant:6333/collections/memories/points/payload
  Body: {
    "points": ["${memory_id}_semantic"],
    "payload": {
      "salience_score": $json.salience_score
    }
  }

════════════════════════════════════════════════════════════════════
STEP 6: USE IN CURRENT CONVERSATION
════════════════════════════════════════════════════════════════════

User: "What did I learn about Python optimization?"

AnythingLLM Agent:
├─ Detects query about past knowledge
├─ Generates query embedding
│
├─ [Parallel Search]
│  │
│  ├─ [Qdrant: Search Documents]
│  │  POST /collections/knowledge_base/points/search
│  │  {
│  │    "vector": [query_embedding],
│  │    "filter": {"must": [{"key": "user_id", "match": {"value": "..."}}]},
│  │    "limit": 3
│  │  }
│  │  Result: 0 matches (no recent documents about Python optimization)
│  │
│  └─ [Qdrant: Search Memories]
│     POST /collections/memories/points/search
│     {
│       "vector": [query_embedding],
│       "filter": {
│         "must": [
│           {"key": "user_id", "match": {"value": "..."}},
│           {"key": "sector", "match": {"value": "semantic"}}
│         ]
│       },
│       "limit": 5,
│       "score_threshold": 0.6
│     }
│
│     Results (sorted by composite score):
│     1. "Python list comprehensions are faster..." (0.89, salience: 0.85)
│     2. "Use generators for memory efficiency..." (0.87, salience: 0.75)
│     3. "Numba JIT compilation speeds up loops..." (0.82, salience: 0.70)
│
├─ [Construct Context]
│  Context from memories (ChatGPT import):
│  ```
│  Relevant past knowledge:
│
│  1. From conversation on 2024-05-15:
│     "Python list comprehensions are faster than for loops because
│      they're optimized at the bytecode level"
│
│  2. From conversation on 2024-06-20:
│     "Use generators for memory efficiency when processing large
│      datasets - they don't load everything into memory"
│
│  3. From conversation on 2024-07-10:
│     "Numba JIT compilation can speed up numerical loops by 50-100x"
│  ```
│
├─ [LLM Generation]
│  POST http://ollama:11434/api/chat
│  Model: llama3.2:3b
│  Messages: [
│    {role: "system", content: "You have access to user's past conversations..."},
│    {role: "user", content: "What did I learn about Python optimization?"},
│    {role: "assistant", content: [Generated with context]}
│  ]
│
└─ Response:
   "Based on your previous conversations, you learned several Python
    optimization techniques:

    1. **List Comprehensions**: You discovered they're faster than
       traditional for loops due to bytecode-level optimizations.

    2. **Generators**: You learned to use generators for memory-efficient
       processing of large datasets.

    3. **Numba JIT**: You explored Numba for speeding up numerical
       computations by 50-100x.

    Would you like me to elaborate on any of these, or explore new
    optimization techniques?"

════════════════════════════════════════════════════════════════════
STEP 7: STORE CURRENT CONVERSATION IN OPENMEMORY
════════════════════════════════════════════════════════════════════

After each chat turn in AnythingLLM:

Workflow: n8n-workflows/15-store-chat-turn.json
Trigger: Webhook called by AnythingLLM after each message

[Webhook] POST /webhook/store-chat-turn
Body: {
  "user_message": "What did I learn about Python optimization?",
  "assistant_response": "Based on your previous conversations...",
  "conversation_id": "anythingllm_conv789",
  "user_id": "00000000-0000-0000-0000-000000000001"
}

[Insert User Message as Memory]
[Insert Assistant Response as Memory]
[Classify Sectors]
[Generate Embeddings]
[Store in Qdrant]

Now future queries can reference BOTH ChatGPT AND AnythingLLM conversations!
```

---

## 📂 Chat Export Format Examples

### **ChatGPT Export Format**

```json
{
  "conversations.json": [
    {
      "id": "conv-abc123",
      "title": "Python optimization tips",
      "create_time": 1700000000,
      "update_time": 1700001000,
      "mapping": {
        "msg-uuid-1": {
          "id": "msg-uuid-1",
          "message": {
            "id": "msg-uuid-1",
            "author": {"role": "user"},
            "create_time": 1700000000,
            "content": {
              "content_type": "text",
              "parts": ["How can I optimize Python code?"]
            }
          }
        },
        "msg-uuid-2": {
          "id": "msg-uuid-2",
          "message": {
            "id": "msg-uuid-2",
            "author": {"role": "assistant"},
            "create_time": 1700000100,
            "content": {
              "content_type": "text",
              "parts": [
                "Here are 5 ways to optimize Python code:\n\n1. Use list comprehensions...\n2. Profile with cProfile...\n3. Use generators for large datasets...\n4. Leverage NumPy for numerical operations...\n5. Consider Cython for performance-critical code..."
              ]
            }
          }
        }
      }
    }
  ]
}
```

### **Claude Export Format**

```json
{
  "conversations": [
    {
      "uuid": "conv-xyz789",
      "name": "Docker optimization",
      "created_at": "2025-11-19T10:00:00.000Z",
      "updated_at": "2025-11-19T11:30:00.000Z",
      "chat_messages": [
        {
          "uuid": "msg-1",
          "text": "How can I optimize Docker builds?",
          "sender": "human",
          "created_at": "2025-11-19T10:00:00.000Z"
        },
        {
          "uuid": "msg-2",
          "text": "Here are key strategies for optimizing Docker builds:\n\n1. **Multi-stage builds**: Separate build and runtime stages...\n2. **Layer caching**: Order Dockerfile commands by change frequency...\n3. **`.dockerignore`**: Exclude unnecessary files...",
          "sender": "assistant",
          "created_at": "2025-11-19T10:01:00.000Z"
        }
      ]
    }
  ]
}
```

### **Gemini Export Format**

```json
{
  "conversations": [
    {
      "conversation_id": "conv-gemini-123",
      "conversation": {
        "id": "conv-gemini-123",
        "create_time": "2025-11-19T09:00:00Z",
        "update_time": "2025-11-19T09:30:00Z"
      },
      "messages": [
        {
          "author": "user",
          "text": "Explain quantum computing",
          "create_time": "2025-11-19T09:00:00Z"
        },
        {
          "author": "model",
          "text": "Quantum computing leverages quantum mechanics principles like superposition and entanglement...",
          "create_time": "2025-11-19T09:00:30Z"
        }
      ]
    }
  ]
}
```

---

## 🔄 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ EXTERNAL CHAT SERVICES                                       │
├─────────────────────────────────────────────────────────────┤
│ • ChatGPT (conversations.json export)                       │
│ • Claude (JSON export)                                      │
│ • Gemini (conversation history)                             │
│ • Other AI services                                         │
└─────────────────────────────────────────────────────────────┘
                    ↓ Export JSON files
┌─────────────────────────────────────────────────────────────┐
│ /chat_exports/                                              │
│ ├─ chatgpt/conversations.json                               │
│ ├─ claude/export_2025-11-19.json                            │
│ └─ gemini/conversations.json                                │
└─────────────────────────────────────────────────────────────┘
                    ↓ File trigger (every 5 min)
┌─────────────────────────────────────────────────────────────┐
│ n8n Workflow: Import Chat History                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Detect new file                                          │
│ 2. Check hash (avoid duplicates)                            │
│ 3. Parse JSON (format-specific parser)                      │
│ 4. Extract conversations & messages                         │
│ 5. For each message:                                        │
│    ├─ Insert to PostgreSQL (memories table)                 │
│    ├─ Classify sectors (semantic/episodic/etc)              │
│    ├─ Generate embedding (Ollama)                           │
│    └─ Store in Qdrant (memories collection)                 │
│ 6. Track import (imported_chats table)                      │
│ 7. Move file to archive                                     │
└─────────────────────────────────────────────────────────────┘
                    ↓ Stored in
┌────────────────────────────────┬────────────────────────────┐
│ PostgreSQL (openmemory DB)     │ Qdrant (memories)          │
├────────────────────────────────┼────────────────────────────┤
│ • memories (content, metadata) │ • Multi-sector vectors     │
│ • memory_sectors (classification) │ • User filtering       │
│ • conversations (groups)       │ • Salience scoring         │
│ • memory_links (relationships) │ • Temporal indexing        │
└────────────────────────────────┴────────────────────────────┘
                    ↓ Retrieved during
┌─────────────────────────────────────────────────────────────┐
│ Current AnythingLLM Conversation                            │
├─────────────────────────────────────────────────────────────┤
│ User: "What did I learn about Python?"                      │
│   ↓                                                          │
│ AnythingLLM Agent:                                          │
│ ├─ Generate query embedding                                 │
│ ├─ Search Qdrant (knowledge_base + memories)                │
│ │  ├─ Documents: 0 results                                  │
│ │  └─ Memories: 5 results (from ChatGPT import)             │
│ ├─ Retrieve memory content from PostgreSQL                  │
│ ├─ Construct context with citations                         │
│ └─ Generate response with LLM                               │
│   ↓                                                          │
│ Response: "Based on your conversation on 2024-05-15..."     │
│   ↓                                                          │
│ n8n Workflow: Store Current Turn                            │
│ ├─ Save user question as memory                             │
│ ├─ Save assistant response as memory                        │
│ ├─ Link to current conversation                             │
│ └─ Embed and store in Qdrant                                │
└─────────────────────────────────────────────────────────────┘
                    ↓ Optionally
┌─────────────────────────────────────────────────────────────┐
│ Memory Vault Sync (n8n workflow, every 6 hours)            │
├─────────────────────────────────────────────────────────────┤
│ 1. Query recent memories from PostgreSQL                    │
│ 2. Group by sector                                          │
│ 3. Format as markdown                                       │
│ 4. Write to /memory_vault/{sector}/{date}-{title}.md        │
│ 5. Create YAML frontmatter with metadata                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Benefits

### **All Your AI Conversations in ONE Place**
- ✅ ChatGPT, Claude, Gemini, and AnythingLLM conversations all searchable
- ✅ No more context switching between different AI services
- ✅ Build on past knowledge across all platforms

### **Smart Memory Organization**
- ✅ Multi-sector classification (semantic, episodic, procedural, emotional, reflective)
- ✅ Salience scoring (important memories surface first)
- ✅ Memory linking (related concepts connected automatically)
- ✅ Temporal queries ("what did I learn last month?")

### **100% Local & Private**
- ✅ All data stays on your machine
- ✅ No cloud dependencies
- ✅ Complete control over your knowledge base
- ✅ Works offline

### **Future-Proof**
- ✅ Import from any AI service (extensible parsers)
- ✅ Export to markdown (portable, version controlled)
- ✅ PostgreSQL + Qdrant (industry-standard storage)
- ✅ Open-source stack (no vendor lock-in)

---

## 🚀 Next Steps

1. **Set up the stack**: Follow `LOCAL_STACK_SETUP.md`
2. **Export your conversations**: Download from ChatGPT, Claude, Gemini
3. **Drop files in `/chat_exports/`**: n8n automatically processes
4. **Start chatting**: Ask "What have I learned about X?" and watch the magic!

---

**This is your complete, detailed structure with OpenMemory fully integrated for a unified AI knowledge base!**
