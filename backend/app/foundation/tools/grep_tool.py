"""Grep tool — fast content search inside files.

Inspired by Claude Code's GrepTool: searches file contents using regex
and returns matching lines (with optional context).
"""

import asyncio
import os
import re
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
from app.foundation.tools.glob_tool import EXCLUDE_DIRS

logger = get_logger(__name__)


class GrepInput(ToolInput):
    """Input for GrepTool."""

    pattern: str = Field(..., description="Regular expression pattern to search for.")
    path: str | None = Field(
        None,
        description="File or directory to search in. Defaults to cwd.",
    )
    glob: str | None = Field(
        None,
        description="Optional glob filter, e.g. '*.py' to only search Python files.",
    )
    case_insensitive: bool = Field(False, description="Case-insensitive match.")
    context_before: int = Field(0, description="Lines of context before each match.", ge=0, le=20)
    context_after: int = Field(0, description="Lines of context after each match.", ge=0, le=20)
    max_matches: int = Field(50, description="Maximum number of matches to return.", ge=1, le=500)


class GrepTool(Tool[GrepInput]):
    """Search file contents with regex."""

    name = "grep"
    description = (
        "Search file contents using a regular expression. Returns matching lines "
        "with file path and line number. Supports optional context lines and glob filters. "
        "Excludes common junk directories (.venv, node_modules, .git, __pycache__)."
    )
    input_schema = GrepInput
    aliases = ["search"]

    def __init__(self, allowed_root: str | None = None):
        self.allowed_root = Path(allowed_root or os.getcwd()).resolve()

    def _resolve_target(self, path: str | None) -> Path:
        if path:
            p = Path(path)
            if not p.is_absolute():
                p = self.allowed_root / p
            return p.resolve()
        return self.allowed_root

    def is_readonly(self, input_data: GrepInput) -> bool:
        return True

    def check_permissions(
        self, input_data: GrepInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    def _matches_glob(self, path: Path, glob_pattern: str | None) -> bool:
        if not glob_pattern:
            return True
        # Use Path.match for simple patterns; for '**' patterns, fall back to fnmatch on name
        try:
            if "*" in glob_pattern or "?" in glob_pattern:
                import fnmatch

                return fnmatch.fnmatch(path.name, glob_pattern)
            return path.name == glob_pattern
        except Exception:
            return True

    def _search_file(
        self,
        file_path: Path,
        regex: re.Pattern[str],
        input_data: GrepInput,
    ) -> list[str]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        lines = text.splitlines()
        results: list[str] = []
        for i, line in enumerate(lines):
            if regex.search(line):
                start = max(0, i - input_data.context_before)
                end = min(len(lines), i + 1 + input_data.context_after)
                for j in range(start, end):
                    marker = ">" if j == i else " "
                    results.append(f"{file_path}:{j + 1}:{marker} {lines[j]}")
                results.append("")  # blank line between matches
                if len(results) >= input_data.max_matches * 2:
                    break
        return results

    async def call(self, input_data: GrepInput, context: dict[str, Any]) -> ToolResult:
        try:
            target = self._resolve_target(input_data.path)
            if not target.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {target}",
                )

            flags = re.IGNORECASE if input_data.case_insensitive else 0
            try:
                regex = re.compile(input_data.pattern, flags)
            except re.error as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid regex pattern: {e}",
                )

            # Collect files to search
            files: list[Path] = []
            if target.is_file():
                files.append(target)
            else:
                for p in target.rglob("*"):
                    if not p.is_file():
                        continue
                    if any(part in EXCLUDE_DIRS for part in p.parts):
                        continue
                    if not self._matches_glob(p, input_data.glob):
                        continue
                    files.append(p)

            # Run the search in a thread to avoid blocking the event loop
            def _run() -> list[str]:
                all_results: list[str] = []
                for fp in files:
                    if len(all_results) >= input_data.max_matches * 2:
                        break
                    all_results.extend(self._search_file(fp, regex, input_data))
                return all_results

            results = await asyncio.to_thread(_run)

            if not results:
                return ToolResult(
                    success=True,
                    output="(no matches found)",
                    metadata={
                        "files_searched": len(files),
                        "match_count": 0,
                    },
                )

            output = "\n".join(results)
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "files_searched": len(files),
                    "match_count": len(results),
                },
            )

        except Exception as e:
            logger.error("grep_error", error=str(e), pattern=input_data.pattern)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to grep: {e}",
            )
