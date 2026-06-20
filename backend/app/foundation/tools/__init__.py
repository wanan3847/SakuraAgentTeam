"""Tools module.

This module provides all available tools for agents.
"""

from app.foundation.tools.base import (
    PermissionResult,
    Tool,
    ToolInput,
    ToolRegistry,
    ToolResult,
    tool_registry,
)
from app.foundation.tools.file_ops import FileReadInput, FileReadTool
from app.foundation.tools.shell import FileWriteInput, FileWriteTool
from app.foundation.tools.shell_run import ShellRunInput, ShellRunTool

# Register default tools
tool_registry.register(FileReadTool())
tool_registry.register(FileWriteTool())
tool_registry.register(ShellRunTool())

__all__ = [
    "PermissionResult",
    "Tool",
    "ToolInput",
    "ToolRegistry",
    "ToolResult",
    "tool_registry",
    "FileReadTool",
    "FileReadInput",
    "FileWriteTool",
    "FileWriteInput",
    "ShellRunTool",
    "ShellRunInput",
]
