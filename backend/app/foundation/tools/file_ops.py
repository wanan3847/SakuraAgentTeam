"""File read tool implementation."""

import os
from pathlib import Path
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


class FileReadInput(ToolInput):
    """Input for FileReadTool."""

    file_path: str = Field(..., description="Path to the file to read")
    start_line: int | None = Field(None, description="Start line number (1-indexed)")
    end_line: int | None = Field(None, description="End line number (1-indexed)")
    encoding: str = Field("utf-8", description="File encoding")


class FileReadTool(Tool[FileReadInput]):
    """Tool for reading file contents.

    Supports reading entire files or specific line ranges.
    Implements path validation to prevent directory traversal attacks.
    """

    name = "file_read"
    description = "Read the contents of a file"
    input_schema = FileReadInput
    aliases = ["read", "cat"]

    def __init__(self, allowed_root: str | None = None):
        """Initialize the file read tool.

        Args:
            allowed_root: Root directory that files must be within.
                         If None, uses current working directory.
        """
        self.allowed_root = Path(allowed_root or os.getcwd()).resolve()

    def _validate_path(self, file_path: str) -> Path:
        """Validate that the path is within allowed root.

        Args:
            file_path: Path to validate

        Returns:
            Resolved path

        Raises:
            ValueError: If path is outside allowed root
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.allowed_root / path

        path = path.resolve()

        if not str(path).startswith(str(self.allowed_root)):
            raise ValueError(
                f"Path '{file_path}' is outside allowed directory '{self.allowed_root}'"
            )

        return path

    def check_permissions(
        self, input_data: FileReadInput, context: dict[str, Any]
    ) -> PermissionResult:
        """Check if the file can be read.

        Args:
            input_data: Tool input
            context: Execution context

        Returns:
            Permission result
        """
        try:
            path = self._validate_path(input_data.file_path)
            if not path.exists():
                return PermissionResult.DENY
            if not path.is_file():
                return PermissionResult.DENY
            return PermissionResult.ALLOW
        except ValueError:
            return PermissionResult.DENY

    def is_readonly(self, input_data: FileReadInput) -> bool:
        """File read is always read-only."""
        return True

    async def call(self, input_data: FileReadInput, context: dict[str, Any]) -> ToolResult:
        """Read file contents.

        Args:
            input_data: Tool input
            context: Execution context

        Returns:
            Tool result with file contents
        """
        try:
            path = self._validate_path(input_data.file_path)

            if not path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {input_data.file_path}",
                )

            if not path.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Not a file: {input_data.file_path}",
                )

            with open(path, encoding=input_data.encoding) as f:
                if input_data.start_line is not None:
                    # Read specific line range
                    lines = f.readlines()
                    start = max(0, input_data.start_line - 1)
                    end = input_data.end_line or len(lines)
                    content = "".join(lines[start:end])
                else:
                    # Read entire file
                    content = f.read()

            logger.info(
                "file_read_success",
                file_path=str(path),
                start_line=input_data.start_line,
                end_line=input_data.end_line,
            )

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "file_path": str(path),
                    "size": len(content),
                    "lines": content.count("\n") + 1,
                },
            )

        except UnicodeDecodeError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to decode file with encoding {input_data.encoding}: {e}",
            )
        except Exception as e:
            logger.error("file_read_error", error=str(e), file_path=input_data.file_path)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to read file: {e}",
            )
