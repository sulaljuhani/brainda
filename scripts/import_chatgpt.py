#!/usr/bin/env python3
"""
Import ChatGPT conversation exports into OpenMemory.

ChatGPT exports are JSON files with conversation history. This script
parses the export and stores each conversation turn in OpenMemory.

Usage:
    python scripts/import_chatgpt.py conversations.json
    python scripts/import_chatgpt.py conversations.json --user-id your-uuid
    python scripts/import_chatgpt.py conversations.json --filter-after 2024-01-01

ChatGPT Export Format:
    Download from ChatGPT: Settings → Data Controls → Export Data
    You'll get a zip file with conversations.json
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


BASE_URL = os.getenv("VIB_URL", "http://localhost:8000")
API_TOKEN = os.getenv("API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


def parse_chatgpt_export(file_path: str) -> List[Dict]:
    """Parse ChatGPT export JSON file.

    ChatGPT export structure:
    [
        {
            "id": "conversation_id",
            "title": "Conversation title",
            "create_time": 1234567890.123,
            "update_time": 1234567890.123,
            "mapping": {
                "node_id": {
                    "id": "node_id",
                    "message": {
                        "id": "message_id",
                        "author": {"role": "user" | "assistant" | "system"},
                        "create_time": 1234567890.123,
                        "content": {"content_type": "text", "parts": ["message text"]}
                    },
                    "parent": "parent_node_id",
                    "children": ["child_node_id"]
                }
            }
        }
    ]
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conversations = []

    for conv in data:
        conv_id = conv.get("id")
        title = conv.get("title", "Untitled")
        create_time = conv.get("create_time")
        mapping = conv.get("mapping", {})

        # Extract message chain
        messages = []
        for node_id, node in mapping.items():
            message = node.get("message")
            if not message:
                continue

            author = message.get("author", {})
            role = author.get("role")

            # Skip system messages
            if role == "system":
                continue

            content = message.get("content", {})
            parts = content.get("parts", [])

            if not parts or not parts[0]:
                continue

            text = parts[0] if isinstance(parts[0], str) else ""

            if text.strip():
                messages.append({
                    "role": role,
                    "content": text,
                    "timestamp": message.get("create_time"),
                })

        if messages:
            conversations.append({
                "id": conv_id,
                "title": title,
                "created_at": datetime.fromtimestamp(create_time).isoformat() if create_time else None,
                "messages": messages,
            })

    return conversations


def group_into_turns(messages: List[Dict]) -> List[Dict]:
    """Group messages into user-assistant turns."""
    turns = []
    current_user_msg = None

    for msg in messages:
        if msg["role"] == "user":
            if current_user_msg:
                # Previous user message without assistant response
                turns.append({
                    "user": current_user_msg["content"],
                    "assistant": None,
                    "timestamp": current_user_msg["timestamp"],
                })
            current_user_msg = msg
        elif msg["role"] == "assistant" and current_user_msg:
            turns.append({
                "user": current_user_msg["content"],
                "assistant": msg["content"],
                "timestamp": current_user_msg["timestamp"],
            })
            current_user_msg = None

    # Handle trailing user message
    if current_user_msg:
        turns.append({
            "user": current_user_msg["content"],
            "assistant": None,
            "timestamp": current_user_msg["timestamp"],
        })

    return turns


async def store_conversation_in_openmemory(
    conversation: Dict,
    filter_after: Optional[datetime] = None,
    dry_run: bool = False,
) -> int:
    """Store a conversation in OpenMemory."""
    conv_id = conversation["id"]
    title = conversation["title"]
    messages = conversation["messages"]
    created_at = conversation.get("created_at")

    print(f"\n📝 Processing: {title}")
    print(f"   ID: {conv_id}")
    print(f"   Created: {created_at}")
    print(f"   Messages: {len(messages)}")

    turns = group_into_turns(messages)
    print(f"   Turns: {len(turns)} (user-assistant pairs)")

    if filter_after:
        original_count = len(turns)
        turns = [
            t for t in turns
            if t["timestamp"] and datetime.fromtimestamp(t["timestamp"]) >= filter_after
        ]
        if len(turns) < original_count:
            print(f"   Filtered: {len(turns)} turns after {filter_after.date()}")

    if not turns:
        print("   ⏭️  Skipped (no turns to import)")
        return 0

    if dry_run:
        print(f"   [DRY RUN] Would import {len(turns)} turns")
        return 0

    stored_count = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, turn in enumerate(turns, 1):
            user_msg = turn["user"]
            assistant_msg = turn["assistant"] or "(No response)"
            timestamp = turn["timestamp"]

            # Create conversation content
            content = f"User: {user_msg}\n\nAssistant: {assistant_msg}"

            # Metadata
            metadata = {
                "source": "chatgpt_import",
                "conversation_id": conv_id,
                "conversation_title": title,
                "turn_index": idx,
                "total_turns": len(turns),
            }

            if timestamp:
                metadata["original_timestamp"] = datetime.fromtimestamp(timestamp).isoformat()

            # Store in OpenMemory
            try:
                response = await client.post(
                    f"{BASE_URL}/api/v1/memory",
                    headers=HEADERS,
                    json={
                        "content": content,
                        "tags": ["chatgpt", "imported", title[:30]],
                        "metadata": metadata,
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        memory = result["data"]
                        sectors = memory.get("sectors", [])
                        print(f"   ✓ Turn {idx}/{len(turns)} → Sectors: {', '.join(sectors)}")
                        stored_count += 1
                    else:
                        print(f"   ✗ Turn {idx}/{len(turns)} → Failed: {result}")
                else:
                    print(f"   ✗ Turn {idx}/{len(turns)} → HTTP {response.status_code}")

            except Exception as e:
                print(f"   ✗ Turn {idx}/{len(turns)} → Error: {e}")

            # Rate limiting
            await asyncio.sleep(0.1)

    print(f"   ✅ Imported {stored_count}/{len(turns)} turns")
    return stored_count


async def import_chatgpt_export(
    file_path: str,
    filter_after: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
):
    """Import ChatGPT export into OpenMemory."""
    print(f"🔄 Importing ChatGPT conversations from: {file_path}\n")

    # Parse filter date
    filter_date = None
    if filter_after:
        filter_date = datetime.fromisoformat(filter_after)
        print(f"📅 Filtering conversations after: {filter_date.date()}\n")

    # Parse export
    print("📖 Parsing export file...")
    conversations = parse_chatgpt_export(file_path)
    print(f"   Found {len(conversations)} conversations\n")

    if not conversations:
        print("❌ No conversations found in export")
        return

    # Apply limit
    if limit:
        conversations = conversations[:limit]
        print(f"⚠️  Limited to first {limit} conversations\n")

    # Check OpenMemory health
    print("🏥 Checking OpenMemory connection...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/memory/health",
                headers=HEADERS,
            )
            health = response.json()

            if health.get("status") != "healthy":
                print(f"❌ OpenMemory is not healthy: {health}")
                return

            print(f"   ✓ Connected to {health.get('url')}\n")
        except Exception as e:
            print(f"❌ Failed to connect to OpenMemory: {e}")
            return

    # Import conversations
    total_turns = 0
    for idx, conv in enumerate(conversations, 1):
        print(f"\n[{idx}/{len(conversations)}]")
        turns = await store_conversation_in_openmemory(
            conv,
            filter_after=filter_date,
            dry_run=dry_run,
        )
        total_turns += turns

    # Summary
    print(f"\n{'='*60}")
    print(f"✅ Import Complete!")
    print(f"{'='*60}")
    print(f"Conversations processed: {len(conversations)}")
    print(f"Total turns imported: {total_turns}")

    if dry_run:
        print("\n⚠️  This was a DRY RUN - no data was actually imported")
        print("Run without --dry-run to perform the import")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nExamples:")
        print("  python scripts/import_chatgpt.py conversations.json")
        print("  python scripts/import_chatgpt.py conversations.json --filter-after 2024-01-01")
        print("  python scripts/import_chatgpt.py conversations.json --limit 10")
        print("  python scripts/import_chatgpt.py conversations.json --dry-run")
        return

    file_path = sys.argv[1]

    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return

    # Parse arguments
    filter_after = None
    limit = None
    dry_run = False

    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == "--filter-after" and i + 1 < len(sys.argv):
            filter_after = sys.argv[i + 1]
        elif arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        elif arg == "--dry-run":
            dry_run = True

    asyncio.run(import_chatgpt_export(
        file_path,
        filter_after=filter_after,
        limit=limit,
        dry_run=dry_run,
    ))


if __name__ == "__main__":
    main()
