"""Tool orchestration service - Intelligently select and execute tool chains."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from api.tools.registry import get_tool_registry
from api.adapters.llm_adapter import get_llm_adapter, BaseLLMAdapter
from api.metrics import tool_calls_total

logger = structlog.get_logger()


class ToolOrchestrationService:
    """Orchestrate complex multi-tool workflows with LLM intelligence."""

    def __init__(self, user_id: UUID, db, llm_adapter: BaseLLMAdapter | None = None):
        self.user_id = user_id
        self.db = db
        self.llm_adapter = llm_adapter or get_llm_adapter()
        self.tool_registry = get_tool_registry()
        self.conversation_history: list[dict[str, Any]] = []

    async def execute_user_request(
        self,
        user_message: str,
        context: str | None = None,
        max_iterations: int = 5,
    ) -> dict[str, Any]:
        """
        Execute user request with autonomous tool usage.

        Flow:
        1. LLM analyzes request and decides which tools to use
        2. Execute tools and collect results
        3. LLM synthesizes final response from tool results
        4. Return response + tool call trace for transparency

        Args:
            user_message: The user's request
            context: Optional additional context
            max_iterations: Maximum number of tool-calling iterations

        Returns:
            dict with:
                - response: Final text response
                - tool_calls: List of tool calls executed
                - iterations: Number of iterations used
                - truncated: Whether max iterations was reached (bool)
        """
        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Build user prompt with context
        full_prompt = user_message
        if context:
            full_prompt = f"Context:\n{context}\n\nUser request:\n{user_message}"

        # Track tool execution
        tool_call_history: list[dict] = []
        iteration = 0

        # Conversation messages for stateful tool calling
        messages: list[dict] = []

        while iteration < max_iterations:
            iteration += 1

            logger.info(
                "orchestration_iteration",
                iteration=iteration,
                user_id=str(self.user_id),
            )

            # Call LLM with tools
            try:
                response = await self.llm_adapter.complete_with_tools(
                    prompt=full_prompt if iteration == 1 else "Based on the tool results, provide a final response to the user or use additional tools if needed.",
                    tools=self.tool_registry.get_all_tools(),
                    system_prompt=system_prompt if iteration == 1 else None,
                    temperature=0.7,
                )
            except Exception as exc:
                logger.error("llm_completion_failed", error=str(exc))
                return {
                    "response": f"I encountered an error while processing your request: {str(exc)}",
                    "tool_calls": tool_call_history,
                    "iterations": iteration,
                    "error": str(exc),
                }

            # Case 1: LLM returns final text response (no more tools needed)
            if response.get("type") == "text":
                logger.info(
                    "orchestration_complete",
                    iterations=iteration,
                    tools_used=len(tool_call_history),
                )

                return {
                    "response": response.get("content", ""),
                    "tool_calls": tool_call_history,
                    "iterations": iteration,
                    "truncated": False,
                }

            # Case 2: LLM wants to use tools
            elif response.get("type") == "tool_calls":
                tool_results: list[dict] = []

                for tool_call in response.get("tool_calls", []):
                    # Handle different tool call formats from different LLM providers
                    if "name" in tool_call:
                        # Anthropic format
                        tool_name = tool_call["name"]
                        arguments = tool_call.get("arguments", {})
                    elif "function" in tool_call:
                        # OpenAI format
                        tool_name = tool_call["function"]["name"]
                        arguments = tool_call["function"]["arguments"]
                    else:
                        logger.warning("unknown_tool_call_format", tool_call=tool_call)
                        continue

                    logger.info(
                        "executing_tool",
                        tool_name=tool_name,
                        arguments=arguments,
                        user_id=str(self.user_id),
                    )

                    # Execute tool
                    result = await self.tool_registry.execute(
                        tool_name=tool_name,
                        arguments=arguments,
                        user_id=self.user_id,
                        db=self.db,
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
                        "error": result.get("error"),
                    })

                # Format tool results for LLM
                tool_results_text = self._format_tool_results(tool_results)

                # Update prompt with tool results
                full_prompt = f"""You previously executed these tools:
{tool_results_text}

Now provide a final natural language response to the user based on these results.
If you need to use more tools, you can do so, otherwise synthesize a helpful response."""

            else:
                logger.warning("unexpected_llm_response_type", response_type=response.get("type"))
                return {
                    "response": "I received an unexpected response format. Please try again.",
                    "tool_calls": tool_call_history,
                    "iterations": iteration,
                    "error": "Unexpected response type",
                }

        # Max iterations reached
        logger.warning("orchestration_max_iterations", user_id=str(self.user_id))

        return {
            "response": "I've completed several steps but need more iterations to finish. Here's what I've done so far:\n\n"
            + self._summarize_tool_calls(tool_call_history),
            "tool_calls": tool_call_history,
            "iterations": max_iterations,
            "truncated": True,
        }

    def _build_system_prompt(self) -> str:
        """Build system prompt with available tools."""
        tool_names = self.tool_registry.get_tool_names()

        return f"""You are a personal AI secretary with access to the user's complete system.

You can perform actions using the available tools. When the user makes a request:
1. Determine which tools are needed
2. Execute tools in the correct order
3. Synthesize results into a helpful response

Available tools: {', '.join(tool_names)}

Tool categories:
- Knowledge: Search notes, documents, get answers from knowledge base
- Tasks: Create, update, complete, and list tasks
- Reminders: Create, list, and snooze reminders
- Calendar: Create, update, list, and delete calendar events
- Analysis: Generate summaries and productivity insights
- Vision: Extract text from images (OCR)
- Web: Search internet and fetch web pages

Important guidelines:
- Be proactive: If user says "remind me to call John tomorrow", use create_reminder tool
- Be precise: When creating tasks/events, include all relevant details
- Be transparent: Mention which actions you took
- Be efficient: Use multiple tools when necessary
- Be smart: Learn from context and conversation history

Current time: {datetime.now().isoformat()}
Current date: {datetime.now().strftime("%Y-%m-%d %A")}
"""

    def _format_tool_results(self, tool_results: list[dict]) -> str:
        """Format tool results for LLM consumption."""
        formatted = []
        for result in tool_results:
            tool_name = result["tool"]
            success = result["result"].get("success", False)
            data = result["result"].get("data", {})
            error = result["result"].get("error", {})

            if success:
                formatted.append(f"✓ {tool_name}: {data}")
            else:
                formatted.append(f"✗ {tool_name}: {error.get('message', 'Unknown error')}")

        return "\n".join(formatted)

    def _summarize_tool_calls(self, tool_calls: list[dict]) -> str:
        """Summarize tool calls for user."""
        summary = []
        for call in tool_calls:
            tool = call["tool"]
            success = call["success"]
            status = "✓" if success else "✗"
            data = call.get("data", "No data")
            summary.append(f"{status} {tool}: {data}")

        return "\n".join(summary)
