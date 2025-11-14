# Browsing OpenMemory Contents

This guide shows you how to browse and export your OpenMemory contents.

## Quick Start

### 1. Via API

```bash
# List memories
curl -X GET "http://localhost:8000/api/v1/memory?limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Search memories
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "everything", "limit": 100}'
```

### 2. Via CLI Tool

```bash
# Show statistics
python scripts/browse_memory.py stats

# List memories
python scripts/browse_memory.py list

# Search memories
python scripts/browse_memory.py search "user preferences"

# Search by sector
python scripts/browse_memory.py search "how to deploy" --sectors=procedural

# Export to markdown
python scripts/browse_memory.py export
```

### 3. Via Memory Vault (Markdown Mirror)

Enable automatic syncing to markdown files:

```bash
# In .env:
MEMORY_VAULT_SYNC_ENABLED=true
MEMORY_VAULT_PATH=./memory_vault

# Restart orchestrator
docker compose up -d --build orchestrator

# Trigger sync
curl -X POST http://localhost:8000/api/v1/memory/sync \
  -H "Authorization: Bearer YOUR_TOKEN"

# Browse files
ls memory_vault/your-user-id/
cat memory_vault/your-user-id/README.md
```

## Memory Vault Structure

When you sync, memories are organized like this:

```
memory_vault/
└── {user-id}/
    ├── README.md           # Index with overview
    ├── semantic/           # Facts and knowledge
    │   ├── abc12345_user-prefers-dark.md
    │   └── def67890_paris-is-capital.md
    ├── episodic/           # Events and experiences
    │   └── ghi12345_meeting-on-jan-15.md
    ├── procedural/         # How-to knowledge
    │   └── jkl67890_deploy-using-ci-cd.md
    ├── emotional/          # Emotional context
    ├── reflective/         # Insights
    └── uncategorized/      # No sector assigned
```

### File Format

Each markdown file contains:

```markdown
---
id: memory_abc123
sectors: ["semantic", "procedural"]
tags: ["preference", "ui"]
salience: 0.85
created_at: 2025-01-15T10:30:00Z
synced_at: 2025-01-15T11:00:00Z
---

# Memory `semantic` `procedural`

**Salience**: ★★★★☆ (0.85)
**Tags**: preference, ui
**Created**: 2025-01-15T10:30:00Z

---

User prefers dark mode for all applications and wants
consistent theming across the interface.
```

## CLI Tool Reference

### Installation

The CLI tool requires `httpx`:

```bash
pip install httpx
```

### Commands

**Show Statistics**
```bash
python scripts/browse_memory.py stats

# Output:
# === OpenMemory Statistics ===
#
# Status: healthy
# Enabled: True
# URL: http://localhost:8080
#
# Total Memories: 42
#
# By Sector:
#   semantic: 15
#   episodic: 12
#   procedural: 10
#   emotional: 3
#   reflective: 2
```

**List Memories**
```bash
# List first 50
python scripts/browse_memory.py list

# List first 100
python scripts/browse_memory.py list 100
```

**Search Memories**
```bash
# Basic search
python scripts/browse_memory.py search "user preferences"

# Search specific sectors
python scripts/browse_memory.py search "deployment process" --sectors=procedural,semantic

# Output shows:
# - Relevance score
# - Assigned sectors
# - Content preview
```

**Export to Markdown**
```bash
# Export to default directory (memories/)
python scripts/browse_memory.py export

# Export to custom directory
python scripts/browse_memory.py export my_memories/

# This creates the same structure as Memory Vault
```

## API Endpoints

### List Memories

```bash
GET /api/v1/memory?limit=50&offset=0
```

Response:
```json
{
  "success": true,
  "data": {
    "memories": [
      {
        "id": "memory_abc123",
        "content": "User prefers dark mode...",
        "sectors": ["semantic", "procedural"],
        "tags": ["preference"],
        "salience": 0.85,
        "created_at": "2025-01-15T10:30:00Z"
      }
    ],
    "count": 42,
    "limit": 50,
    "offset": 0
  }
}
```

### Search Memories

```bash
POST /api/v1/memory/search
```

Request:
```json
{
  "query": "user interface preferences",
  "limit": 10,
  "min_score": 0.5,
  "sectors": ["semantic"],
  "tags": ["preference"]
}
```

Response:
```json
{
  "success": true,
  "data": {
    "memories": [
      {
        "id": "memory_abc123",
        "content": "...",
        "sectors": ["semantic", "procedural"],
        "score": 0.87,
        "salience": 0.85
      }
    ],
    "count": 5
  }
}
```

### Sync to Vault

```bash
POST /api/v1/memory/sync
```

Response:
```json
{
  "success": true,
  "message": "Memory vault sync started in background",
  "vault_path": "/memory_vault/user-uuid"
}
```

## Use Cases

### 1. Debugging RAG Context

See what memories would be retrieved for a chat query:

```bash
curl -X GET "http://localhost:8000/api/v1/memory/context/preview?query=how+to+deploy" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Audit Memory Contents

Export and review all memories:

```bash
python scripts/browse_memory.py export audit_$(date +%Y%m%d)/
cd audit_20250115/
cat README.md
```

### 3. Search by Sector

Find only procedural knowledge (how-to):

```bash
python scripts/browse_memory.py search "process" --sectors=procedural
```

### 4. Version Control

Add memory vault to git for tracking:

```bash
# In .env
MEMORY_VAULT_PATH=./memory_vault

# Add to .gitignore (or commit if you want version control)
echo "memory_vault/" >> .gitignore

# Or commit it
git add memory_vault/
git commit -m "Snapshot of OpenMemory contents"
```

### 5. Browse Like Obsidian/Notion

Use any markdown editor to browse the vault:

```bash
# Open in VS Code
code memory_vault/your-user-id/

# Or use Obsidian
# 1. Open Obsidian
# 2. Open folder: memory_vault/your-user-id/
# 3. Browse with graph view and search
```

## Configuration

### Environment Variables

```bash
# Enable OpenMemory
OPENMEMORY_ENABLED=true
OPENMEMORY_URL=http://localhost:8080
OPENMEMORY_API_KEY=your-key

# Enable Memory Vault sync
MEMORY_VAULT_SYNC_ENABLED=true
MEMORY_VAULT_PATH=./memory_vault
```

### Docker Volume

The memory vault is mounted in `docker-compose.yml`:

```yaml
volumes:
  - ./memory_vault:/memory_vault
```

This allows the orchestrator to write files that persist on your host.

## Automation

### Periodic Sync

Add a cron job or systemd timer to sync regularly:

```bash
# Crontab example (sync every hour)
0 * * * * curl -X POST http://localhost:8000/api/v1/memory/sync \
  -H "Authorization: Bearer $API_TOKEN"
```

### Post-Chat Sync

Trigger sync after important conversations to immediately reflect them in the vault.

### Backup Strategy

```bash
#!/bin/bash
# backup_memories.sh

# Export via CLI
python scripts/browse_memory.py export backups/$(date +%Y%m%d)/

# Or sync via API
curl -X POST http://localhost:8000/api/v1/memory/sync \
  -H "Authorization: Bearer $API_TOKEN"

# Compress
tar -czf memory_backup_$(date +%Y%m%d).tar.gz memory_vault/

# Upload to backup location
# rclone copy memory_backup_*.tar.gz remote:backups/
```

## Troubleshooting

### Sync Not Working

1. Check if enabled:
   ```bash
   # Should be "true"
   echo $MEMORY_VAULT_SYNC_ENABLED
   ```

2. Check permissions:
   ```bash
   ls -la memory_vault/
   # Should be writable by Docker user
   ```

3. Check logs:
   ```bash
   docker compose logs -f orchestrator | grep memory_vault
   ```

### CLI Tool Errors

1. Install dependencies:
   ```bash
   pip install httpx
   ```

2. Set API token:
   ```bash
   export API_TOKEN=your-token-here
   export VIB_URL=http://localhost:8000
   ```

3. Test connection:
   ```bash
   curl http://localhost:8000/api/v1/memory/health \
     -H "Authorization: Bearer $API_TOKEN"
   ```

### Empty Vault

If vault is empty after sync:

1. Check OpenMemory has content:
   ```bash
   python scripts/browse_memory.py list
   ```

2. Manually trigger sync:
   ```bash
   curl -X POST http://localhost:8000/api/v1/memory/sync \
     -H "Authorization: Bearer $API_TOKEN"
   ```

3. Wait a moment (runs in background), then check:
   ```bash
   ls -R memory_vault/
   ```

## Best Practices

1. **Regular Exports**: Export periodically for backup
2. **Sector Organization**: Leverage sectors for browsing (semantic for facts, procedural for how-to, etc.)
3. **Search First**: Use search instead of listing when looking for specific memories
4. **Salience Matters**: High-salience memories (★★★★★) are most important
5. **Tag Consistently**: Use consistent tags when storing memories manually

## See Also

- [OpenMemory Integration Guide](OPENMEMORY_INTEGRATION.md)
- [Memory Sectors](OPENMEMORY_INTEGRATION.md#memory-sectors)
- [API Documentation](http://localhost:8000/docs) - FastAPI Swagger UI
