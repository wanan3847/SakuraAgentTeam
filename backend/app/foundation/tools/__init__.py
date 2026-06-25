"""Tools module.

This module provides all available tools for agents.

Available tools:
- file_read: Read file contents (read-only)
- file_write: Write/create files
- file_edit: Surgical string replacement in a file
- shell_run: Execute shell commands (sandboxed)
- glob: Find files by glob pattern (read-only)
- grep: Search file contents with regex (read-only)
- sub_agent: Dispatch a sub-agent for a focused subtask (read-only)
- skill_invoke: Invoke a registered skill by name (read-only)
- list_skills: List all available skills (read-only)
"""

from app.foundation.tools.base import (
    PermissionResult,
    Tool,
    ToolInput,
    ToolRegistry,
    ToolResult,
    tool_registry,
)
from app.foundation.tools.file_edit import FileEditInput, FileEditTool
from app.foundation.tools.file_ops import FileReadInput, FileReadTool
from app.foundation.tools.glob_tool import GlobInput, GlobTool
from app.foundation.tools.grep_tool import GrepInput, GrepTool
from app.foundation.tools.shell import FileWriteInput, FileWriteTool
from app.foundation.tools.shell_run import ShellRunInput, ShellRunTool
from app.foundation.tools.skill_tool import (
    ListSkillsInput,
    ListSkillsTool,
    SkillInvokeInput,
    SkillTool,
)
from app.foundation.tools.sub_agent import SubAgentInput, SubAgentTool

# Register default tools (idempotent — re-import won't double-register
# because register() overwrites by name)
tool_registry.register(FileReadTool())
tool_registry.register(FileWriteTool())
tool_registry.register(FileEditTool())
tool_registry.register(ShellRunTool())
tool_registry.register(GlobTool())
tool_registry.register(GrepTool())
tool_registry.register(SubAgentTool())
tool_registry.register(SkillTool())
tool_registry.register(ListSkillsTool())

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
    "FileEditTool",
    "FileEditInput",
    "ShellRunTool",
    "ShellRunInput",
    "GlobTool",
    "GlobInput",
    "GrepTool",
    "GrepInput",
    "SubAgentTool",
    "SubAgentInput",
    "SkillTool",
    "SkillInvokeInput",
    "ListSkillsTool",
    "ListSkillsInput",
]
