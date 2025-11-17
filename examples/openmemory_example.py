#!/usr/bin/env python3
"""
OpenMemory Integration Examples for Brainda

This script demonstrates how to use OpenMemory integration in Brainda for:
- Storing explicit memories
- Searching memories semantically
- Previewing conversation context
- Managing user memories

Prerequisites:
    - Brainda running with OpenMemory enabled
    - Valid session token or API token
    - OPENMEMORY_URL configured
"""

import asyncio
import httpx
import os
from uuid import uuid4


# Configuration
BASE_URL = os.getenv("BRAINDA_URL", "http://localhost:8000")
API_TOKEN = os.getenv("API_TOKEN", "your-api-token-here")

# Use session token or API token
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


async def check_memory_health():
    """Check if OpenMemory integration is healthy."""
    print("\n=== Checking OpenMemory Health ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/memory/health",
            headers=HEADERS,
        )
        result = response.json()
        print(f"Status: {result}")

        if result.get("status") == "healthy":
            print("✅ OpenMemory is healthy and ready")
            return True
        else:
            print("❌ OpenMemory is not available")
            return False


async def store_user_preferences():
    """Store user preferences as memories."""
    print("\n=== Storing User Preferences ===")

    preferences = [
        {
            "content": "User prefers dark mode for all applications",
            "memory_type": "preference",
            "metadata": {"category": "ui_settings"},
        },
        {
            "content": "User works in Pacific timezone (PST/PDT)",
            "memory_type": "preference",
            "metadata": {"category": "localization"},
        },
        {
            "content": "User prefers concise answers without verbose explanations",
            "memory_type": "preference",
            "metadata": {"category": "communication_style"},
        },
    ]

    async with httpx.AsyncClient() as client:
        for pref in preferences:
            response = await client.post(
                f"{BASE_URL}/api/v1/memory",
                headers=HEADERS,
                json=pref,
            )
            result = response.json()
            if result.get("success"):
                memory_id = result["data"].get("id")
                print(f"✅ Stored: {pref['content'][:50]}... (ID: {memory_id})")
            else:
                print(f"❌ Failed: {result}")


async def store_project_facts():
    """Store project-related facts."""
    print("\n=== Storing Project Facts ===")

    facts = [
        {
            "content": "Project Alpha deadline is December 31, 2025",
            "memory_type": "fact",
            "metadata": {"project": "alpha", "type": "deadline"},
        },
        {
            "content": "Team uses Python 3.11+ for all backend services",
            "memory_type": "fact",
            "metadata": {"project": "general", "type": "tech_stack"},
        },
        {
            "content": "Weekly stand-ups are on Mondays at 10 AM PST",
            "memory_type": "event",
            "metadata": {"recurring": "weekly", "type": "meeting"},
        },
    ]

    async with httpx.AsyncClient() as client:
        for fact in facts:
            response = await client.post(
                f"{BASE_URL}/api/v1/memory",
                headers=HEADERS,
                json=fact,
            )
            result = response.json()
            if result.get("success"):
                print(f"✅ Stored: {fact['content'][:50]}...")
            else:
                print(f"❌ Failed: {result}")


async def search_memories(query: str, memory_type: str = None):
    """Search memories by semantic similarity."""
    print(f"\n=== Searching Memories: '{query}' ===")

    payload = {
        "query": query,
        "limit": 5,
        "min_score": 0.3,
    }

    if memory_type:
        payload["memory_type"] = memory_type

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/memory/search",
            headers=HEADERS,
            json=payload,
        )
        result = response.json()

        if result.get("success"):
            memories = result["data"]["memories"]
            print(f"Found {len(memories)} relevant memories:")

            for idx, mem in enumerate(memories, 1):
                content = mem.get("content", "")
                score = mem.get("score", 0.0)
                mem_type = mem.get("type", "unknown")
                print(f"\n{idx}. [{mem_type}] (score: {score:.2f})")
                print(f"   {content[:100]}...")
        else:
            print(f"❌ Search failed: {result}")


async def preview_conversation_context(query: str):
    """Preview what context would be retrieved for a chat query."""
    print(f"\n=== Previewing Context for: '{query}' ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/memory/context/preview",
            headers=HEADERS,
            params={"query": query, "max_memories": 10},
        )
        result = response.json()

        if result.get("success"):
            context = result["data"]["context"]
            context_length = result["data"]["context_length"]

            print(f"Context length: {context_length} characters")
            print("\n--- Context Preview ---")
            print(context[:500] + "..." if len(context) > 500 else context)
        else:
            print(f"❌ Preview failed: {result}")


async def list_all_memories():
    """List all user memories."""
    print("\n=== Listing All Memories ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/memory",
            headers=HEADERS,
            params={"limit": 20, "offset": 0},
        )
        result = response.json()

        if result.get("success"):
            memories = result["data"]["memories"]
            count = result["data"]["count"]

            print(f"Total memories: {count}")

            for idx, mem in enumerate(memories, 1):
                content = mem.get("content", "")
                mem_type = mem.get("type", "unknown")
                timestamp = mem.get("timestamp", "")
                print(f"\n{idx}. [{mem_type}] {timestamp}")
                print(f"   {content[:80]}...")
        else:
            print(f"❌ Failed: {result}")


async def chat_with_memory(message: str):
    """Send a chat message that will use OpenMemory context."""
    print(f"\n=== Chatting with Memory: '{message}' ===")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            headers=HEADERS,
            json={"message": message},
        )
        result = response.json()

        answer = result.get("answer", "")
        memory_used = result.get("memory_used", False)
        sources_used = result.get("sources_used", 0)

        print(f"\nMemory used: {'✅' if memory_used else '❌'}")
        print(f"Sources used: {sources_used}")
        print(f"\nAnswer:\n{answer}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("OpenMemory Integration Examples for Brainda")
    print("=" * 60)

    # 1. Health check
    is_healthy = await check_memory_health()
    if not is_healthy:
        print("\n⚠️  OpenMemory is not available. Check your configuration.")
        print("Set OPENMEMORY_ENABLED=true and OPENMEMORY_URL in .env")
        return

    # 2. Store various types of memories
    await store_user_preferences()
    await store_project_facts()

    # Wait a moment for indexing
    await asyncio.sleep(2)

    # 3. Search memories
    await search_memories("user interface preferences", memory_type="preference")
    await search_memories("project deadlines")
    await search_memories("team meetings")

    # 4. Preview conversation context
    await preview_conversation_context("What are my UI preferences?")
    await preview_conversation_context("Tell me about project timelines")

    # 5. List all memories
    await list_all_memories()

    # 6. Chat with memory context
    await chat_with_memory("What timezone do I work in?")
    await chat_with_memory("When is the Project Alpha deadline?")
    await chat_with_memory("What's the team's tech stack?")

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
