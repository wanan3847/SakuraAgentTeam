"""File write tool implementation."""

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


class FileWriteInput(ToolInput):
    """Input for FileWriteTool."""

    file_path: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write to the file")
    mode: str = Field("write", description="Write mode: 'write' or 'append'")
    encoding: str = Field("utf-8", description="File encoding")
    create_dirs: bool = Field(True, description="Create parent directories if needed")


class FileWriteTool(Tool[FileWriteInput]):
    """Tool for writing content to files.

    Supports creating new files, overwriting existing files, and appending.
    Implements path validation to prevent directory traversal attacks.
    """

    name = "file_write"
    description = "Write content to a file"
    input_schema = FileWriteInput
    aliases = ["write", "echo"]

    def __init__(self, allowed_root: str | None = None):
        """Initialize the file write tool.

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
        self, input_data: FileWriteInput, context: dict[str, Any]
    ) -> PermissionResult:
        """Check if the file can be written.

        Args:
            input_data: Tool input
            context: Execution context

        Returns:
            Permission result
        """
        try:
            self._validate_path(input_data.file_path)
            return PermissionResult.ALLOW
        except ValueError:
            return PermissionResult.DENY

    def is_readonly(self, input_data: FileWriteInput) -> bool:
        """File write is not read-only."""
        return False

    async def call(self, input_data: FileWriteInput, context: dict[str, Any]) -> ToolResult:
        """Write content to file.

        Args:
            input_data: Tool input
            context: Execution context

        Returns:
            Tool result
        """
        try:
            path = self._validate_path(input_data.file_path)

            # Create parent directories if needed
            if input_data.create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Determine write mode
            mode = "a" if input_data.mode == "append" else "w"

            with open(path, mode, encoding=input_data.encoding) as f:
                f.write(input_data.content)

            logger.info(
                "file_write_success",
                file_path=str(path),
                mode=input_data.mode,
                size=len(input_data.content),
            )

            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(input_data.content)} bytes to {input_data.file_path}",
                metadata={
                    "file_path": str(path),
                    "size": len(input_data.content),
                    "mode": input_data.mode,
                },
            )

        except Exception as e:
            logger.error("file_write_error", error=str(e), file_path=input_data.file_path)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to write file: {e}",
            )
