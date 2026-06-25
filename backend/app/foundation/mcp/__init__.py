"""MCP (Model Context Protocol) 客户端模块。

提供与 MCP server 的 stdio 通信能力，支持工具发现与调用。
"""

from app.foundation.mcp.client import MCPClient
from app.foundation.mcp.config import ServerConfig, load_mcp_config

__all__ = ["MCPClient", "ServerConfig", "load_mcp_config", "mcp_client"]

# 全局单例
mcp_client = MCPClient()
