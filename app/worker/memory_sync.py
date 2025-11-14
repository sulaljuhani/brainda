"""
Background task for syncing OpenMemory to markdown files.

This creates a vault-like mirror of OpenMemory contents in /memory_vault,
organized by sector (semantic/, episodic/, etc.)
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from api.adapters.openmemory_adapter import OpenMemoryAdapter, OpenMemoryError

logger = structlog.get_logger()

MEMORY_VAULT_PATH = os.getenv("MEMORY_VAULT_PATH", "/memory_vault")


class MemorySyncService:
    """Service for syncing OpenMemory to markdown files."""

    def __init__(self, vault_path: str = MEMORY_VAULT_PATH):
        self.vault_path = Path(vault_path)
        self.adapter = OpenMemoryAdapter()
        self.enabled = os.getenv("MEMORY_VAULT_SYNC_ENABLED", "false").lower() == "true"

    def is_enabled(self) -> bool:
        """Check if memory vault sync is enabled."""
        return self.enabled

    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """Create a safe filename from text."""
        # Remove special characters
        safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in text)
        # Replace spaces with hyphens
        safe = safe.replace(" ", "-")
        # Limit length
        return safe[:max_length].strip("-")

    def _create_markdown_content(self, memory: Dict) -> str:
        """Create markdown content from memory object."""
        mem_id = memory.get("id", "unknown")
        content = memory.get("content", "")
        sectors = memory.get("sectors", [])
        tags = memory.get("tags", [])
        timestamp = memory.get("created_at", memory.get("timestamp", ""))
        salience = memory.get("salience", 0.0)
        metadata = memory.get("metadata", {})

        # Create frontmatter
        frontmatter = {
            "id": mem_id,
            "sectors": sectors,
            "tags": tags,
            "salience": salience,
            "created_at": timestamp,
            "synced_at": datetime.utcnow().isoformat() + "Z",
        }

        # Add metadata if present
        if metadata:
            frontmatter["metadata"] = metadata

        # Build markdown
        md = "---\n"
        for key, value in frontmatter.items():
            if isinstance(value, (list, dict)):
                md += f"{key}: {json.dumps(value)}\n"
            else:
                md += f"{key}: {value}\n"
        md += "---\n\n"

        # Add header with sectors
        sector_badges = " ".join([f"`{s}`" for s in sectors])
        md += f"# Memory {sector_badges}\n\n"

        # Add metadata section
        md += "**Salience**: " + "★" * int(salience * 5) + f" ({salience:.2f})\n"
        if tags:
            md += f"**Tags**: {', '.join(tags)}\n"
        md += f"**Created**: {timestamp}\n\n"

        # Add content
        md += "---\n\n"
        md += content + "\n"

        return md

    async def sync_all_memories(self, user_id: str) -> Dict:
        """Sync all memories for a user to markdown files."""
        if not self.enabled:
            logger.debug("memory_vault_sync_disabled")
            return {"success": False, "reason": "disabled"}

        logger.info("starting_memory_vault_sync", user_id=user_id)

        try:
            # Create vault directory structure
            self.vault_path.mkdir(parents=True, exist_ok=True)

            user_vault = self.vault_path / user_id
            user_vault.mkdir(exist_ok=True)

            # Create sector directories
            for sector in ["semantic", "episodic", "procedural", "emotional", "reflective", "uncategorized"]:
                (user_vault / sector).mkdir(exist_ok=True)

            # Fetch all memories (paginated)
            all_memories = []
            offset = 0
            limit = 100

            while True:
                try:
                    memories = await self.adapter.get_user_memories(
                        user_id=user_id,
                        limit=limit,
                        offset=offset,
                    )

                    if not memories:
                        break

                    all_memories.extend(memories)
                    offset += limit
                    logger.debug("fetched_memories_batch", count=len(memories), total=len(all_memories))

                except OpenMemoryError as e:
                    logger.error("failed_to_fetch_memories", error=str(e), offset=offset)
                    break

            logger.info("fetched_all_memories", user_id=user_id, total=len(all_memories))

            # Write memories to markdown files
            written = 0
            by_sector = {}

            for memory in all_memories:
                mem_id = memory.get("id", "unknown")
                sectors = memory.get("sectors", ["uncategorized"])
                primary_sector = sectors[0] if sectors else "uncategorized"

                # Track by sector for index
                if primary_sector not in by_sector:
                    by_sector[primary_sector] = []
                by_sector[primary_sector].append(memory)

                # Create filename
                content_preview = self._sanitize_filename(memory.get("content", "")[:30])
                filename = f"{mem_id[:8]}_{content_preview}.md"

                # Write file
                sector_dir = user_vault / primary_sector
                file_path = sector_dir / filename

                md_content = self._create_markdown_content(memory)
                file_path.write_text(md_content)
                written += 1

            # Create index file
            self._create_index(user_vault, by_sector, all_memories)

            logger.info(
                "memory_vault_sync_complete",
                user_id=user_id,
                memories_synced=written,
                sectors=list(by_sector.keys()),
            )

            return {
                "success": True,
                "memories_synced": written,
                "sectors": list(by_sector.keys()),
                "path": str(user_vault),
            }

        except Exception as e:
            logger.error("memory_vault_sync_failed", user_id=user_id, error=str(e))
            return {"success": False, "error": str(e)}

    def _create_index(self, user_vault: Path, by_sector: Dict, all_memories: List):
        """Create an index markdown file."""
        index = f"""# OpenMemory Vault

**Last Synced**: {datetime.utcnow().isoformat()}Z
**Total Memories**: {len(all_memories)}

## Contents

This vault mirrors your OpenMemory contents, organized by primary sector.

"""

        for sector in ["semantic", "episodic", "procedural", "emotional", "reflective", "uncategorized"]:
            memories = by_sector.get(sector, [])
            if not memories:
                continue

            index += f"\n## {sector.capitalize()} ({len(memories)} memories)\n\n"

            # Sort by salience
            sorted_memories = sorted(memories, key=lambda m: m.get("salience", 0), reverse=True)

            for mem in sorted_memories[:20]:  # Show top 20
                mem_id = mem.get("id", "unknown")[:8]
                content = mem.get("content", "")[:60].replace("\n", " ")
                salience = mem.get("salience", 0.0)
                tags = mem.get("tags", [])

                content_preview = self._sanitize_filename(mem.get("content", "")[:30])
                filename = f"{mem_id}_{content_preview}.md"

                tag_str = f" `{' '.join(tags)}`" if tags else ""
                index += f"- [{content}...]({sector}/{filename}) ★{salience:.1f}{tag_str}\n"

            if len(sorted_memories) > 20:
                index += f"\n_...and {len(sorted_memories) - 20} more in `{sector}/`_\n"

        # Add usage instructions
        index += """

## Usage

- Browse memories by sector in the subdirectories
- Each file contains frontmatter with metadata
- Salience (★) indicates importance (0.0-1.0)
- Files are read-only mirrors of OpenMemory

## Sectors Explained

- **semantic**: Facts and conceptual knowledge
- **episodic**: Specific events and experiences
- **procedural**: How-to knowledge and workflows
- **emotional**: Emotional context and sentiment
- **reflective**: Insights and meta-cognition

## Syncing

To manually trigger a sync:
```bash
curl -X POST http://localhost:8000/api/v1/memory/sync \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Or use the CLI:
```bash
python scripts/browse_memory.py export
```
"""

        (user_vault / "README.md").write_text(index)


async def sync_memory_for_user(user_id: str) -> Dict:
    """Sync memory vault for a specific user."""
    service = MemorySyncService()
    return await service.sync_all_memories(user_id)
