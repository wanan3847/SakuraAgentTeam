"""Docker sandbox for safe code execution.

This module provides a Docker-based sandbox for executing agent tools
in an isolated environment. Inspired by OpenHands Runtime.
"""

import asyncio
import os
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

import docker
from docker.models.containers import Container

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SandboxError(Exception):
    """Error during sandbox operations."""

    pass


class DockerSandbox:
    """Docker-based sandbox for safe code execution.

    Features:
    - Isolated container environment
    - Resource limits (CPU, memory, time)
    - File system isolation
    - Network isolation (optional)
    - Automatic cleanup
    """

    def __init__(
        self,
        image: str = None,
        timeout: int = None,
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
        network_disabled: bool = False,
    ):
        """Initialize the Docker sandbox.

        Args:
            image: Docker image to use
            timeout: Default timeout in seconds
            memory_limit: Memory limit (e.g., "512m", "1g")
            cpu_limit: CPU limit (number of CPUs)
            network_disabled: Whether to disable network access
        """
        self.image = image or settings.sandbox_image
        self.timeout = timeout or settings.sandbox_timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_disabled = network_disabled

        self.client: Optional[docker.DockerClient] = None
        self.container: Optional[Container] = None
        self.workspace: Optional[Path] = None

    async def __aenter__(self) -> "DockerSandbox":
        """Create and start the sandbox container."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop and remove the sandbox container."""
        await self.stop()

    async def start(self) -> None:
        """Start the sandbox container."""
        try:
            # Initialize Docker client
            self.client = docker.from_env()

            # Create workspace directory
            self.workspace = Path(tempfile.mkdtemp(prefix="sandbox_"))

            # Pull image if not present
            try:
                self.client.images.get(self.image)
                logger.debug("sandbox_image_found", image=self.image)
            except docker.errors.ImageNotFound:
                logger.info("sandbox_image_pulling", image=self.image)
                self.client.images.pull(self.image)

            # Create container
            self.container = self.client.containers.create(
                image=self.image,
                detach=True,
                working_dir="/workspace",
                volumes={
                    str(self.workspace): {"bind": "/workspace", "mode": "rw"}
                },
                mem_limit=self.memory_limit,
                cpu_period=100000,
                cpu_quota=int(100000 * self.cpu_limit),
                network_disabled=self.network_disabled,
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
            )

            # Start container
            self.container.start()

            logger.info(
                "sandbox_started",
                container_id=self.container.id[:12],
                image=self.image,
                workspace=str(self.workspace),
            )

        except docker.errors.DockerException as e:
            logger.error("sandbox_start_failed", error=str(e))
            raise SandboxError(f"Failed to start sandbox: {e}")

    async def stop(self) -> None:
        """Stop and remove the sandbox container."""
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                logger.info("sandbox_stopped", container_id=self.container.id[:12])
            except docker.errors.DockerException as e:
                logger.warning("sandbox_stop_failed", error=str(e))
            finally:
                self.container = None

        # Clean up workspace
        if self.workspace and self.workspace.exists():
            import shutil
            shutil.rmtree(self.workspace, ignore_errors=True)
            self.workspace = None

    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        workdir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute a command in the sandbox.

        Args:
            command: Command to execute
            timeout: Timeout in seconds (overrides default)
            workdir: Working directory inside container
            env: Environment variables

        Returns:
            Dict with 'exit_code', 'stdout', 'stderr'
        """
        if not self.container:
            raise SandboxError("Sandbox not started")

        timeout = timeout or self.timeout
        workdir = workdir or "/workspace"

        logger.debug(
            "sandbox_execute_start",
            command=command,
            timeout=timeout,
            workdir=workdir,
        )

        try:
            # Execute command in container
            exit_code, output = self.container.exec_run(
                cmd=["/bin/bash", "-c", command],
                workdir=workdir,
                environment=env or {},
                demux=True,
            )

            stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
            stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""

            logger.debug(
                "sandbox_execute_complete",
                exit_code=exit_code,
                stdout_len=len(stdout),
                stderr_len=len(stderr),
            )

            return {
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            }

        except docker.errors.DockerException as e:
            logger.error("sandbox_execute_failed", error=str(e))
            raise SandboxError(f"Failed to execute command: {e}")

    async def write_file(self, path: str, content: str) -> None:
        """Write a file to the sandbox.

        Args:
            path: Path inside container
            content: File content
        """
        if not self.container:
            raise SandboxError("Sandbox not started")

        # Create tar archive with the file
        tar_stream = BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            data = content.encode("utf-8")
            tarinfo = tarfile.TarInfo(name=path)
            tarinfo.size = len(data)
            tar.addfile(tarinfo, BytesIO(data))

        tar_stream.seek(0)

        # Copy file to container
        self.container.put_archive("/workspace", tar_stream)

        logger.debug("sandbox_file_written", path=path, size=len(content))

    async def read_file(self, path: str) -> str:
        """Read a file from the sandbox.

        Args:
            path: Path inside container

        Returns:
            File content
        """
        if not self.container:
            raise SandboxError("Sandbox not started")

        try:
            # Get file from container
            bits, stat = self.container.get_archive(f"/workspace/{path}")

            # Extract content from tar
            tar_stream = BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)

            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                member = tar.getmembers()[0]
                f = tar.extractfile(member)
                if f:
                    content = f.read().decode("utf-8")
                    logger.debug("sandbox_file_read", path=path, size=len(content))
                    return content

            raise SandboxError(f"Failed to read file: {path}")

        except docker.errors.DockerException as e:
            logger.error("sandbox_read_file_failed", error=str(e))
            raise SandboxError(f"Failed to read file: {e}")


async def create_sandbox(**kwargs) -> DockerSandbox:
    """Create and start a new sandbox.

    Args:
        **kwargs: Arguments for DockerSandbox

    Returns:
        Started sandbox instance
    """
    sandbox = DockerSandbox(**kwargs)
    await sandbox.start()
    return sandbox
