#!/usr/bin/env python3
"""
MCP Server for OpenMemory Integration.

This MCP (Model Context Protocol) server allows AI assistants to store
and retrieve memories from OpenMemory through VIB's API.

Use cases:
- Claude Desktop can use this to store conversations
- Custom AI agents can integrate with OpenMemory
- Other applications can use MCP to access VIB's memory system

Installation:
    pip install mcp httpx

Usage:
    # Run the server
    python mcp/openmemory_server.py

    # Add to Claude Desktop config (~/.config/claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "vib-openmemory": {
          "command": "python",
          "args": ["/path/to/brainda/mcp/openmemory_server.py"],
          "env": {
            "VIB_URL": "http://localhost:8000",
            "VIB_API_TOKEN": "your-token-here"
          }
        }
      }
    }
"""

import asyncio
import os
import sys
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)


# Configuration
VIB_URL = os.getenv("VIB_URL", "http://localhost:8000")
VIB_API_TOKEN = os.getenv("VIB_API_TOKEN")

if not VIB_API_TOKEN:
    print("Error: VIB_API_TOKEN environment variable not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {VIB_API_TOKEN}",
    "Content-Type": "application/json",
}


# Create MCP server
app = Server("vib-openmemory")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="store_memory",
            description=(
                "Store a new memory in OpenMemory. The memory will be automatically "
                "classified into sectors (semantic, episodic, procedural, emotional, reflective). "
                "Use this to remember important facts, preferences, or conversation context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The memory content to store (e.g., 'User prefers dark mode')",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization (e.g., ['preference', 'ui'])",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata (e.g., {'source': 'chat', 'topic': 'settings'})",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="search_memories",
            description=(
                "Search memories by semantic similarity. Returns relevant memories ranked by "
                "composite score (60% similarity + 20% salience + 10% recency + 10% link weight). "
                "Use this to recall previous context, facts, or preferences."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'user preferences', 'previous discussions about deployment')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5,
                    },
                    "sectors": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["semantic", "episodic", "procedural", "emotional", "reflective"],
                        },
                        "description": "Filter by specific sectors (optional)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (optional)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="store_conversation",
            description=(
                "Store a conversation turn (user message + assistant response) in OpenMemory. "
                "This is automatically classified as episodic memory and can be recalled later "
                "for context continuity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string",
                        "description": "The user's message",
                    },
                    "assistant_message": {
                        "type": "string",
                        "description": "The assistant's response",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata (e.g., {'topic': 'python', 'sources_used': 3})",
                    },
                },
                "required": ["user_message", "assistant_message"],
            },
        ),
        Tool(
            name="list_memories",
            description=(
                "List all memories in chronological order. Use this to review what's stored "
                "or get an overview of the memory system."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories (default: 20)",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default: 0)",
                        "default": 0,
                    },
                },
            },
        ),
        Tool(
            name="get_conversation_context",
            description=(
                "Get relevant conversation context for the current query. This searches "
                "OpenMemory for related past interactions and formats them for use in the prompt."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Current query or topic",
                    },
                    "max_memories": {
                        "type": "integer",
                        "description": "Maximum memories to retrieve (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "store_memory":
                content = arguments["content"]
                tags = arguments.get("tags", [])
                metadata = arguments.get("metadata", {})

                response = await client.post(
                    f"{VIB_URL}/api/v1/memory",
                    headers=HEADERS,
                    json={
                        "content": content,
                        "tags": tags,
                        "metadata": metadata,
                    },
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    memory = result["data"]
                    sectors = memory.get("sectors", [])
                    mem_id = memory.get("id")

                    return [
                        TextContent(
                            type="text",
                            text=f"✓ Memory stored successfully\n"
                            f"ID: {mem_id}\n"
                            f"Sectors: {', '.join(sectors)}\n"
                            f"Salience: {memory.get('salience', 0):.2f}",
                        )
                    ]
                else:
                    return [TextContent(type="text", text=f"✗ Failed: {result}")]

            elif name == "search_memories":
                query = arguments["query"]
                limit = arguments.get("limit", 5)
                sectors = arguments.get("sectors")
                tags = arguments.get("tags")

                response = await client.post(
                    f"{VIB_URL}/api/v1/memory/search",
                    headers=HEADERS,
                    json={
                        "query": query,
                        "limit": limit,
                        "sectors": sectors,
                        "tags": tags,
                    },
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    memories = result["data"]["memories"]

                    if not memories:
                        return [TextContent(type="text", text="No memories found.")]

                    output = f"Found {len(memories)} memories:\n\n"

                    for idx, mem in enumerate(memories, 1):
                        content = mem.get("content", "")
                        sectors = mem.get("sectors", [])
                        score = mem.get("score", 0.0)
                        salience = mem.get("salience", 0.0)

                        output += f"{idx}. Score: {score:.3f} | Salience: {salience:.2f}\n"
                        output += f"   Sectors: {', '.join(sectors)}\n"
                        output += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n\n"

                    return [TextContent(type="text", text=output)]
                else:
                    return [TextContent(type="text", text=f"✗ Failed: {result}")]

            elif name == "store_conversation":
                user_msg = arguments["user_message"]
                assistant_msg = arguments["assistant_message"]
                metadata = arguments.get("metadata", {})

                # Format as conversation
                content = f"User: {user_msg}\n\nAssistant: {assistant_msg}"

                response = await client.post(
                    f"{VIB_URL}/api/v1/memory",
                    headers=HEADERS,
                    json={
                        "content": content,
                        "tags": ["conversation", "mcp"],
                        "metadata": {**metadata, "source": "mcp"},
                    },
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    memory = result["data"]
                    sectors = memory.get("sectors", [])

                    return [
                        TextContent(
                            type="text",
                            text=f"✓ Conversation stored\n"
                            f"Sectors: {', '.join(sectors)}",
                        )
                    ]
                else:
                    return [TextContent(type="text", text=f"✗ Failed: {result}")]

            elif name == "list_memories":
                limit = arguments.get("limit", 20)
                offset = arguments.get("offset", 0)

                response = await client.get(
                    f"{VIB_URL}/api/v1/memory",
                    headers=HEADERS,
                    params={"limit": limit, "offset": offset},
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    memories = result["data"]["memories"]
                    total = result["data"]["count"]

                    output = f"Memories ({offset + 1}-{offset + len(memories)} of {total}):\n\n"

                    for idx, mem in enumerate(memories, offset + 1):
                        content = mem.get("content", "")
                        sectors = mem.get("sectors", [])
                        tags = mem.get("tags", [])

                        output += f"{idx}. {', '.join(sectors)}\n"
                        if tags:
                            output += f"   Tags: {', '.join(tags)}\n"
                        output += f"   {content[:150]}{'...' if len(content) > 150 else ''}\n\n"

                    return [TextContent(type="text", text=output)]
                else:
                    return [TextContent(type="text", text=f"✗ Failed: {result}")]

            elif name == "get_conversation_context":
                query = arguments["query"]
                max_memories = arguments.get("max_memories", 10)

                response = await client.get(
                    f"{VIB_URL}/api/v1/memory/context/preview",
                    headers=HEADERS,
                    params={"query": query, "max_memories": max_memories},
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    context = result["data"]["context"]

                    if not context:
                        return [TextContent(type="text", text="No relevant context found.")]

                    return [
                        TextContent(
                            type="text",
                            text=f"Conversation Context:\n\n{context}",
                        )
                    ]
                else:
                    return [TextContent(type="text", text=f"✗ Failed: {result}")]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"✗ HTTP Error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"✗ Error: {e}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
