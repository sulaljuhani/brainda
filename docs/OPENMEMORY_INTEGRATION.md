# OpenMemory Integration Guide

This document describes the OpenMemory integration in Brainda, which provides long-term AI memory capabilities for enhanced conversational experiences.

## Overview

OpenMemory is integrated into Brainda to provide:

- **Persistent Conversation Memory**: Automatically stores chat interactions for context continuity
- **Semantic Memory Search**: Retrieves relevant past conversations based on current queries
- **Enhanced RAG**: Combines document search (Qdrant) with conversation history (OpenMemory)
- **Explicit Memory Storage**: Store facts, preferences, and events that should be remembered

## Architecture

### Components

1. **OpenMemory Adapter** (`app/api/adapters/openmemory_adapter.py`)
   - HTTP client for OpenMemory API
   - Handles authentication, retries, and error handling
   - Provides methods for storing/searching memories

2. **Memory Service** (`app/api/services/memory_service.py`)
   - High-level business logic for memory operations
   - Integrates with OpenMemory adapter
   - Gracefully handles disabled/unavailable states

3. **Enhanced RAG Service** (`app/api/services/rag_service.py`)
   - Automatically retrieves conversation context from OpenMemory
   - Combines with document/note context from Qdrant
   - Stores chat interactions for future reference

4. **Memory API Endpoints** (`app/api/routers/memory.py`)
   - RESTful API for memory operations
   - User-scoped memory isolation
   - Health checks and debugging tools

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# OpenMemory Integration
OPENMEMORY_URL=http://localhost:8080
OPENMEMORY_API_KEY=your-api-key-if-required
OPENMEMORY_ENABLED=true
```

### Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENMEMORY_URL` | OpenMemory server URL | `http://localhost:8080` |
| `OPENMEMORY_API_KEY` | API key for authentication (optional) | Empty |
| `OPENMEMORY_ENABLED` | Enable/disable integration | `true` |

## Usage

### Automatic Memory (RAG Chat)

When using the chat endpoint (`POST /api/v1/chat`), OpenMemory is automatically used:

1. **Retrieval Phase**: Searches OpenMemory for relevant past conversations
2. **Context Building**: Combines OpenMemory context with Qdrant document search
3. **LLM Response**: Generates answer using both contexts
4. **Storage Phase**: Stores the conversation turn in OpenMemory

Example chat request:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What did we discuss about the project timeline?",
    "conversation_id": "optional-conversation-id"
  }'
```

Response includes:

```json
{
  "answer": "Based on our previous discussion...",
  "citations": [...],
  "sources_used": 3,
  "memory_used": true
}
```

### Manual Memory Operations

#### Store a Memory

Store explicit facts, preferences, or events:

```bash
curl -X POST http://localhost:8000/api/v1/memory \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers dark mode for all applications",
    "tags": ["preference", "ui"],
    "metadata": {
      "category": "ui_settings",
      "source": "user_profile"
    }
  }'

# Response will include sectors:
# {
#   "success": true,
#   "data": {
#     "id": "memory_uuid",
#     "content": "User prefers dark mode for all applications",
#     "sectors": ["semantic", "procedural"],
#     ...
#   }
# }
```

#### Search Memories

Search for relevant memories semantically:

```bash
# Basic search
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the user interface preferences?",
    "limit": 5,
    "min_score": 0.5
  }'

# Search with sector filtering (only semantic facts)
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the user interface preferences?",
    "limit": 5,
    "sectors": ["semantic"],
    "tags": ["preference"]
  }'
```

#### List All Memories

Get paginated list of all memories:

```bash
curl -X GET "http://localhost:8000/api/v1/memory?limit=50&offset=0" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

#### Delete a Memory

Remove a specific memory:

```bash
curl -X DELETE http://localhost:8000/api/v1/memory/{memory_id} \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

#### Preview Conversation Context

Debug what context would be retrieved for a query:

```bash
curl -X GET "http://localhost:8000/api/v1/memory/context/preview?query=project%20timeline&max_memories=10" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

#### Health Check

Verify OpenMemory connectivity:

```bash
curl -X GET http://localhost:8000/api/v1/memory/health \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Memory Sectors

OpenMemory uses **Hierarchical Memory Decomposition (HMD)** to automatically classify memories into sectors. Each memory is assigned 2-3 relevant sectors and gets one embedding per sector for multi-dimensional recall.

### Automatic Sector Classification

When you store a memory, OpenMemory analyzes the content and assigns appropriate sectors:

**Available Sectors:**

- **semantic**: Facts and conceptual knowledge
  - Example: "Paris is the capital of France"
  - Example: "User's email is user@example.com"

- **episodic**: Specific events and experiences
  - Example: "Had a productive meeting on Jan 15"
  - Example: "User mentioned struggling with the login flow"

- **procedural**: How-to knowledge and workflows
  - Example: "To deploy: run tests, build, then push"
  - Example: "User prefers reviewing code in small batches"

- **emotional**: Emotional context and sentiment
  - Example: "User was frustrated with slow performance"
  - Example: "Excited about the new feature launch"

- **reflective**: Insights and meta-cognition
  - Example: "Realized the architecture needs refactoring"
  - Example: "User learns best through hands-on examples"

### Sector Assignment Example

```bash
# Store a memory
curl -X POST http://localhost:8000/api/v1/memory \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers reviewing code in the morning when focused",
    "tags": ["preference", "workflow"]
  }'

# Response shows assigned sectors
{
  "success": true,
  "data": {
    "id": "memory_abc123",
    "content": "User prefers reviewing code in the morning when focused",
    "sectors": ["procedural", "semantic"],  # Automatically determined!
    "embeddings": {
      "procedural": [...],
      "semantic": [...]
    },
    "salience": 0.8,
    ...
  }
}
```

### Filtering by Sectors

You can filter searches to specific sectors:

```bash
# Search only procedural memories (how-to knowledge)
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how does the user prefer to work?",
    "sectors": ["procedural"],
    "limit": 5
  }'

# Search across semantic and episodic
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what happened at the last meeting?",
    "sectors": ["episodic", "semantic"],
    "limit": 5
  }'
```

### Composite Scoring

OpenMemory ranks search results using:
- **60%** similarity (semantic match to query)
- **20%** salience (importance/reinforcement)
- **10%** recency (how recent the memory is)
- **10%** link weight (connections to other memories)

This ensures the most relevant and important memories surface first.

## Advanced Usage

### Programmatic Integration

```python
from api.services.memory_service import MemoryService
from uuid import UUID

service = MemoryService()

# Store a custom memory
memory = await service.store_memory(
    user_id=UUID("user-uuid"),
    content="Important business rule: discounts apply on weekends",
    memory_type="procedural",
    metadata={"domain": "business_logic"}
)

# Search memories
results = await service.search_memories(
    user_id=UUID("user-uuid"),
    query="discount rules",
    limit=5,
    min_score=0.6,
    memory_type="procedural"
)

# Get conversation context for RAG
context = await service.get_conversation_context(
    user_id=UUID("user-uuid"),
    current_query="What are the current discount policies?",
    max_memories=10
)
```

### Customizing RAG Behavior

To disable OpenMemory for specific RAG queries:

```python
from api.services.rag_service import RAGService
from api.services.vector_service import VectorService
from api.adapters.llm_adapter import get_llm_adapter

rag_service = RAGService(
    vector_service=VectorService(),
    llm_adapter=get_llm_adapter()
)

# Disable memory for this query
result = await rag_service.answer_question(
    query="What is in document X?",
    user_id=user_id,
    use_memory=False  # Only use Qdrant, not OpenMemory
)
```

## Troubleshooting

### Integration Disabled

If you see "OpenMemory integration is disabled":

1. Check `OPENMEMORY_ENABLED=true` in `.env`
2. Restart the orchestrator: `docker compose restart orchestrator`
3. Verify environment variable: `docker exec brainda-orchestrator env | grep OPENMEMORY`

### Connection Errors

If OpenMemory is unreachable:

1. Check OpenMemory server status
2. Verify `OPENMEMORY_URL` is correct
3. Check network connectivity from Docker container
4. Review logs: `docker compose logs -f orchestrator | grep openmemory`

### Health Check

Use the health endpoint to diagnose issues:

```bash
curl -X GET http://localhost:8000/api/v1/memory/health \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

Possible responses:

- **Disabled**: `{"enabled": false, "status": "disabled"}`
- **Healthy**: `{"enabled": true, "status": "healthy", "url": "..."}`
- **Error**: `{"enabled": true, "status": "error", "error": "..."}`

### Performance Tuning

Adjust memory retrieval limits:

```python
# In RAG service, modify max_memories parameter
memory_context = await self.memory_service.get_conversation_context(
    user_id=user_id,
    current_query=query,
    max_memories=5  # Reduce for faster responses
)
```

## User Isolation

All memory operations are **strictly user-scoped**:

- Memories are filtered by `user_id` in all operations
- One user cannot access another user's memories
- Memory service enforces isolation at the adapter level
- OpenMemory server should also enforce user isolation

## Best Practices

### When to Store Memories

✅ **DO** store:
- User preferences and settings
- Important facts mentioned in conversation
- Explicit user requests to remember something
- Business rules and procedural knowledge

❌ **DON'T** store:
- Temporary/transient information
- Sensitive credentials (use encrypted storage instead)
- Duplicate information already in documents/notes
- Excessive detail (summarize when possible)

### Memory Type Guidelines

Choose appropriate memory types:

- **conversation**: Automatic storage via RAG, don't store manually
- **fact**: Discrete facts like "User's birthday is Jan 1"
- **preference**: Settings like "Prefers metric units"
- **event**: Time-based like "Mentioned vacation from Dec 1-10"
- **procedural**: Instructions like "Weekly reports due on Fridays"

### Metadata Best Practices

Include useful metadata for filtering and debugging:

```python
metadata = {
    "source": "chat" | "api" | "import",
    "category": "business" | "personal" | "technical",
    "confidence": 0.0-1.0,  # How certain is this memory?
    "created_by": "user" | "system",
    "tags": ["important", "project-x"]
}
```

## Monitoring

### Metrics

Monitor OpenMemory integration via structured logs:

```bash
docker compose logs -f orchestrator | grep openmemory
```

Key log events:

- `storing_openmemory`: Memory storage attempts
- `searching_openmemory`: Memory search requests
- `retrieved_conversation_context`: Context retrieval
- `openmemory_health_check_failed`: Health check failures

### Performance Metrics

Track in Prometheus (if enabled):

- RAG query latency with/without memory
- Memory search result counts
- Memory storage success/failure rates

## Migration and Data Management

### Bulk Import Memories

```python
import asyncio
from api.services.memory_service import MemoryService
from uuid import UUID

async def bulk_import():
    service = MemoryService()

    memories = [
        {"content": "...", "type": "fact"},
        {"content": "...", "type": "preference"},
    ]

    for mem in memories:
        await service.store_memory(
            user_id=UUID("user-uuid"),
            content=mem["content"],
            memory_type=mem["type"]
        )

asyncio.run(bulk_import())
```

### Export User Memories

```bash
curl -X GET "http://localhost:8000/api/v1/memory?limit=1000" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  > user_memories.json
```

## Security Considerations

1. **Authentication**: All memory endpoints require valid session token
2. **Authorization**: Users can only access their own memories
3. **API Key**: Store `OPENMEMORY_API_KEY` securely (not in version control)
4. **Network**: Consider using HTTPS for OpenMemory server in production
5. **Data Privacy**: Be mindful of what information is stored in memories

## Future Enhancements

Potential improvements:

- [ ] Memory expiration/TTL policies
- [ ] Memory consolidation (merge similar memories)
- [ ] Memory ranking and reinforcement
- [ ] Multi-modal memories (images, documents)
- [ ] Memory decay simulation
- [ ] Automatic fact extraction from conversations
- [ ] Memory conflict resolution

## Support

For issues with:

- **Brainda Integration**: Check Brainda logs and this documentation
- **OpenMemory Server**: See [OpenMemory documentation](https://github.com/CaviraOSS/OpenMemory)
- **API Questions**: Review `/api/v1/docs` (FastAPI Swagger UI)

## References

- [OpenMemory GitHub](https://github.com/CaviraOSS/OpenMemory)
- [Brainda CLAUDE.md](../CLAUDE.md) - Project overview
- [RAG Service](../app/api/services/rag_service.py) - Implementation details
