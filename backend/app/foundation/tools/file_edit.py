"""File edit tool — surgical string replacement in a file.

Inspired by Claude Code's FileEditTool: replace a unique old_string with
new_string. Refuses to edit if old_string is not unique, forcing the LLM
to provide enough context to disambiguate.
"""

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


class FileEditInput(ToolInput):
    """Input for FileEditTool."""

    file_path: str = Field(..., description="Path to the file to edit")
    old_string: str = Field(
        ...,
        description="The exact string to replace. Must be unique in the file.",
    )
    new_string: str = Field(..., description="The replacement string")
    replace_all: bool = Field(
        False,
        description="If true, replace all occurrences of old_string (dangerous).",
    )


class FileEditTool(Tool[FileEditInput]):
    """Edit a file by replacing old_string with new_string.

    The old_string must be unique in the file unless replace_all is True.
    This mirrors Claude Code's FileEditTool semantics, which forces the
    model to include enough surrounding context to disambiguate the edit.
    """

    name = "file_edit"
    description = (
        "Edit a file by replacing a unique old_string with new_string. "
        "The old_string must appear exactly once in the file unless replace_all=true."
    )
    input_schema = FileEditInput
    aliases = ["edit"]

    def __init__(self, allowed_root: str | None = None):
        self.allowed_root = Path(allowed_root or os.getcwd()).resolve()

    def _validate_path(self, file_path: str) -> Path:
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
        self, input_data: FileEditInput, context: dict[str, Any]
    ) -> PermissionResult:
        try:
            self._validate_path(input_data.file_path)
            return PermissionResult.ALLOW
        except ValueError:
            return PermissionResult.DENY

    def is_readonly(self, input_data: FileEditInput) -> bool:
        return False

    async def call(self, input_data: FileEditInput, context: dict[str, Any]) -> ToolResult:
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

            original = path.read_text(encoding="utf-8")

            if input_data.old_string == input_data.new_string:
                return ToolResult(
                    success=False,
                    output="",
                    error="old_string and new_string are identical; nothing to do.",
                )

            occurrences = original.count(input_data.old_string)
            if occurrences == 0:
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        "old_string not found in file. Make sure the string matches "
                        "exactly (including whitespace and indentation)."
                    ),
                )

            if occurrences > 1 and not input_data.replace_all:
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        f"old_string appears {occurrences} times in the file. "
                        "Provide more surrounding context to make it unique, "
                        "or set replace_all=true."
                    ),
                )

            if input_data.replace_all:
                new_content = original.replace(input_data.old_string, input_data.new_string)
                replaced = occurrences
            else:
                new_content = original.replace(input_data.old_string, input_data.new_string, 1)
                replaced = 1

            path.write_text(new_content, encoding="utf-8")

            logger.info(
                "file_edit_success",
                file_path=str(path),
                replacements=replaced,
            )

            # Show a small diff-like preview for the LLM
            preview_old = input_data.old_string[:200]
            preview_new = input_data.new_string[:200]
            return ToolResult(
                success=True,
                output=(
                    f"Edited {input_data.file_path}: replaced {replaced} occurrence(s).\n"
                    f"--- old (first 200 chars)\n{preview_old}\n"
                    f"+++ new (first 200 chars)\n{preview_new}\n"
                ),
                metadata={
                    "file_path": str(path),
                    "replacements": replaced,
                },
            )

        except Exception as e:
            logger.error("file_edit_error", error=str(e), file_path=input_data.file_path)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to edit file: {e}",
            )
