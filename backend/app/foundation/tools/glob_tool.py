"""Glob tool — fast file pattern matching.

Inspired by Claude Code's GlobTool: returns file paths matching a glob
pattern, sorted by modification time (most recent first).
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

# Directories we never want to surface in glob results.
EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    "node_modules",
    "site-packages",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}


class GlobInput(ToolInput):
    """Input for GlobTool."""

    pattern: str = Field(
        ...,
        description=(
            "Glob pattern, e.g. '**/*.py' for all Python files, "
            "'src/*.ts' for top-level TypeScript files."
        ),
    )
    path: str | None = Field(
        None,
        description="Directory to search in. Defaults to the current working directory.",
    )
    max_results: int = Field(
        100,
        description="Maximum number of file paths to return.",
        ge=1,
        le=1000,
    )


class GlobTool(Tool[GlobInput]):
    """Find files matching a glob pattern."""

    name = "glob"
    description = (
        "Fast file pattern matcher. Returns file paths matching a glob pattern "
        "(e.g. '**/*.py'). Results are sorted by modification time, most recent first. "
        "Excludes common junk directories (.venv, node_modules, .git, __pycache__)."
    )
    input_schema = GlobInput
    aliases = ["find_files"]

    def __init__(self, allowed_root: str | None = None):
        self.allowed_root = Path(allowed_root or os.getcwd()).resolve()

    def _resolve_root(self, path: str | None) -> Path:
        if path:
            p = Path(path)
            if not p.is_absolute():
                p = self.allowed_root / p
            return p.resolve()
        return self.allowed_root

    def is_readonly(self, input_data: GlobInput) -> bool:
        return True

    def check_permissions(
        self, input_data: GlobInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: GlobInput, context: dict[str, Any]) -> ToolResult:
        try:
            root = self._resolve_root(input_data.path)
            if not root.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Directory does not exist: {root}",
                )

            matches: list[Path] = []
            for p in root.glob(input_data.pattern):
                if not p.is_file():
                    continue
                # Skip excluded dirs
                if any(part in EXCLUDE_DIRS for part in p.parts):
                    continue
                matches.append(p)
                if len(matches) >= input_data.max_results:
                    break

            # Sort by mtime descending (most recent first)
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Make paths relative to root for readability
            try:
                rel_paths = [str(p.relative_to(root)) for p in matches]
            except ValueError:
                rel_paths = [str(p) for p in matches]

            output = "\n".join(rel_paths) if rel_paths else "(no matches)"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "match_count": len(matches),
                    "pattern": input_data.pattern,
                    "root": str(root),
                },
            )

        except Exception as e:
            logger.error("glob_error", error=str(e), pattern=input_data.pattern)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to glob: {e}",
            )
