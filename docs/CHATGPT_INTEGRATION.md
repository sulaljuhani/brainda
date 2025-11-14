# ChatGPT Integration with OpenMemory

This guide shows how to import ChatGPT conversations into OpenMemory and set up real-time integration.

## Table of Contents

1. [Import ChatGPT Exports](#import-chatgpt-exports)
2. [MCP Server for Real-time Integration](#mcp-server-for-real-time-integration)
3. [Browser Extension (Alternative)](#browser-extension-alternative)
4. [Use Cases](#use-cases)

---

## Import ChatGPT Exports

### 1. Export Your ChatGPT Conversations

1. Go to ChatGPT: https://chat.openai.com
2. Click your profile → **Settings**
3. Go to **Data Controls** → **Export Data**
4. Wait for email with download link
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

### Import Output Example

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

### What Gets Stored

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

---

## MCP Server for Real-time Integration

The MCP (Model Context Protocol) server allows AI assistants to store and retrieve memories in real-time.

### Supported Clients

- ✅ **Claude Desktop** (native MCP support)
- ✅ **Custom AI agents** (using MCP SDK)
- ❌ **ChatGPT web** (no MCP support yet)
- ⚠️ **ChatGPT API** (possible with wrapper)

### Setup for Claude Desktop

#### 1. Install MCP Python SDK

```bash
pip install mcp httpx
```

#### 2. Configure Claude Desktop

Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vib-openmemory": {
      "command": "python",
      "args": ["/absolute/path/to/brainda/mcp/openmemory_server.py"],
      "env": {
        "VIB_URL": "http://localhost:8000",
        "VIB_API_TOKEN": "your-api-token-here"
      }
    }
  }
}
```

**Note**: Use absolute paths!

#### 3. Restart Claude Desktop

Close and reopen Claude Desktop. You should see "vib-openmemory" in the MCP servers list.

#### 4. Use Memory Tools

In Claude Desktop, you can now:

**Store a memory:**
```
Can you store this fact: "User prefers Python 3.11 for all projects"
```

Claude will use the `store_memory` tool automatically.

**Search memories:**
```
What do you remember about my Python preferences?
```

Claude will use the `search_memories` tool.

**Store conversation:**
```
Remember this conversation for future reference
```

Claude will use the `store_conversation` tool.

### Available MCP Tools

The MCP server provides 5 tools:

1. **`store_memory`** - Store a single memory
   - Input: content, tags (optional), metadata (optional)
   - Output: Memory ID, assigned sectors, salience

2. **`search_memories`** - Search by semantic similarity
   - Input: query, limit, sectors (optional), tags (optional)
   - Output: List of matching memories with scores

3. **`store_conversation`** - Store a conversation turn
   - Input: user_message, assistant_message, metadata (optional)
   - Output: Memory ID, assigned sectors

4. **`list_memories`** - List all memories chronologically
   - Input: limit, offset
   - Output: Paginated memory list

5. **`get_conversation_context`** - Get relevant context for a query
   - Input: query, max_memories
   - Output: Formatted context string

### Manual Testing

Test the MCP server manually:

```bash
# Run the server
export VIB_URL=http://localhost:8000
export VIB_API_TOKEN=your-token
python mcp/openmemory_server.py

# In another terminal, send MCP requests
# (requires MCP client or use Claude Desktop)
```

---

## Browser Extension (Alternative)

For capturing ChatGPT conversations in real-time, you can create a browser extension:

### Concept

```
ChatGPT Web ───► Browser Extension ───► VIB API ───► OpenMemory
                 (captures messages)
```

### Implementation Outline

**1. Manifest (manifest.json):**
```json
{
  "manifest_version": 3,
  "name": "ChatGPT to OpenMemory",
  "version": "1.0",
  "permissions": ["storage", "activeTab"],
  "host_permissions": ["https://chat.openai.com/*"],
  "content_scripts": [{
    "matches": ["https://chat.openai.com/*"],
    "js": ["content.js"]
  }],
  "background": {
    "service_worker": "background.js"
  }
}
```

**2. Content Script (content.js):**
```javascript
// Observe ChatGPT DOM for new messages
const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    // Detect new message elements
    const messages = document.querySelectorAll('[data-message-author-role]');

    // Extract user message and assistant response
    // Send to background script
    chrome.runtime.sendMessage({
      type: 'conversation_turn',
      user: userMessage,
      assistant: assistantMessage
    });
  }
});

observer.observe(document.body, { childList: true, subtree: true });
```

**3. Background Script (background.js):**
```javascript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'conversation_turn') {
    // Send to VIB API
    fetch('http://localhost:8000/api/v1/memory', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer YOUR_TOKEN',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content: `User: ${message.user}\n\nAssistant: ${message.assistant}`,
        tags: ['chatgpt', 'live'],
        metadata: { source: 'browser_extension' }
      })
    });
  }
});
```

**Note**: This is a simplified outline. A full implementation would need:
- Proper message detection logic
- Rate limiting
- Error handling
- Settings UI for API token
- CORS handling

---

## Use Cases

### 1. Unified Memory Across AI Assistants

Import ChatGPT history → Use in VIB's RAG chat:

```bash
# Import ChatGPT conversations
python scripts/import_chatgpt.py chatgpt_export.json

# Now ask VIB about those conversations
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message": "What did I discuss about Python async patterns?"}'

# VIB will search both:
# - OpenMemory (your ChatGPT conversations)
# - Qdrant (your documents and notes)
```

### 2. Context Migration

Moving from ChatGPT to VIB? Import your entire conversation history:

```bash
# Import everything
python scripts/import_chatgpt.py conversations.json

# VIB now has context of all your previous ChatGPT interactions
```

### 3. Cross-Platform Memory

Use MCP server with Claude Desktop while importing ChatGPT history:

```
ChatGPT History ──► OpenMemory ◄── Claude Desktop (via MCP)
                         ▲
                         │
                    VIB's RAG Chat
```

All three interfaces share the same memory system!

### 4. Conversation Analytics

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
#   ...
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

**Error: "VIB_API_TOKEN not set"**
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
```

**Error: "Failed to parse export"**
- Make sure you extracted the ZIP file
- Use the `conversations.json` file (not other files in the export)
- Check JSON is valid: `jq . conversations.json`

### MCP Server Issues

**Claude Desktop doesn't show the server:**
- Check config file location: `~/.config/claude/claude_desktop_config.json`
- Use absolute paths (not relative)
- Verify permissions: `python mcp/openmemory_server.py` should run without errors
- Restart Claude Desktop completely

**"VIB_API_TOKEN not set" error:**
- Check the `env` section in Claude config
- Make sure token is valid: `echo $VIB_API_TOKEN`

**Connection refused:**
- Ensure VIB is running: `curl http://localhost:8000/api/v1/health`
- Check firewall settings
- Verify `VIB_URL` in config

### Performance Issues

**Import is slow:**
```bash
# The script adds 0.1s delay between requests to avoid overloading
# For faster import, edit import_chatgpt.py line ~400:
await asyncio.sleep(0.05)  # Reduce from 0.1 to 0.05
```

**Too many conversations:**
```bash
# Import in batches
python scripts/import_chatgpt.py conversations.json --limit 50
python scripts/import_chatgpt.py conversations.json --limit 50 --offset 50
# etc.
```

---

## Best Practices

### When Importing

1. **Start with dry run**: `--dry-run` to preview before importing
2. **Filter by date**: Use `--filter-after` to import only recent conversations
3. **Limit first import**: Use `--limit 10` to test before importing everything
4. **Tag imported data**: All imports are tagged with `["chatgpt", "imported"]`
5. **Check duplicates**: Re-running import will create duplicates (OpenMemory doesn't dedupe)

### When Using MCP

1. **Be explicit**: Tell Claude to "store this memory" rather than expecting automatic storage
2. **Use tags**: Add tags when storing for better organization
3. **Search strategically**: Use sector filters for better results
4. **Monitor usage**: Check `python scripts/browse_memory.py stats` periodically

### Memory Management

1. **Review imports**: `python scripts/browse_memory.py list 50`
2. **Search imported**: `search "topic" --sectors=episodic`
3. **Delete if needed**: Use `/api/v1/memory/{id}` DELETE endpoint
4. **Export vault**: Keep markdown backup with `browse_memory.py export`

---

## Advanced: Automated Sync

### Periodic ChatGPT Export Import

```bash
#!/bin/bash
# sync_chatgpt.sh

# Export from ChatGPT (manual step - save to ~/Downloads/chatgpt_export/)
# Then run this script

EXPORT_DIR=~/Downloads/chatgpt_export
LAST_SYNC_DATE=$(cat ~/.last_chatgpt_sync 2>/dev/null || echo "2024-01-01")

# Find latest export
LATEST_EXPORT=$(ls -t $EXPORT_DIR/conversations*.json | head -1)

if [ -f "$LATEST_EXPORT" ]; then
  echo "Importing from $LATEST_EXPORT since $LAST_SYNC_DATE"

  python scripts/import_chatgpt.py "$LATEST_EXPORT" \
    --filter-after "$LAST_SYNC_DATE"

  # Update last sync date
  date +%Y-%m-%d > ~/.last_chatgpt_sync

  echo "Sync complete!"
else
  echo "No export found in $EXPORT_DIR"
fi
```

Make executable and run:
```bash
chmod +x sync_chatgpt.sh
./sync_chatgpt.sh
```

---

## FAQ

**Q: Will this work with Claude.ai web chat history?**
A: Not directly. Claude.ai doesn't provide conversation exports yet. However, you can use the MCP server with Claude Desktop.

**Q: Can I import from other AI assistants?**
A: Yes! The import script can be adapted for any JSON export format. You'd need to modify the `parse_chatgpt_export()` function.

**Q: Do imported conversations affect RAG quality?**
A: Yes! They provide conversational context. VIB's RAG will search both OpenMemory (conversations) and Qdrant (documents).

**Q: How much storage do conversations use?**
A: Approximately 1-2 KB per conversation turn. 1000 conversations ≈ 1-2 MB in OpenMemory.

**Q: Can I delete imported conversations?**
A: Yes, via API: `DELETE /api/v1/memory/{memory_id}`

**Q: Will OpenMemory deduplicate if I import twice?**
A: No, it will create duplicates. Use `--filter-after` to avoid re-importing.

---

## See Also

- [OpenMemory Integration Guide](OPENMEMORY_INTEGRATION.md)
- [Memory Browsing Guide](MEMORY_BROWSING.md)
- [MCP Server Documentation](https://modelcontextprotocol.io/)
- [Claude Desktop MCP Setup](https://docs.anthropic.com/claude/docs/mcp)
