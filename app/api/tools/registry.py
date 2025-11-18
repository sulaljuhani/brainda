"""Central tool registry for LLM orchestration."""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import structlog

from api.tools.knowledge_tools import KNOWLEDGE_TOOLS, execute_knowledge_tool
from api.tools.task_tools import TASK_TOOLS, execute_task_tool
from api.tools.reminder_tools import REMINDER_TOOLS, execute_reminder_tool
from api.tools.calendar import CALENDAR_TOOLS, execute_calendar_tool
from api.tools.analysis_tools import ANALYSIS_TOOLS, execute_analysis_tool
from api.tools.vision_tools import VISION_TOOLS, execute_vision_tool
from api.tools.web_tools import WEB_TOOLS, execute_web_tool

logger = structlog.get_logger()


class ToolRegistry:
    """Central registry for all LLM tools."""

    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._executors: dict[str, Callable] = {}
        self._register_all_tools()

    def _register_all_tools(self):
        """Register all available tools."""
        # Knowledge tools
        for tool in KNOWLEDGE_TOOLS:
            self.register(tool, execute_knowledge_tool)

        # Task tools
        for tool in TASK_TOOLS:
            self.register(tool, execute_task_tool)

        # Reminder tools
        for tool in REMINDER_TOOLS:
            self.register(tool, execute_reminder_tool)

        # Calendar tools
        for tool in CALENDAR_TOOLS:
            self.register(tool, execute_calendar_tool)

        # Analysis tools
        for tool in ANALYSIS_TOOLS:
            self.register(tool, execute_analysis_tool)

        # Vision tools
        for tool in VISION_TOOLS:
            self.register(tool, execute_vision_tool)

        # Web tools
        for tool in WEB_TOOLS:
            self.register(tool, execute_web_tool)

        logger.info(
            "tool_registry_initialized",
            total_tools=len(self._tools),
            tool_names=list(self._tools.keys()),
        )

    def register(self, tool_spec: dict, executor: Callable):
        """Register a tool with its executor."""
        tool_name = tool_spec["function"]["name"]
        self._tools[tool_name] = tool_spec
        self._executors[tool_name] = executor

    def get_all_tools(self) -> list[dict]:
        """Get all tool specifications for LLM."""
        return list(self._tools.values())

    def get_tools_by_category(self, category: str) -> list[dict]:
        """Get tools filtered by category."""
        return [
            tool
            for tool in self._tools.values()
            if tool.get("category") == category
        ]

    def get_tool_names(self) -> list[str]:
        """Get list of all tool names."""
        return list(self._tools.keys())

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: UUID,
        db,
    ) -> dict[str, Any]:
        """Execute a tool by name."""
        if tool_name not in self._executors:
            logger.warning("unknown_tool_requested", tool_name=tool_name)
            return {
                "success": False,
                "error": {
                    "code": "UNKNOWN_TOOL",
                    "message": f"Tool '{tool_name}' not found",
                },
            }

        executor = self._executors[tool_name]

        try:
            # Different tools have different signatures
            # Knowledge tools don't take db parameter
            if tool_name in [tool["function"]["name"] for tool in KNOWLEDGE_TOOLS]:
                return await executor(tool_name, arguments, user_id)
            else:
                return await executor(tool_name, arguments, user_id, db)

        except Exception as exc:
            logger.error(
                "tool_execution_failed",
                tool_name=tool_name,
                error=str(exc),
            )
            return {
                "success": False,
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": f"Tool execution failed: {str(exc)}",
                },
            }


# Global singleton instance
_registry_instance: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ToolRegistry()
    return _registry_instance
