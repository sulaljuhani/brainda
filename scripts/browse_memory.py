#!/usr/bin/env python3
"""
CLI tool for browsing OpenMemory contents.

Usage:
    python scripts/browse_memory.py list [--limit 50]
    python scripts/browse_memory.py search "query text"
    python scripts/browse_memory.py export [--output memories/]
"""

import asyncio
import httpx
import os
import sys
import json
from datetime import datetime
from pathlib import Path


BASE_URL = os.getenv("BRAINDA_URL", "http://localhost:8000")
API_TOKEN = os.getenv("API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


async def list_memories(limit=50, offset=0):
    """List all memories."""
    print(f"\n=== Listing Memories (limit={limit}, offset={offset}) ===\n")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/memory",
            headers=HEADERS,
            params={"limit": limit, "offset": offset},
        )
        result = response.json()

        if not result.get("success"):
            print(f"❌ Error: {result}")
            return

        memories = result["data"]["memories"]
        total = result["data"]["count"]

        print(f"Found {total} memories:\n")

        for idx, mem in enumerate(memories, start=offset + 1):
            mem_id = mem.get("id", "unknown")
            content = mem.get("content", "")
            sectors = mem.get("sectors", [])
            tags = mem.get("tags", [])
            timestamp = mem.get("created_at", mem.get("timestamp", ""))
            salience = mem.get("salience", 0.0)

            print(f"{idx}. ID: {mem_id}")
            print(f"   Sectors: {', '.join(sectors)}")
            if tags:
                print(f"   Tags: {', '.join(tags)}")
            print(f"   Salience: {salience:.2f}")
            print(f"   Created: {timestamp}")
            print(f"   Content: {content[:150]}{'...' if len(content) > 150 else ''}")
            print()


async def search_memories(query, limit=20, sectors=None):
    """Search memories by query."""
    print(f"\n=== Searching: '{query}' ===\n")

    payload = {
        "query": query,
        "limit": limit,
        "min_score": 0.1,
    }

    if sectors:
        payload["sectors"] = sectors.split(",")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/memory/search",
            headers=HEADERS,
            json=payload,
        )
        result = response.json()

        if not result.get("success"):
            print(f"❌ Error: {result}")
            return

        memories = result["data"]["memories"]
        print(f"Found {len(memories)} results:\n")

        for idx, mem in enumerate(memories, 1):
            mem_id = mem.get("id", "unknown")
            content = mem.get("content", "")
            sectors = mem.get("sectors", [])
            score = mem.get("score", 0.0)

            print(f"{idx}. Score: {score:.3f} | Sectors: {', '.join(sectors)}")
            print(f"   ID: {mem_id}")
            print(f"   {content[:200]}{'...' if len(content) > 200 else ''}")
            print()


async def export_memories(output_dir="memories"):
    """Export all memories to markdown files."""
    print(f"\n=== Exporting Memories to {output_dir}/ ===\n")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Fetch all memories (paginated)
    all_memories = []
    offset = 0
    limit = 100

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"{BASE_URL}/api/v1/memory",
                headers=HEADERS,
                params={"limit": limit, "offset": offset},
            )
            result = response.json()

            if not result.get("success"):
                print(f"❌ Error: {result}")
                return

            memories = result["data"]["memories"]
            if not memories:
                break

            all_memories.extend(memories)
            offset += limit
            print(f"Fetched {len(all_memories)} memories so far...")

    print(f"\nExporting {len(all_memories)} memories to markdown...\n")

    # Group by sectors for organization
    by_sector = {}

    for mem in all_memories:
        mem_id = mem.get("id", "unknown")
        content = mem.get("content", "")
        sectors = mem.get("sectors", ["uncategorized"])
        tags = mem.get("tags", [])
        timestamp = mem.get("created_at", mem.get("timestamp", ""))
        salience = mem.get("salience", 0.0)

        # Use primary sector for organization
        primary_sector = sectors[0] if sectors else "uncategorized"

        if primary_sector not in by_sector:
            by_sector[primary_sector] = []

        # Create markdown content
        md_content = f"""---
id: {mem_id}
sectors: {json.dumps(sectors)}
tags: {json.dumps(tags)}
salience: {salience}
created_at: {timestamp}
---

# Memory: {mem_id[:8]}

**Sectors**: {', '.join(sectors)}
**Tags**: {', '.join(tags) if tags else 'none'}
**Salience**: {salience:.2f}
**Created**: {timestamp}

## Content

{content}
"""

        by_sector[primary_sector].append({
            "id": mem_id,
            "content": md_content,
            "timestamp": timestamp,
        })

    # Write files organized by sector
    total_written = 0
    for sector, memories in by_sector.items():
        sector_dir = output_path / sector
        sector_dir.mkdir(exist_ok=True)

        for mem in memories:
            # Create filename from timestamp and ID
            mem_id = mem["id"][:8]
            filename = f"{mem_id}.md"

            file_path = sector_dir / filename
            file_path.write_text(mem["content"])
            total_written += 1

        print(f"✓ Wrote {len(memories)} memories to {sector}/")

    # Create index file
    index_content = f"""# OpenMemory Export

**Export Date**: {datetime.now().isoformat()}
**Total Memories**: {len(all_memories)}

## By Sector

"""

    for sector, memories in sorted(by_sector.items()):
        index_content += f"\n### {sector.capitalize()} ({len(memories)} memories)\n\n"
        for mem in sorted(memories, key=lambda x: x["timestamp"], reverse=True)[:10]:
            mem_id = mem["id"][:8]
            index_content += f"- [{mem_id}]({sector}/{mem_id}.md)\n"

    (output_path / "README.md").write_text(index_content)

    print(f"\n✅ Export complete! {total_written} memories exported to {output_dir}/")
    print(f"📄 Index created at {output_dir}/README.md")


async def show_stats():
    """Show memory statistics."""
    print("\n=== OpenMemory Statistics ===\n")

    async with httpx.AsyncClient() as client:
        # Get health
        response = await client.get(
            f"{BASE_URL}/api/v1/memory/health",
            headers=HEADERS,
        )
        health = response.json()

        print(f"Status: {health.get('status', 'unknown')}")
        print(f"Enabled: {health.get('enabled', False)}")
        if "url" in health:
            print(f"URL: {health['url']}")

        # Get memories
        response = await client.get(
            f"{BASE_URL}/api/v1/memory",
            headers=HEADERS,
            params={"limit": 1000, "offset": 0},
        )
        result = response.json()

        if result.get("success"):
            memories = result["data"]["memories"]

            print(f"\nTotal Memories: {len(memories)}")

            # Count by sector
            sector_counts = {}
            tag_counts = {}

            for mem in memories:
                for sector in mem.get("sectors", []):
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1

                for tag in mem.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            print("\nBy Sector:")
            for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
                print(f"  {sector}: {count}")

            if tag_counts:
                print("\nTop Tags:")
                for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:10]:
                    print(f"  {tag}: {count}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        asyncio.run(list_memories(limit=limit))

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: browse_memory.py search 'query text' [--sectors semantic,procedural]")
            return
        query = sys.argv[2]
        sectors = sys.argv[3].replace("--sectors=", "") if len(sys.argv) > 3 and "--sectors" in sys.argv[3] else None
        asyncio.run(search_memories(query, sectors=sectors))

    elif command == "export":
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "memories"
        asyncio.run(export_memories(output_dir=output_dir))

    elif command == "stats":
        asyncio.run(show_stats())

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
