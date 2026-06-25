"""Sub-agent tool — lets the LLM dispatch a sub-agent for a subtask.

Inspired by Claude Code's AgentTool: the main agent can delegate a focused
subtask to a fresh sub-agent with its own agentic loop. This is useful for:
- Exploring a large codebase before making changes
- Researching an approach before committing to it
- Breaking a complex task into smaller, isolated steps

The sub-agent runs its own agentic loop with a clean context, so it won't
pollute the main agent's conversation history.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.logging import get_logger
from app.foundation.tools.base import (
    PermissionResult,
    Tool,
    ToolInput,
    ToolResult,
)

logger = get_logger(__name__)


class SubAgentInput(ToolInput):
    """Input for SubAgentTool."""

    task: str = Field(
        ...,
        description=(
            "A focused, self-contained subtask for the sub-agent. "
            "Example: 'Find all files that import fastapi and list their paths.'"
        ),
    )
    max_iterations: int = Field(
        8,
        description="Max LLM round-trips for the sub-agent.",
        ge=1,
        le=20,
    )


class SubAgentTool(Tool[SubAgentInput]):
    """Dispatch a sub-agent to handle a focused subtask.

    The sub-agent runs its own agentic loop with a clean conversation context.
    Only the final text answer is returned to the calling agent.

    This mirrors Claude Code's AgentTool pattern, where the main agent can
    spawn a sub-agent for exploration or research without cluttering its own
    context window.
    """

    name = "sub_agent"
    description = (
        "Dispatch a sub-agent to handle a focused subtask (e.g. 'explore the codebase "
        "and find all API endpoints'). The sub-agent runs its own agentic loop with "
        "file_read/glob/grep tools and returns a text summary. Use this for research "
        "or exploration tasks that would otherwise clutter the main conversation."
    )
    input_schema = SubAgentInput
    aliases = ["agent", "delegate"]

    def is_readonly(self, input_data: SubAgentInput) -> bool:
        # Sub-agent could do anything, but we only give it read-only tools by default
        return True

    def check_permissions(
        self, input_data: SubAgentInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: SubAgentInput, context: dict[str, Any]) -> ToolResult:
        """Run the sub-agent loop.

        The sub-agent gets read-only tools (file_read, glob, grep) by default,
        so it can explore but not modify. The calling agent's context is passed
        through so the sub-agent knows the session_id and project paths.
        """
        try:
            # Lazy imports to avoid circular deps
            from app.agents.base import Agent
            from app.agents.types import AgentRole, Context
            from app.foundation.tools import tool_registry

            # Find the calling agent from the context
            agent_role = context.get("agent_role", "requirements")
            try:
                role_enum = AgentRole(agent_role)
            except ValueError:
                role_enum = AgentRole.REQUIREMENTS

            from app.agents import get_agent

            # Reuse the same agent class but with a fresh context
            sub_agent = get_agent(role_enum, llm_provider=_get_global_llm_provider())
            if sub_agent.llm is None:
                return ToolResult(
                    success=False,
                    output="",
                    error="No LLM provider available for sub-agent.",
                )

            # Build a minimal context for the sub-agent
            sub_ctx = Context(
                session_id=context.get("session_id", "sub-agent"),
                project_id=context.get("project_id", "sub-agent-project"),
                user_requirement=input_data.task,
            )

            # Give the sub-agent only read-only tools
            all_tools = tool_registry.get_all_tools()
            readonly_tools = [t for t in all_tools if t.is_readonly(t.input_schema())]

            system_prompt = (
                "You are a focused sub-agent. Complete the given task using the "
                "available read-only tools (file_read, glob, grep). "
                "Be concise and return only the relevant findings."
            )

            logger.info(
                "sub_agent_start",
                parent_role=agent_role,
                task=input_data.task[:200],
                max_iterations=input_data.max_iterations,
            )

            result_text = await sub_agent.run_agentic_loop(
                prompt=input_data.task,
                ctx=sub_ctx,
                system_prompt=system_prompt,
                tools=readonly_tools,
                max_iterations=input_data.max_iterations,
            )

            logger.info(
                "sub_agent_complete",
                parent_role=agent_role,
                result_len=len(result_text),
            )

            return ToolResult(
                success=True,
                output=result_text,
                metadata={
                    "parent_role": agent_role,
                    "task": input_data.task,
                    "result_length": len(result_text),
                },
            )

        except Exception as e:
            logger.error("sub_agent_error", error=str(e), task=input_data.task[:200])
            return ToolResult(
                success=False,
                output="",
                error=f"Sub-agent failed: {e}",
            )


def _get_global_llm_provider():
    """Get the global metered LLM provider, if any."""
    try:
        from app.foundation.llm.meter import get_global_provider

        return get_global_provider()
    except Exception:
        return None
