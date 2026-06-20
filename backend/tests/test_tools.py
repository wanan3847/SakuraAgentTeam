"""Tests for tools."""

from app.foundation.tools import (
    FileReadInput,
    FileReadTool,
    FileWriteInput,
    FileWriteTool,
    ShellRunInput,
    tool_registry,
)


def test_tool_registry():
    """Test tool registry."""
    tools = tool_registry.list_tools()

    assert "file_read" in tools
    assert "file_write" in tools
    assert "shell_run" in tools


def test_file_read_input_validation():
    """Test FileReadInput validation."""
    input_data = FileReadInput(file_path="/test/file.txt")

    assert input_data.file_path == "/test/file.txt"
    assert input_data.encoding == "utf-8"


def test_file_write_input_validation():
    """Test FileWriteInput validation."""
    input_data = FileWriteInput(
        file_path="/test/file.txt",
        content="Hello, World!",
    )

    assert input_data.file_path == "/test/file.txt"
    assert input_data.content == "Hello, World!"
    assert input_data.mode == "write"


def test_shell_run_input_validation():
    """Test ShellRunInput validation."""
    input_data = ShellRunInput(command="ls -la")

    assert input_data.command == "ls -la"
    assert input_data.timeout == 60


def test_file_read_tool_is_readonly():
    """Test FileReadTool is readonly."""
    tool = FileReadTool()
    input_data = FileReadInput(file_path="/test/file.txt")

    assert tool.is_readonly(input_data) is True


def test_file_write_tool_not_readonly():
    """Test FileWriteTool is not readonly."""
    tool = FileWriteTool()
    input_data = FileWriteInput(file_path="/test/file.txt", content="test")

    assert tool.is_readonly(input_data) is False
