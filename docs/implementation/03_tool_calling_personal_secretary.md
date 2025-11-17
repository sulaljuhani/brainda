# Tool Calling & Personal Secretary - Implementation Plan

## Vision
Transform Brainda from a passive chat assistant into a **proactive personal secretary** that:
- Executes actions on your behalf (create notes, tasks, events)
- Monitors your schedule and sends proactive reminders
- Generates daily summaries and insights
- Runs scheduled agents (morning briefing, evening review)
- Learns your patterns and suggests optimizations

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                          │
│  Chat, Notifications, Dashboard, Task Suggestions            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│               Tool Orchestration Engine                      │
│  - Parse user intent                                         │
│  - Select appropriate tools                                  │
│  - Execute tool chain                                        │
│  - Format results for user                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        │             │             │              │
┌───────▼──────┐ ┌───▼────┐ ┌─────▼─────┐ ┌──────▼──────┐
│ Knowledge    │ │ Action │ │  Vision   │ │   External  │
│ Tools        │ │ Tools  │ │  Tools    │ │   Tools     │
├──────────────┤ ├────────┤ ├───────────┤ ├─────────────┤
│ • Search KB  │ │ • Notes│ │ • OCR     │ │ • Web       │
│ • RAG Q&A    │ │ • Tasks│ │ • Image   │ │ • Search    │
│ • Vector     │ │ • Events│ │  Analysis │ │ • Weather   │
│   Search     │ │ • Remind│ │           │ │ • News      │
└──────────────┘ └────────┘ └───────────┘ └─────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Scheduled Agent System                          │
│  - Morning Briefing Agent (7:00 AM)                          │
│  - Evening Review Agent (8:00 PM)                            │
│  - Reminder Watcher (continuous)                             │
│  - Weekly Summary Agent (Sunday 6:00 PM)                     │
│  - Smart Suggestions Agent (on-demand)                       │
└──────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Complete Tool Registry (4-5 hours)

### File: `app/api/tools/registry.py` (NEW)

Central registry of all available tools:

```python
"""Complete tool registry for LLM orchestration."""
from typing import Dict, List, Callable
from uuid import UUID

from api.tools.knowledge_tools import KNOWLEDGE_TOOLS, execute_knowledge_tool
from api.tools.action_tools import ACTION_TOOLS, execute_action_tool
from api.tools.vision_tools import VISION_TOOLS, execute_vision_tool
from api.tools.web_tools import WEB_TOOLS, execute_web_tool
from api.tools.analysis_tools import ANALYSIS_TOOLS, execute_analysis_tool


class ToolRegistry:
    """Central registry for all LLM tools."""

    def __init__(self):
        self._tools: Dict[str, dict] = {}
        self._executors: Dict[str, Callable] = {}
        self._register_all_tools()

    def _register_all_tools(self):
        """Register all available tools."""
        # Knowledge tools
        for tool in KNOWLEDGE_TOOLS:
            self.register(tool, execute_knowledge_tool)

        # Action tools (CRUD operations)
        for tool in ACTION_TOOLS:
            self.register(tool, execute_action_tool)

        # Vision tools
        for tool in VISION_TOOLS:
            self.register(tool, execute_vision_tool)

        # Web tools
        for tool in WEB_TOOLS:
            self.register(tool, execute_web_tool)

        # Analysis tools
        for tool in ANALYSIS_TOOLS:
            self.register(tool, execute_analysis_tool)

    def register(self, tool_spec: dict, executor: Callable):
        """Register a tool with its executor."""
        tool_name = tool_spec["function"]["name"]
        self._tools[tool_name] = tool_spec
        self._executors[tool_name] = executor

    def get_all_tools(self) -> List[dict]:
        """Get all tool specifications for LLM."""
        return list(self._tools.values())

    def get_tools_by_category(self, category: str) -> List[dict]:
        """Get tools filtered by category."""
        return [
            tool for tool in self._tools.values()
            if tool.get("category") == category
        ]

    async def execute(self, tool_name: str, arguments: dict, user_id: UUID) -> dict:
        """Execute a tool by name."""
        if tool_name not in self._executors:
            return {
                "success": False,
                "error": {"code": "UNKNOWN_TOOL", "message": f"Tool '{tool_name}' not found"}
            }

        executor = self._executors[tool_name]
        return await executor(tool_name, arguments, user_id)


# Global singleton
tool_registry = ToolRegistry()
```

---

### File: `app/api/tools/action_tools.py` (NEW)

Complete CRUD operations for all entities:

```python
"""Action tools - CRUD operations for notes, tasks, events, reminders."""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
import structlog

from api.services.task_service import TaskService
from api.services.reminder_service import ReminderService
from api.services.calendar_service import CalendarService
from api.dependencies import get_db

logger = structlog.get_logger()

ACTION_TOOLS = [
    # ============ NOTES ============
    {
        "type": "function",
        "category": "notes",
        "function": {
            "name": "create_note",
            "description": "Create a new note in the knowledge base",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Note title"},
                    "content": {"type": "string", "description": "Note content (markdown supported)"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization"
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "category": "notes",
        "function": {
            "name": "update_note",
            "description": "Update an existing note",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "Note UUID"},
                    "title": {"type": "string", "description": "New title (optional)"},
                    "content": {"type": "string", "description": "New content (optional)"},
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "category": "notes",
        "function": {
            "name": "delete_note",
            "description": "Delete a note permanently",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "Note UUID"},
                },
                "required": ["note_id"],
            },
        },
    },

    # ============ TASKS ============
    {
        "type": "function",
        "category": "tasks",
        "function": {
            "name": "create_task",
            "description": "Create a new task/todo item",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Detailed description"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Task priority"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in ISO format (YYYY-MM-DD) or relative (tomorrow, next week)"
                    },
                    "category_id": {"type": "string", "description": "Category UUID (optional)"},
                    "parent_task_id": {"type": "string", "description": "Parent task UUID for subtasks"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "category": "tasks",
        "function": {
            "name": "update_task",
            "description": "Update task details",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "status": {"type": "string", "enum": ["active", "completed", "cancelled"]},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "category": "tasks",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "category": "tasks",
        "function": {
            "name": "list_tasks",
            "description": "Get list of tasks with filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "all"],
                        "description": "Filter by status"
                    },
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "due_soon": {
                        "type": "boolean",
                        "description": "Show only tasks due in next 3 days"
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "category": "tasks",
        "function": {
            "name": "delete_task",
            "description": "Delete a task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                },
                "required": ["task_id"],
            },
        },
    },

    # ============ REMINDERS ============
    {
        "type": "function",
        "category": "reminders",
        "function": {
            "name": "create_reminder",
            "description": "Set a reminder for a specific time",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Reminder title"},
                    "body": {"type": "string", "description": "Reminder details"},
                    "due_at": {
                        "type": "string",
                        "description": "When to trigger (ISO datetime or relative: 'tomorrow at 2pm', 'in 30 minutes')"
                    },
                    "recurrence": {
                        "type": "string",
                        "description": "RRULE for recurring reminders (daily, weekly, etc.)"
                    },
                },
                "required": ["title", "due_at"],
            },
        },
    },
    {
        "type": "function",
        "category": "reminders",
        "function": {
            "name": "list_reminders",
            "description": "Get upcoming reminders",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "fired", "all"]},
                    "limit": {"type": "integer", "description": "Max number to return"},
                },
            },
        },
    },
    {
        "type": "function",
        "category": "reminders",
        "function": {
            "name": "cancel_reminder",
            "description": "Cancel a pending reminder",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "Reminder UUID"},
                },
                "required": ["reminder_id"],
            },
        },
    },

    # ============ CALENDAR EVENTS ============
    {
        "type": "function",
        "category": "calendar",
        "function": {
            "name": "create_event",
            "description": "Create a calendar event",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "description": {"type": "string", "description": "Event details"},
                    "start_time": {
                        "type": "string",
                        "description": "Start time (ISO datetime or relative)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time (ISO datetime or relative)"
                    },
                    "location": {"type": "string", "description": "Event location"},
                    "recurrence": {"type": "string", "description": "RRULE for recurring events"},
                },
                "required": ["title", "start_time"],
            },
        },
    },
    {
        "type": "function",
        "category": "calendar",
        "function": {
            "name": "list_events",
            "description": "Get calendar events in a time range",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date (ISO or 'today', 'this week')"},
                    "end_date": {"type": "string", "description": "End date"},
                    "limit": {"type": "integer", "description": "Max events to return"},
                },
            },
        },
    },
    {
        "type": "function",
        "category": "calendar",
        "function": {
            "name": "update_event",
            "description": "Update calendar event",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event UUID"},
                    "title": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "category": "calendar",
        "function": {
            "name": "delete_event",
            "description": "Delete calendar event",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event UUID"},
                },
                "required": ["event_id"],
            },
        },
    },
]


async def execute_action_tool(tool_name: str, arguments: dict, user_id: UUID) -> dict:
    """Execute action tools (CRUD operations)."""

    try:
        # ============ NOTES ============
        if tool_name == "create_note":
            from api.services.note_service import NoteService
            async with get_db_connection() as db:
                service = NoteService(db)
                note = await service.create_note(
                    user_id=user_id,
                    title=arguments["title"],
                    content=arguments["content"],
                    tags=arguments.get("tags", []),
                )
                return {"success": True, "data": {"note_id": str(note["id"]), "title": note["title"]}}

        elif tool_name == "update_note":
            from api.services.note_service import NoteService
            async with get_db_connection() as db:
                service = NoteService(db)
                note = await service.update_note(
                    note_id=UUID(arguments["note_id"]),
                    user_id=user_id,
                    title=arguments.get("title"),
                    content=arguments.get("content"),
                )
                return {"success": True, "data": {"note_id": str(note["id"])}}

        elif tool_name == "delete_note":
            from api.services.note_service import NoteService
            async with get_db_connection() as db:
                service = NoteService(db)
                await service.delete_note(UUID(arguments["note_id"]), user_id)
                return {"success": True, "data": {"deleted": True}}

        # ============ TASKS ============
        elif tool_name == "create_task":
            async with get_db_connection() as db:
                service = TaskService(db)

                # Parse relative dates
                due_date = None
                if arguments.get("due_date"):
                    due_date = parse_relative_date(arguments["due_date"])

                task = await service.create_task(
                    user_id=user_id,
                    title=arguments["title"],
                    description=arguments.get("description"),
                    priority=arguments.get("priority", "medium"),
                    due_date=due_date,
                    category_id=UUID(arguments["category_id"]) if arguments.get("category_id") else None,
                    parent_task_id=UUID(arguments["parent_task_id"]) if arguments.get("parent_task_id") else None,
                )
                return {"success": True, "data": {"task_id": str(task["id"]), "title": task["title"]}}

        elif tool_name == "update_task":
            async with get_db_connection() as db:
                service = TaskService(db)
                task = await service.update_task(
                    task_id=UUID(arguments["task_id"]),
                    user_id=user_id,
                    **{k: v for k, v in arguments.items() if k != "task_id"}
                )
                return {"success": True, "data": task}

        elif tool_name == "complete_task":
            async with get_db_connection() as db:
                service = TaskService(db)
                task = await service.complete_task(UUID(arguments["task_id"]), user_id)
                return {"success": True, "data": {"task_id": str(task["id"]), "completed": True}}

        elif tool_name == "list_tasks":
            async with get_db_connection() as db:
                service = TaskService(db)

                # Apply filters
                filters = {}
                if arguments.get("status") and arguments["status"] != "all":
                    filters["status"] = arguments["status"]
                if arguments.get("priority"):
                    filters["priority"] = arguments["priority"]

                tasks = await service.list_tasks(user_id, **filters)

                # Filter due soon
                if arguments.get("due_soon"):
                    three_days_from_now = datetime.now() + timedelta(days=3)
                    tasks = [t for t in tasks if t.get("due_date") and t["due_date"] <= three_days_from_now]

                return {
                    "success": True,
                    "data": {
                        "tasks": [
                            {
                                "id": str(t["id"]),
                                "title": t["title"],
                                "priority": t.get("priority"),
                                "status": t.get("status"),
                                "due_date": t.get("due_date").isoformat() if t.get("due_date") else None,
                            }
                            for t in tasks
                        ]
                    }
                }

        elif tool_name == "delete_task":
            async with get_db_connection() as db:
                service = TaskService(db)
                await service.delete_task(UUID(arguments["task_id"]), user_id)
                return {"success": True, "data": {"deleted": True}}

        # ============ REMINDERS ============
        elif tool_name == "create_reminder":
            async with get_db_connection() as db:
                service = ReminderService(db)

                # Parse relative datetime
                due_at = parse_relative_datetime(arguments["due_at"])

                reminder = await service.create_reminder(
                    user_id=user_id,
                    title=arguments["title"],
                    body=arguments.get("body", ""),
                    due_at_utc=due_at,
                    recurrence_rule=arguments.get("recurrence"),
                )
                return {"success": True, "data": {"reminder_id": str(reminder["id"]), "due_at": due_at.isoformat()}}

        # ... (implement remaining tools)

        return {
            "success": False,
            "error": {"code": "NOT_IMPLEMENTED", "message": f"Tool {tool_name} not yet implemented"}
        }

    except Exception as exc:
        logger.error("action_tool_failed", tool=tool_name, error=str(exc))
        return {
            "success": False,
            "error": {"code": "EXECUTION_ERROR", "message": str(exc)}
        }


def parse_relative_date(date_str: str) -> datetime:
    """Parse relative date strings like 'tomorrow', 'next week', '2024-12-25'."""
    import dateparser
    parsed = dateparser.parse(date_str, settings={'PREFER_DATES_FROM': 'future'})
    if not parsed:
        raise ValueError(f"Could not parse date: {date_str}")
    return parsed


def parse_relative_datetime(datetime_str: str) -> datetime:
    """Parse relative datetime strings like 'tomorrow at 2pm', 'in 30 minutes'."""
    import dateparser
    parsed = dateparser.parse(datetime_str, settings={'PREFER_DATES_FROM': 'future'})
    if not parsed:
        raise ValueError(f"Could not parse datetime: {datetime_str}")
    return parsed
```

---

### File: `app/api/tools/analysis_tools.py` (NEW)

Tools for insights and analysis:

```python
"""Analysis tools - Generate insights, summaries, and suggestions."""

ANALYSIS_TOOLS = [
    {
        "type": "function",
        "category": "analysis",
        "function": {
            "name": "generate_daily_summary",
            "description": "Generate summary of today's activities, tasks, and notes",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date to summarize (default: today)"},
                    "include_sections": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["tasks", "events", "notes", "reminders"]},
                        "description": "Sections to include in summary"
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "category": "analysis",
        "function": {
            "name": "suggest_tasks_from_notes",
            "description": "Analyze notes and suggest actionable tasks",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific notes to analyze (optional)"
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "category": "analysis",
        "function": {
            "name": "analyze_productivity",
            "description": "Analyze productivity patterns and provide insights",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "this_week", "this_month"],
                        "description": "Time period to analyze"
                    },
                },
            },
        },
    },
]


async def execute_analysis_tool(tool_name: str, arguments: dict, user_id: UUID) -> dict:
    """Execute analysis tools."""

    if tool_name == "generate_daily_summary":
        return await generate_daily_summary(user_id, arguments.get("date"))

    elif tool_name == "suggest_tasks_from_notes":
        return await suggest_tasks_from_notes(user_id, arguments.get("note_ids"))

    elif tool_name == "analyze_productivity":
        return await analyze_productivity(user_id, arguments.get("period", "today"))

    return {"success": False, "error": "Unknown analysis tool"}


async def generate_daily_summary(user_id: UUID, date: Optional[str] = None) -> dict:
    """Generate comprehensive daily summary."""
    from api.services.task_service import TaskService
    from api.services.calendar_service import CalendarService
    from api.services.rag_service import RAGService

    target_date = parse_relative_date(date) if date else datetime.now()

    async with get_db_connection() as db:
        task_service = TaskService(db)
        calendar_service = CalendarService(db)

        # Get completed tasks
        completed_tasks = await task_service.list_tasks(
            user_id,
            status="completed",
            completed_after=target_date.replace(hour=0, minute=0),
        )

        # Get events
        events = await calendar_service.list_events(
            user_id,
            start_date=target_date,
            end_date=target_date + timedelta(days=1),
        )

        # Get active tasks
        active_tasks = await task_service.list_tasks(user_id, status="active")

        summary = {
            "date": target_date.date().isoformat(),
            "completed_tasks": len(completed_tasks),
            "total_events": len(events),
            "pending_tasks": len([t for t in active_tasks if t.get("due_date") and t["due_date"].date() <= target_date.date()]),
            "tasks": [{"title": t["title"], "status": t["status"]} for t in completed_tasks],
            "events": [{"title": e["title"], "start": e["start_time"].isoformat()} for e in events],
        }

        return {"success": True, "data": summary}
```

---

## Phase 2: Tool Orchestration Engine (6-8 hours)

### File: `app/api/services/orchestration_service.py` (NEW)

Intelligent tool selection and execution:

```python
"""Tool orchestration - Intelligently select and execute tool chains."""
import structlog
from typing import List, Dict, Any, Optional
from uuid import UUID

from api.tools.registry import tool_registry
from api.adapters.llm_adapter import get_llm_adapter
from api.metrics import tool_calls_total

logger = structlog.get_logger()


class ToolOrchestrationService:
    """Orchestrate complex multi-tool workflows."""

    def __init__(self, user_id: UUID):
        self.user_id = user_id
        self.llm_adapter = get_llm_adapter()
        self.conversation_history: List[Dict[str, Any]] = []

    async def execute_user_request(
        self,
        user_message: str,
        context: Optional[str] = None,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute user request with autonomous tool usage.

        Flow:
        1. LLM analyzes request and decides which tools to use
        2. Execute tools and collect results
        3. LLM synthesizes final response from tool results
        4. Return response + tool call trace for transparency
        """

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Build user prompt with context
        full_prompt = user_message
        if context:
            full_prompt = f"{context}\n\n{user_message}"

        # Conversation state
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_prompt},
        ]

        tool_call_history = []
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            logger.info(
                "orchestration_iteration",
                iteration=iteration,
                user_id=str(self.user_id),
            )

            # Call LLM with tools
            response = await self.llm_adapter.complete_with_tools(
                prompt=messages[-1]["content"],
                tools=tool_registry.get_all_tools(),
                system_prompt=system_prompt if iteration == 1 else None,
            )

            # Case 1: LLM returns final text response (no more tools needed)
            if response["type"] == "text":
                logger.info(
                    "orchestration_complete",
                    iterations=iteration,
                    tools_used=len(tool_call_history),
                )

                return {
                    "response": response["content"],
                    "tool_calls": tool_call_history,
                    "iterations": iteration,
                }

            # Case 2: LLM wants to use tools
            elif response["type"] == "tool_calls":
                tool_results = []

                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]

                    logger.info(
                        "executing_tool",
                        tool_name=tool_name,
                        arguments=arguments,
                        user_id=str(self.user_id),
                    )

                    # Execute tool
                    result = await tool_registry.execute(
                        tool_name=tool_name,
                        arguments=arguments,
                        user_id=self.user_id,
                    )

                    # Track metrics
                    status = "success" if result.get("success") else "error"
                    tool_calls_total.labels(tool_name=tool_name, status=status).inc()

                    tool_results.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": result,
                    })

                    # Add to history for transparency
                    tool_call_history.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "success": result.get("success", False),
                        "data": result.get("data"),
                    })

                # Add tool results to conversation
                tool_results_text = self._format_tool_results(tool_results)
                messages.append({
                    "role": "assistant",
                    "content": f"Tool calls executed. Results:\n{tool_results_text}"
                })

                # Ask LLM to synthesize or continue
                messages.append({
                    "role": "user",
                    "content": "Based on these results, provide a final response to the user or use additional tools if needed."
                })

        # Max iterations reached
        logger.warning("orchestration_max_iterations", user_id=str(self.user_id))

        return {
            "response": "I've completed several steps but need more iterations to finish. Here's what I've done so far:\n\n" +
                       self._summarize_tool_calls(tool_call_history),
            "tool_calls": tool_call_history,
            "iterations": max_iterations,
            "truncated": True,
        }

    def _build_system_prompt(self) -> str:
        """Build system prompt with available tools."""
        return f"""You are a personal AI secretary with access to the user's complete system.

You can perform actions using the available tools. When the user makes a request:
1. Determine which tools are needed
2. Execute tools in the correct order
3. Synthesize results into a helpful response

Available tool categories:
- Knowledge: Search notes, documents, get answers from knowledge base
- Actions: Create/update/delete notes, tasks, events, reminders
- Analysis: Generate summaries, insights, suggestions
- Vision: Extract text from images (OCR)
- Web: Search internet, fetch web pages

Important guidelines:
- Be proactive: If user says "remind me to call John tomorrow", use create_reminder tool
- Be precise: When creating tasks/events, ask for clarification if needed
- Be transparent: Mention which actions you took
- Be efficient: Use multiple tools in parallel when possible
- Be smart: Learn from context and conversation history

Current time: {datetime.now().isoformat()}
"""

    def _format_tool_results(self, tool_results: List[Dict]) -> str:
        """Format tool results for LLM consumption."""
        formatted = []
        for result in tool_results:
            tool_name = result["tool"]
            success = result["result"].get("success", False)
            data = result["result"].get("data", {})

            if success:
                formatted.append(f"✓ {tool_name}: {data}")
            else:
                error = result["result"].get("error", {})
                formatted.append(f"✗ {tool_name}: {error.get('message', 'Unknown error')}")

        return "\n".join(formatted)

    def _summarize_tool_calls(self, tool_calls: List[Dict]) -> str:
        """Summarize tool calls for user."""
        summary = []
        for call in tool_calls:
            tool = call["tool"]
            success = call["success"]
            status = "✓" if success else "✗"
            summary.append(f"{status} {tool}: {call.get('data', 'No data')}")

        return "\n".join(summary)
```

---

## Phase 3: Scheduled Agent System (8-10 hours)

### File: `app/worker/agents.py` (NEW)

Autonomous agents that run on schedule:

```python
"""Scheduled autonomous agents for proactive assistance."""
import asyncio
from datetime import datetime, time, timedelta
from typing import Optional
from uuid import UUID

import structlog
from celery import Task

from worker.tasks import celery_app
from api.services.orchestration_service import ToolOrchestrationService
from api.services.notification_service import NotificationService

logger = structlog.get_logger()


# ============ MORNING BRIEFING AGENT ============

@celery_app.task(name="agents.morning_briefing")
def morning_briefing_agent(user_id: str):
    """
    Morning briefing agent - Runs at 7:00 AM daily.

    Provides:
    - Today's schedule (events, meetings)
    - High-priority tasks
    - Unread reminders
    - Weather forecast
    - News headlines relevant to user's interests
    """
    asyncio.run(_run_morning_briefing(UUID(user_id)))


async def _run_morning_briefing(user_id: UUID):
    """Generate and deliver morning briefing."""
    logger.info("morning_briefing_start", user_id=str(user_id))

    orchestrator = ToolOrchestrationService(user_id)

    # Generate briefing using tools
    briefing_prompt = """
    Generate a morning briefing for the user. Include:
    1. Today's calendar events
    2. High-priority tasks due today or overdue
    3. Pending reminders
    4. A motivational message

    Format it clearly and concisely.
    """

    result = await orchestrator.execute_user_request(briefing_prompt)

    # Send notification
    notification_service = NotificationService()
    await notification_service.send_notification(
        user_id=user_id,
        title="☀️ Good morning! Here's your briefing",
        body=result["response"],
        type="morning_briefing",
        priority="high",
    )

    logger.info("morning_briefing_complete", user_id=str(user_id))


# ============ EVENING REVIEW AGENT ============

@celery_app.task(name="agents.evening_review")
def evening_review_agent(user_id: str):
    """
    Evening review agent - Runs at 8:00 PM daily.

    Provides:
    - Summary of today's accomplishments
    - Tasks completed vs planned
    - Tomorrow's preview
    - Suggestions for improvement
    """
    asyncio.run(_run_evening_review(UUID(user_id)))


async def _run_evening_review(user_id: UUID):
    """Generate and deliver evening review."""
    logger.info("evening_review_start", user_id=str(user_id))

    orchestrator = ToolOrchestrationService(user_id)

    review_prompt = """
    Generate an evening review for the user. Include:
    1. Tasks completed today (celebrate wins!)
    2. Tasks that were postponed (no judgment, just awareness)
    3. Preview of tomorrow's important tasks and events
    4. One productivity tip or reflection

    Keep it positive and actionable.
    """

    result = await orchestrator.execute_user_request(review_prompt)

    # Send notification
    notification_service = NotificationService()
    await notification_service.send_notification(
        user_id=user_id,
        title="🌙 Evening Review",
        body=result["response"],
        type="evening_review",
        priority="normal",
    )

    logger.info("evening_review_complete", user_id=str(user_id))


# ============ REMINDER WATCHER AGENT ============

@celery_app.task(name="agents.reminder_watcher")
def reminder_watcher_agent():
    """
    Reminder watcher - Runs every minute.

    Checks for due reminders and sends proactive notifications.
    """
    asyncio.run(_check_and_fire_reminders())


async def _check_and_fire_reminders():
    """Check for due reminders and fire notifications."""
    from api.services.reminder_service import ReminderService

    async with get_db_connection() as db:
        service = ReminderService(db)

        # Get reminders due in next 5 minutes
        now = datetime.utcnow()
        soon = now + timedelta(minutes=5)

        due_reminders = await service.get_due_reminders(
            start_time=now,
            end_time=soon,
        )

        for reminder in due_reminders:
            # Send notification
            notification_service = NotificationService()
            await notification_service.send_notification(
                user_id=reminder["user_id"],
                title=f"⏰ Reminder: {reminder['title']}",
                body=reminder.get("body", ""),
                type="reminder",
                priority="high",
                action_url=f"/reminders/{reminder['id']}",
            )

            # Mark as fired
            await service.mark_reminder_fired(reminder["id"])

            logger.info(
                "reminder_fired",
                reminder_id=str(reminder["id"]),
                user_id=str(reminder["user_id"]),
            )


# ============ WEEKLY SUMMARY AGENT ============

@celery_app.task(name="agents.weekly_summary")
def weekly_summary_agent(user_id: str):
    """
    Weekly summary agent - Runs Sunday at 6:00 PM.

    Provides:
    - Week's accomplishments
    - Productivity metrics
    - Insights and patterns
    - Goals for next week
    """
    asyncio.run(_run_weekly_summary(UUID(user_id)))


async def _run_weekly_summary(user_id: UUID):
    """Generate weekly summary."""
    logger.info("weekly_summary_start", user_id=str(user_id))

    orchestrator = ToolOrchestrationService(user_id)

    summary_prompt = """
    Generate a comprehensive weekly summary. Use the analyze_productivity tool
    for insights. Include:

    1. Tasks completed this week (celebrate progress!)
    2. Key achievements and wins
    3. Productivity patterns (most productive days/times)
    4. Areas for improvement
    5. Suggested goals for next week

    Make it insightful and motivating.
    """

    result = await orchestrator.execute_user_request(summary_prompt)

    # Send notification
    notification_service = NotificationService()
    await notification_service.send_notification(
        user_id=user_id,
        title="📊 Your Week in Review",
        body=result["response"],
        type="weekly_summary",
        priority="normal",
    )

    logger.info("weekly_summary_complete", user_id=str(user_id))


# ============ SMART SUGGESTIONS AGENT ============

@celery_app.task(name="agents.smart_suggestions")
def smart_suggestions_agent(user_id: str):
    """
    Smart suggestions agent - Runs when triggered by user activity.

    Analyzes user's notes and suggests:
    - Actionable tasks extracted from notes
    - Related notes to link
    - Knowledge gaps to fill
    """
    asyncio.run(_generate_smart_suggestions(UUID(user_id)))


async def _generate_smart_suggestions(user_id: UUID):
    """Generate smart suggestions from user activity."""
    logger.info("smart_suggestions_start", user_id=str(user_id))

    orchestrator = ToolOrchestrationService(user_id)

    suggestions_prompt = """
    Analyze the user's recent notes and suggest:
    1. Actionable tasks that should be created
    2. Notes that could be linked together
    3. Knowledge gaps or topics to explore

    Use the suggest_tasks_from_notes tool and knowledge base search.
    """

    result = await orchestrator.execute_user_request(suggestions_prompt)

    # Send notification if there are actionable suggestions
    if result.get("tool_calls"):
        notification_service = NotificationService()
        await notification_service.send_notification(
            user_id=user_id,
            title="💡 Smart Suggestions",
            body=result["response"],
            type="suggestions",
            priority="low",
        )

    logger.info("smart_suggestions_complete", user_id=str(user_id))


# ============ PROACTIVE TASK SUGGESTER ============

@celery_app.task(name="agents.task_suggester")
def proactive_task_suggester_agent(user_id: str, context: str):
    """
    Proactive task suggester - Triggered when user creates a note.

    Automatically suggests tasks based on note content.
    """
    asyncio.run(_suggest_tasks_from_context(UUID(user_id), context))


async def _suggest_tasks_from_context(user_id: UUID, context: str):
    """Suggest tasks from note context."""
    orchestrator = ToolOrchestrationService(user_id)

    prompt = f"""
    Analyze this note and suggest actionable tasks:

    {context}

    For each task you identify:
    1. Use create_task tool to create it
    2. Set appropriate priority and due date
    3. Link it to the source note

    Only create tasks for clear, actionable items.
    """

    result = await orchestrator.execute_user_request(prompt)

    # Log suggestions
    logger.info(
        "tasks_suggested_from_note",
        user_id=str(user_id),
        tasks_created=len([t for t in result.get("tool_calls", []) if t["tool"] == "create_task"]),
    )
```

---

### File: `app/worker/scheduler.py`

Update to register agent schedules:

```python
"""APScheduler configuration for periodic agents."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
import os

# ... existing scheduler code ...

def register_agent_schedules(scheduler: AsyncIOScheduler):
    """Register all autonomous agent schedules."""

    # Get all users (or make per-user schedules configurable)
    users = get_all_active_users()

    for user in users:
        user_id = str(user["id"])

        # Morning briefing - 7:00 AM daily
        scheduler.add_job(
            func="worker.agents.morning_briefing_agent",
            trigger="cron",
            hour=7,
            minute=0,
            args=[user_id],
            id=f"morning_briefing_{user_id}",
            replace_existing=True,
        )

        # Evening review - 8:00 PM daily
        scheduler.add_job(
            func="worker.agents.evening_review_agent",
            trigger="cron",
            hour=20,
            minute=0,
            args=[user_id],
            id=f"evening_review_{user_id}",
            replace_existing=True,
        )

        # Weekly summary - Sunday 6:00 PM
        scheduler.add_job(
            func="worker.agents.weekly_summary_agent",
            trigger="cron",
            day_of_week="sun",
            hour=18,
            minute=0,
            args=[user_id],
            id=f"weekly_summary_{user_id}",
            replace_existing=True,
        )

    # Reminder watcher - Every minute (all users)
    scheduler.add_job(
        func="worker.agents.reminder_watcher_agent",
        trigger="cron",
        minute="*",
        id="reminder_watcher",
        replace_existing=True,
    )
```

---

## Phase 4: Notification System (3-4 hours)

### File: `app/api/services/notification_service.py` (NEW)

```python
"""Notification service for proactive agent communication."""
from typing import Optional
from uuid import UUID
from datetime import datetime

import structlog

logger = structlog.get_logger()


class NotificationService:
    """Send notifications to users via various channels."""

    async def send_notification(
        self,
        user_id: UUID,
        title: str,
        body: str,
        type: str,
        priority: str = "normal",
        action_url: Optional[str] = None,
    ):
        """
        Send notification to user.

        Channels:
        1. In-app notifications (stored in DB, shown in UI)
        2. Web push notifications (if enabled)
        3. Email (for high-priority items)
        4. SMS (for urgent reminders, if configured)
        """

        # Store in database
        async with get_db_connection() as db:
            notification = await db.fetchrow(
                """
                INSERT INTO notifications (
                    user_id, title, body, type, priority, action_url
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, created_at
                """,
                user_id,
                title,
                body,
                type,
                priority,
                action_url,
            )

        # Send web push (if user has enabled)
        await self._send_web_push(user_id, title, body)

        # Send email for high-priority
        if priority == "high":
            await self._send_email(user_id, title, body)

        logger.info(
            "notification_sent",
            user_id=str(user_id),
            type=type,
            priority=priority,
        )

    async def _send_web_push(self, user_id: UUID, title: str, body: str):
        """Send web push notification."""
        # TODO: Implement using web-push library
        pass

    async def _send_email(self, user_id: UUID, title: str, body: str):
        """Send email notification."""
        # TODO: Implement using SMTP or SendGrid
        pass
```

### Migration: `migrations/023_add_notifications.sql`

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,  -- morning_briefing, evening_review, reminder, etc.
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',  -- low, normal, high, urgent

    action_url TEXT,

    read_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX idx_notifications_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;
```

---

## Phase 5: Frontend Integration (4-5 hours)

### Update: `app/web/src/components/chat/MessageList.tsx`

Display tool calls in chat messages:

```typescript
{message.tool_calls && message.tool_calls.length > 0 && (
  <div className={styles.toolCalls}>
    <div className={styles.toolCallsHeader}>
      🔧 Actions taken:
    </div>
    {message.tool_calls.map((call, idx) => (
      <div key={idx} className={styles.toolCall}>
        <div className={styles.toolCallIcon}>
          {getToolIcon(call.tool)}
        </div>
        <div className={styles.toolCallDetails}>
          <div className={styles.toolCallName}>
            {formatToolName(call.tool)}
          </div>
          <div className={styles.toolCallResult}>
            {call.success ? (
              <span className={styles.success}>✓ Completed</span>
            ) : (
              <span className={styles.error}>✗ Failed</span>
            )}
          </div>
          {call.data && (
            <div className={styles.toolCallData}>
              {formatToolData(call.tool, call.data)}
            </div>
          )}
        </div>
      </div>
    ))}
  </div>
)}
```

### Create: `app/web/src/components/layout/NotificationCenter.tsx` (NEW)

```typescript
import { useState, useEffect } from 'react';
import { Bell, X } from 'lucide-react';
import './NotificationCenter.css';

export function NotificationCenter() {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    fetchNotifications();

    // Poll for new notifications every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchNotifications = async () => {
    const response = await fetch('/api/v1/notifications?limit=20', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
    });

    const data = await response.json();
    setNotifications(data.notifications);
    setUnreadCount(data.notifications.filter(n => !n.read_at).length);
  };

  const markAsRead = async (notificationId: string) => {
    await fetch(`/api/v1/notifications/${notificationId}/read`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
    });

    fetchNotifications();
  };

  return (
    <div className="notification-center">
      <button
        className="notification-bell"
        onClick={() => setIsOpen(!isOpen)}
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="notification-badge">{unreadCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-header">
            <h3>Notifications</h3>
            <button onClick={() => setIsOpen(false)}>
              <X size={16} />
            </button>
          </div>

          <div className="notification-list">
            {notifications.map((notif) => (
              <div
                key={notif.id}
                className={`notification-item ${notif.read_at ? 'read' : 'unread'}`}
                onClick={() => markAsRead(notif.id)}
              >
                <div className="notification-icon">
                  {getNotificationIcon(notif.type)}
                </div>
                <div className="notification-content">
                  <div className="notification-title">{notif.title}</div>
                  <div className="notification-body">{notif.body}</div>
                  <div className="notification-time">
                    {formatRelativeTime(notif.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## Example User Interactions

### Example 1: Create Task from Chat

**User**: "Remind me to review the quarterly report tomorrow at 2pm and create a task to prepare slides by Friday"

**LLM Orchestration**:
1. Calls `create_reminder(title="Review quarterly report", due_at="tomorrow at 2pm")`
2. Calls `create_task(title="Prepare slides", due_date="Friday", priority="high")`

**Response**: "Done! I've set a reminder for tomorrow at 2:00 PM to review the quarterly report, and created a high-priority task to prepare slides by Friday."

**Tool Trace Shown**:
- ✓ create_reminder → Due tomorrow at 2:00 PM
- ✓ create_task → Task #1234 created, due Friday

---

### Example 2: Morning Briefing (Autonomous)

**7:00 AM - Scheduled Agent Runs**:

Agent executes:
1. `list_events(start_date="today", end_date="today")`
2. `list_tasks(status="active", due_soon=true)`
3. `list_reminders(status="pending")`

**Notification Sent**:
```
☀️ Good morning! Here's your briefing

📅 Today's Schedule:
• 10:00 AM - Team standup (30 min)
• 2:00 PM - Client presentation (1 hour)

✅ High-Priority Tasks:
• Prepare client presentation slides (due today)
• Review PR #42 (due today)

⏰ Reminders:
• Call dentist to reschedule appointment

Have a productive day! 🚀
```

---

### Example 3: Proactive Task Suggestion

**User creates note**: "Meeting with Sarah: She suggested we explore the new React 19 features. Also mentioned the API refactoring should be prioritized."

**Proactive Agent Triggers**:
1. Analyzes note content
2. Calls `create_task(title="Research React 19 features", priority="medium")`
3. Calls `create_task(title="Prioritize API refactoring", priority="high")`

**Notification**: "💡 I noticed some action items in your meeting notes and created 2 tasks. Check them out!"

---

## Testing Checklist

- [ ] User says "create a task" → Task created via tool
- [ ] User says "what's on my schedule today" → Calendar queried
- [ ] User uploads image → OCR tool extracts text automatically
- [ ] User asks complex question → Multiple tools used in sequence
- [ ] Morning briefing runs at 7 AM → Notification received
- [ ] Evening review runs at 8 PM → Day summarized
- [ ] Reminder fires → Notification sent immediately
- [ ] Weekly summary on Sunday → Insights delivered
- [ ] Tool call fails → Error handled gracefully, alternative suggested
- [ ] Tool call shown in UI → User sees transparency

---

## Performance & Scalability

### Tool Execution Caching
```python
# Cache tool results for 5 minutes to avoid redundant queries
@lru_cache(maxsize=1000, ttl=300)
async def cached_tool_execution(tool_name, arguments_hash, user_id):
    return await tool_registry.execute(tool_name, arguments, user_id)
```

### Parallel Tool Execution
```python
# Execute independent tools in parallel
if multiple_tools_needed:
    results = await asyncio.gather(*[
        tool_registry.execute(tool["name"], tool["args"], user_id)
        for tool in tools
    ])
```

### Agent Throttling
```python
# Prevent agent spam
@celery_app.task(rate_limit="10/m")  # Max 10 per minute per user
def morning_briefing_agent(user_id: str):
    ...
```

---

## Security Considerations

1. **User isolation**: ALL tool calls filter by user_id
2. **Rate limiting**: Max 100 tool calls per user per hour
3. **Tool permissions**: Validate user has access to referenced entities
4. **Input validation**: Sanitize all tool arguments
5. **Audit logging**: Log all tool executions for debugging

---

## Estimated Total Time: 25-30 hours

- Phase 1 (Tool registry): 4-5 hours
- Phase 2 (Orchestration): 6-8 hours
- Phase 3 (Agents): 8-10 hours
- Phase 4 (Notifications): 3-4 hours
- Phase 5 (Frontend): 4-5 hours
- Testing & refinement: 4-6 hours
