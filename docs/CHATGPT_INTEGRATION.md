# ChatGPT Import to OpenMemory

This guide shows how to import your ChatGPT conversation history into OpenMemory.

## Overview

Import your entire ChatGPT conversation history into Brainda's OpenMemory system, enabling:
- Unified memory across AI systems
- Context migration from ChatGPT to Brainda
- Searchable conversation history
- Cross-platform memory access

---

## Quick Start

### 1. Export Your ChatGPT Conversations

1. Go to ChatGPT: https://chat.openai.com
2. Click your profile → **Settings**
3. Go to **Data Controls** → **Export Data**
4. Wait for email with download link (can take up to 24 hours)
5. Download and extract the ZIP file
6. Find `conversations.json` inside

### 2. Install Dependencies

```bash
pip install httpx
```

### 3. Set Environment Variables

```bash
export VIB_URL=http://localhost:8000
export API_TOKEN=your-vib-api-token
```

### 4. Run the Import

**Dry run (preview only):**
```bash
python scripts/import_chatgpt.py conversations.json --dry-run
```

**Import everything:**
```bash
python scripts/import_chatgpt.py conversations.json
```

**Import only recent conversations:**
```bash
# Only conversations after Jan 1, 2024
python scripts/import_chatgpt.py conversations.json --filter-after 2024-01-01
```

**Import limited number:**
```bash
# Only first 10 conversations
python scripts/import_chatgpt.py conversations.json --limit 10
```

### 5. Verify Import

```bash
# Check memory count
python scripts/browse_memory.py stats

# Search imported conversations
python scripts/browse_memory.py search "chatgpt" --sectors=episodic

# List all memories
curl -X GET "http://localhost:8000/api/v1/memory?limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Import Output Example

```
🔄 Importing ChatGPT conversations from: conversations.json

📖 Parsing export file...
   Found 47 conversations

🏥 Checking OpenMemory connection...
   ✓ Connected to http://localhost:8080

[1/47]
📝 Processing: Python async patterns discussion
   ID: abc123...
   Created: 2024-11-05T10:30:00
   Messages: 12
   Turns: 6 (user-assistant pairs)

   ✓ Turn 1/6 → Sectors: semantic, procedural
   ✓ Turn 2/6 → Sectors: episodic, semantic
   ✓ Turn 3/6 → Sectors: procedural
   ...
   ✅ Imported 6/6 turns

[2/47]
...

============================================================
✅ Import Complete!
============================================================
Conversations processed: 47
Total turns imported: 284
```

---

## What Gets Stored

Each conversation turn is stored as:

```json
{
  "content": "User: How do I use async/await in Python?\n\nAssistant: Here's how...",
  "tags": ["chatgpt", "imported", "Python async patterns"],
  "metadata": {
    "source": "chatgpt_import",
    "conversation_id": "abc123...",
    "conversation_title": "Python async patterns discussion",
    "turn_index": 1,
    "total_turns": 6,
    "original_timestamp": "2024-11-05T10:30:00"
  },
  "sectors": ["episodic", "semantic"]  // Auto-assigned by OpenMemory
}
```

**Key Features:**
- **Content**: User-assistant exchange as plain text
- **Tags**: `["chatgpt", "imported", conversation-title]` for easy filtering
- **Metadata**: Preserves conversation ID, title, timestamp, turn index
- **Sectors**: Automatically classified by OpenMemory (typically episodic + semantic)

---

## Command Line Options

### `--dry-run`
Preview what will be imported without actually storing anything.

```bash
python scripts/import_chatgpt.py conversations.json --dry-run
```

### `--filter-after DATE`
Import only conversations created after a specific date (ISO format).

```bash
python scripts/import_chatgpt.py conversations.json --filter-after 2024-01-01
python scripts/import_chatgpt.py conversations.json --filter-after 2024-06-15
```

### `--limit N`
Limit the number of conversations to import (useful for testing).

```bash
python scripts/import_chatgpt.py conversations.json --limit 10
python scripts/import_chatgpt.py conversations.json --limit 5 --dry-run
```

### Combined Options

```bash
# Test with first 5 conversations after Jan 1, 2024
python scripts/import_chatgpt.py conversations.json \
  --filter-after 2024-01-01 \
  --limit 5 \
  --dry-run

# Import recent conversations only (last 6 months)
python scripts/import_chatgpt.py conversations.json \
  --filter-after 2024-06-01
```

---

## Use Cases

### 1. Unified Memory Across AI Systems

Import ChatGPT history → Query it in Brainda's RAG chat:

```bash
# Import ChatGPT conversations
python scripts/import_chatgpt.py chatgpt_export.json

# Now ask Brainda about those conversations
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message": "What did I discuss about Python async patterns?"}'

# Brainda will search both:
# - OpenMemory (your ChatGPT conversations)
# - Qdrant (your documents and notes)
```

### 2. Context Migration

Moving from ChatGPT to Brainda? Import your entire conversation history:

```bash
# Import everything
python scripts/import_chatgpt.py conversations.json

# Brainda now has context of all your previous ChatGPT interactions
```

### 3. Conversation Analytics

Import and analyze your ChatGPT usage:

```bash
# Import
python scripts/import_chatgpt.py conversations.json

# Analyze by sector
python scripts/browse_memory.py stats

# Output:
# By Sector:
#   semantic: 450    (facts discussed)
#   episodic: 380    (conversations)
#   procedural: 290  (how-to queries)
#   emotional: 45    (emotional context)
#   reflective: 30   (insights)
```

### 4. Search Imported Conversations

Search through your imported ChatGPT history:

```bash
# Search by content
python scripts/browse_memory.py search "python async"

# Search by sector (only conversational memories)
python scripts/browse_memory.py search "deployment" --sectors=episodic

# Search via API
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what did I ask about databases?",
    "sectors": ["episodic", "semantic"],
    "tags": ["chatgpt"]
  }'
```

### 5. Backup and Portability

Export from ChatGPT → Import to OpenMemory → Export as Markdown:

```bash
# Import from ChatGPT
python scripts/import_chatgpt.py conversations.json

# Export to markdown vault
python scripts/browse_memory.py export chatgpt_backup/

# Now you have portable markdown files
ls chatgpt_backup/semantic/
ls chatgpt_backup/episodic/
```

---

## Troubleshooting

### Import Script Fails

**Error: "API_TOKEN not set"**
```bash
export API_TOKEN=your-token
# or
export VIB_API_TOKEN=your-token
```

**Error: "OpenMemory is not healthy"**
```bash
# Check OpenMemory connection
curl http://localhost:8000/api/v1/memory/health \
  -H "Authorization: Bearer YOUR_TOKEN"

# Verify OPENMEMORY_ENABLED=true in .env
# Restart orchestrator if needed
docker compose up -d --build orchestrator
```

**Error: "Failed to parse export"**
- Make sure you extracted the ZIP file
- Use the `conversations.json` file (not other files in the export)
- Check JSON is valid: `jq . conversations.json` (installs with `apt install jq`)

**Error: "Connection refused"**
```bash
# Ensure Brainda is running
curl http://localhost:8000/api/v1/health

# Check docker services
docker compose ps

# Verify VIB_URL is correct
echo $VIB_URL  # Should be http://localhost:8000
```

### Performance Issues

**Import is slow:**
The script adds 0.1s delay between requests to avoid overloading. For faster import:

```bash
# Edit scripts/import_chatgpt.py around line 400
# Change:
await asyncio.sleep(0.1)
# To:
await asyncio.sleep(0.05)  # Faster, but may overload server
```

**Too many conversations:**
Import in batches:

```bash
# First batch
python scripts/import_chatgpt.py conversations.json --limit 50

# Then filter by date to avoid duplicates
python scripts/import_chatgpt.py conversations.json --filter-after 2024-06-01
```

**Out of memory:**
If you have thousands of conversations, consider:
- Importing in smaller batches with `--limit`
- Filtering by date with `--filter-after`
- Increasing Docker memory limits

---

## Best Practices

### Before Importing

1. **Start with dry run**: Always use `--dry-run` first to preview
2. **Test with limit**: Use `--limit 5` to test before importing everything
3. **Check OpenMemory health**: Verify connection before starting
4. **Backup existing data**: Export current memories if needed

### During Import

1. **Monitor progress**: Watch the console output for errors
2. **Check logs**: `docker compose logs -f orchestrator | grep openmemory`
3. **Verify sectors**: See which sectors are being assigned
4. **Rate limiting**: The 0.1s delay is intentional to avoid overload

### After Import

1. **Verify count**: `python scripts/browse_memory.py stats`
2. **Search test**: Try searching for known topics
3. **Check quality**: Review a few imported memories
4. **Export vault**: Create markdown backup for safekeeping

### Avoiding Duplicates

⚠️ **Re-running the import will create duplicates!** OpenMemory doesn't deduplicate.

**To avoid duplicates:**

```bash
# First import (all conversations)
python scripts/import_chatgpt.py conversations.json

# Save the date
echo "2024-11-14" > ~/.last_chatgpt_import

# Future imports (only new conversations)
python scripts/import_chatgpt.py conversations.json \
  --filter-after $(cat ~/.last_chatgpt_import)

# Update the date
date +%Y-%m-%d > ~/.last_chatgpt_import
```

---

## Advanced: Automated Sync

Create a script for periodic imports:

```bash
#!/bin/bash
# sync_chatgpt.sh

EXPORT_DIR=~/Downloads/chatgpt_export
LAST_SYNC=$(cat ~/.last_chatgpt_sync 2>/dev/null || echo "2024-01-01")

# Find latest export
LATEST=$(ls -t $EXPORT_DIR/conversations*.json 2>/dev/null | head -1)

if [ -f "$LATEST" ]; then
  echo "Importing from $LATEST since $LAST_SYNC"

  python scripts/import_chatgpt.py "$LATEST" \
    --filter-after "$LAST_SYNC"

  # Update sync date
  date +%Y-%m-%d > ~/.last_chatgpt_sync
  echo "✅ Sync complete!"
else
  echo "❌ No export found in $EXPORT_DIR"
  echo "Export from ChatGPT and save to $EXPORT_DIR"
fi
```

Make executable and run:
```bash
chmod +x sync_chatgpt.sh
./sync_chatgpt.sh
```

---

## ChatGPT Export Format

The export is a JSON array of conversations:

```json
[
  {
    "id": "conversation_id",
    "title": "Conversation title",
    "create_time": 1234567890.123,
    "update_time": 1234567890.123,
    "mapping": {
      "node_id": {
        "message": {
          "author": {"role": "user" | "assistant"},
          "content": {"parts": ["message text"]},
          "create_time": 1234567890.123
        },
        "parent": "parent_node_id",
        "children": ["child_node_id"]
      }
    }
  }
]
```

The import script:
1. Parses this structure
2. Extracts message chains
3. Groups into user-assistant turns
4. Stores each turn in OpenMemory

---

## FAQ

**Q: Will this work with Claude.ai conversation exports?**
A: Not directly. Claude.ai doesn't provide conversation exports yet. The script is specific to ChatGPT's format.

**Q: Can I import from other AI assistants?**
A: Yes! The import script can be adapted for any JSON export format. You'd need to modify the `parse_chatgpt_export()` function to match the export structure.

**Q: Do imported conversations affect RAG quality?**
A: Yes, positively! They provide conversational context. Brainda's RAG will search both OpenMemory (conversations) and Qdrant (documents).

**Q: How much storage do conversations use?**
A: Approximately 1-2 KB per conversation turn. 1000 conversations ≈ 1-2 MB in OpenMemory.

**Q: Can I delete imported conversations?**
A: Yes, via API: `DELETE /api/v1/memory/{memory_id}` or search by tag `["chatgpt"]` and delete in bulk.

**Q: Will OpenMemory deduplicate if I import twice?**
A: No, it will create duplicates. Use `--filter-after` to import only new conversations.

**Q: Can I edit the imported memories?**
A: Not directly. You'd need to delete and re-import, or store a new corrected version.

**Q: How long does import take?**
A: ~0.1 seconds per conversation turn. 1000 turns ≈ 100 seconds (1.7 minutes).

**Q: Can I import while Brainda is in use?**
A: Yes, the import runs via API and won't disrupt normal operations.

---

## See Also

- [OpenMemory Integration Guide](OPENMEMORY_INTEGRATION.md) - Full OpenMemory documentation
- [Memory Browsing Guide](MEMORY_BROWSING.md) - How to browse and export memories
- [Memory Sectors](OPENMEMORY_INTEGRATION.md#memory-sectors) - Understanding sectors
