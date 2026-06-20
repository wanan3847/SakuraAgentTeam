"""Tool abstraction layer.

This module provides a unified interface for all tools that agents can use.
Inspired by Claude Code's Tool.ts and OpenHands Tool abstraction.
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
    """Result of tool execution."""

    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolInput(BaseModel):
    """Base class for tool inputs."""

    pass


InputType = TypeVar("InputType", bound=ToolInput)


class Tool(ABC, Generic[InputType]):
    """Abstract base class for all tools.

    This class defines the unified interface that all tools must implement.
    Inspired by Claude Code's Tool abstraction with:
    - call: Execute the tool
    - check_permissions: Verify permissions before execution
    - description: Human-readable description
    - input_schema: JSON schema for input validation
    """

    name: str
    description: str
    input_schema: type[ToolInput]
    aliases: list[str] = field(default_factory=list)

    @abstractmethod
    async def call(self, input_data: InputType, context: dict[str, Any]) -> ToolResult:
        """Execute the tool.

        Args:
            input_data: Validated input for the tool
            context: Execution context (session info, project path, etc.)

        Returns:
            Tool execution result
        """
        ...

    def check_permissions(self, input_data: InputType, context: dict[str, Any]) -> PermissionResult:
        """Check if the tool can be executed.

        Override this method to implement permission checks.

        Args:
            input_data: Tool input
            context: Execution context

        Returns:
            Permission check result
        """
        return PermissionResult.ALLOW

    def is_readonly(self, input_data: InputType) -> bool:
        """Check if this tool operation is read-only.

        Args:
            input_data: Tool input

        Returns:
            True if the operation is read-only
        """
        return False

    def is_destructive(self, input_data: InputType) -> bool:
        """Check if this tool operation is destructive.

        Args:
            input_data: Tool input

        Returns:
            True if the operation is destructive (deletes data)
        """
        return False

    def validate_input(self, input_dict: dict[str, Any]) -> InputType:
        """Validate and parse input.

        Args:
            input_dict: Raw input dictionary

        Returns:
            Validated input object

        Raises:
            ValidationError: If input is invalid
        """
        return self.input_schema(**input_dict)


class ToolRegistry:
    """Registry for all available tools.

    Provides tool discovery, lookup, and permission management.
    """

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool
        for alias in tool.aliases:
            self._tools[alias] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name or alias.

        Args:
            name: Tool name or alias

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all_tools(self) -> list[Tool]:
        """Get all registered tool instances."""
        return list(set(self._tools.values()))


# Global tool registry
tool_registry = ToolRegistry()
