"""Shell command execution tool.

This tool executes shell commands in a sandboxed environment.
For MVP, it uses subprocess with restrictions.
For production, it should use Docker sandbox.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

from pydantic import Field

from app.core.config import settings
from app.core.logging import get_logger
from app.foundation.tools.base import (
    PermissionResult,
    Tool,
    ToolInput,
    ToolResult,
)

logger = get_logger(__name__)


class ShellRunInput(ToolInput):
    """Input for ShellRunTool."""

    command: str = Field(..., description="Command to execute")
    cwd: str | None = Field(None, description="Working directory")
    timeout: int = Field(60, description="Timeout in seconds", ge=1, le=600)
    env: dict[str, str] | None = Field(None, description="Environment variables")


# Blocked commands for security
BLOCKED_COMMANDS = [
    "rm -rf /",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",  # Fork bomb
    "chmod -R 777 /",
    "chown -R",
]

# Allowed commands for MVP (will be expanded with Docker sandbox)
ALLOWED_COMMANDS = [
    "npm",
    "node",
    "python",
    "pip",
    "git",
    "ls",
    "cat",
    "mkdir",
    "touch",
    "echo",
    "grep",
    "find",
    "pwd",
    "which",
    "curl",
    "wget",
]


class ShellRunTool(Tool[ShellRunInput]):
    """Tool for executing shell commands.

    For MVP: Uses subprocess with command restrictions.
    For production: Should use Docker sandbox for isolation.

    Security measures:
    - Command whitelist (MVP) / Docker sandbox (production)
    - Timeout enforcement
    - Working directory restriction
    - Environment variable filtering
    """

    name = "shell_run"
    description = "Execute a shell command in a sandboxed environment"
    input_schema = ShellRunInput
    aliases = ["run", "exec", "bash"]

    def __init__(self, allowed_root: str | None = None):
        """Initialize the shell run tool.

        Args:
            allowed_root: Root directory for command execution.
                         If None, uses projects_root from settings.
        """
        self.allowed_root = Path(allowed_root or settings.projects_root).resolve()
        self.allowed_root.mkdir(parents=True, exist_ok=True)

    def _is_command_allowed(self, command: str) -> bool:
        """Check if command is allowed.

        Args:
            command: Command to check

        Returns:
            True if command is allowed
        """
        # Check for blocked commands
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return False

        # For MVP, check against allowed list
        # In production with Docker, this can be relaxed
        cmd_parts = command.split()
        if not cmd_parts:
            return False

        base_cmd = cmd_parts[0]
        return base_cmd in ALLOWED_COMMANDS

    def check_permissions(
        self, input_data: ShellRunInput, context: dict[str, Any]
    ) -> PermissionResult:
        """Check if the command can be executed.

        Args:
            input_data: Tool input
            context: Execution context

        Returns:
            Permission result
        """
        # Check if command is allowed
        if not self._is_command_allowed(input_data.command):
            logger.warning(
                "shell_command_blocked",
                command=input_data.command,
            )
            return PermissionResult.DENY

        # Check working directory
        if input_data.cwd:
            cwd_path = Path(input_data.cwd)
            if not cwd_path.is_absolute():
                cwd_path = self.allowed_root / cwd_path
            cwd_path = cwd_path.resolve()

            if not str(cwd_path).startswith(str(self.allowed_root)):
                return PermissionResult.DENY

        return PermissionResult.ALLOW

    async def call(self, input_data: ShellRunInput, context: dict[str, Any]) -> ToolResult:
        """Execute the shell command.

        Args:
            input_data: Tool input
            context: Execution context

        Returns:
            Tool result with command output
        """
        try:
            # Determine working directory
            cwd = self.allowed_root
            if input_data.cwd:
                cwd_path = Path(input_data.cwd)
                if not cwd_path.is_absolute():
                    cwd_path = self.allowed_root / cwd_path
                cwd = cwd_path.resolve()

            # Prepare environment
            env = os.environ.copy()
            if input_data.env:
                # Filter sensitive environment variables
                sensitive_keys = ["API_KEY", "SECRET", "PASSWORD", "TOKEN"]
                for key, value in input_data.env.items():
                    if not any(s in key.upper() for s in sensitive_keys):
                        env[key] = value

            logger.info(
                "shell_run_start",
                command=input_data.command,
                cwd=str(cwd),
                timeout=input_data.timeout,
            )

            # Execute command
            process = await asyncio.create_subprocess_shell(
                input_data.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=input_data.timeout,
                )
            except TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {input_data.timeout} seconds",
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            success = process.returncode == 0
            output = stdout_str if success else stderr_str

            logger.info(
                "shell_run_complete",
                command=input_data.command,
                return_code=process.returncode,
                success=success,
            )

            return ToolResult(
                success=success,
                output=output,
                error=stderr_str if not success else None,
                metadata={
                    "return_code": process.returncode,
                    "stdout_length": len(stdout_str),
                    "stderr_length": len(stderr_str),
                },
            )

        except Exception as e:
            logger.error("shell_run_error", error=str(e), command=input_data.command)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to execute command: {e}",
            )
