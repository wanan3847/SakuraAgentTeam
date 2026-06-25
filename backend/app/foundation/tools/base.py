"""Tool abstraction layer.

This module provides a unified interface for all tools that agents can use.
Inspired by Claude Code's Tool.ts and Hermes tool_executor.

Key design:
- Each Tool has a pydantic input_schema that doubles as the JSON schema
  sent to the LLM for function calling.
- ToolResult carries the textual output fed back to the LLM plus metadata.
- ToolRegistry is the single source of truth for available tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


class PermissionResult(StrEnum):
    """Result of permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class ToolResult:
    """Result of tool execution.

    Attributes:
        success: Whether the tool call succeeded.
        output: Textual output fed back to the LLM (may be truncated).
        error: Optional error message (set when success=False).
        metadata: Extra metadata for logging/UI (not sent to LLM).
    """

    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_llm_content(self) -> str:
        """Render the result as the content of a tool message for the LLM."""
        if self.success:
            return self.output
        return f"[ERROR] {self.error or 'unknown error'}\n{self.output}"


class ToolInput(BaseModel):
    """Base class for tool inputs."""

    pass


InputType = TypeVar("InputType", bound=ToolInput)


class Tool(ABC, Generic[InputType]):
    """Abstract base class for all tools.

    Inspired by Claude Code's Tool abstraction with:
    - call: Execute the tool
    - check_permissions: Verify permissions before execution
    - description: Human-readable description
    - input_schema: Pydantic model whose JSON schema is sent to the LLM
    """

    name: str
    description: str
    input_schema: type[ToolInput]
    aliases: list[str] = field(default_factory=list)

    @abstractmethod
    async def call(self, input_data: InputType, context: dict[str, Any]) -> ToolResult:
        """Execute the tool."""
        ...

    def check_permissions(self, input_data: InputType, context: dict[str, Any]) -> PermissionResult:
        """Check if the tool can be executed. Override for custom logic."""
        return PermissionResult.ALLOW

    def is_readonly(self, input_data: InputType) -> bool:
        """Return True if this operation is read-only."""
        return False

    def is_destructive(self, input_data: InputType) -> bool:
        """Return True if this operation deletes data."""
        return False

    def validate_input(self, input_dict: dict[str, Any]) -> InputType:
        """Validate and parse input."""
        return self.input_schema(**input_dict)

    def to_function_schema(self) -> dict[str, Any]:
        """Render the tool as an OpenAI-style function-calling schema.

        Example:
            {
              "type": "function",
              "function": {
                "name": "file_read",
                "description": "Read the contents of a file",
                "parameters": { ...JSON schema... }
              }
            }
        """
        schema = self.input_schema.model_json_schema()
        # OpenAI expects JSON-schema draft-07; pydantic already produces that.
        # Strip pydantic-specific "title" to keep the schema compact.
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


class ToolRegistry:
    """Registry for all available tools.

    Provides tool discovery, lookup, and schema export for LLM function calling.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by name and all its aliases."""
        self._tools[tool.name] = tool
        for alias in tool.aliases:
            self._tools[alias] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name or alias."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names (including aliases)."""
        return list(self._tools.keys())

    def get_all_tools(self) -> list[Tool]:
        """Get all unique tool instances (deduped)."""
        seen: set[int] = set()
        result: list[Tool] = []
        for tool in self._tools.values():
            if id(tool) not in seen:
                seen.add(id(tool))
                result.append(tool)
        return result

    def to_function_schemas(self) -> list[dict[str, Any]]:
        """Export all tools as OpenAI function-calling schemas."""
        return [tool.to_function_schema() for tool in self.get_all_tools()]


# Global tool registry
tool_registry = ToolRegistry()
