"""MCP server 配置加载。

读取 ~/.sakura/mcp.json 配置文件，解析 MCP server 启动参数。
配置文件不存在时返回空 dict，不报错。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

# 配置文件默认路径
CONFIG_PATH = Path.home() / ".sakura" / "mcp.json"


@dataclass
class ServerConfig:
    """单个 MCP server 的启动配置。"""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


def load_mcp_config(config_path: Path | None = None) -> dict[str, ServerConfig]:
    """加载 MCP server 配置。

    Args:
        config_path: 配置文件路径，默认为 ~/.sakura/mcp.json

    Returns:
        server 名称到 ServerConfig 的映射；配置文件不存在或格式错误时返回空 dict
    """
    path = config_path or CONFIG_PATH
    if not path.exists():
        logger.debug("mcp_config_not_found", path=str(path))
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("mcp_config_invalid_json", path=str(path), error=str(e))
        return {}
    except OSError as e:
        logger.error("mcp_config_read_failed", path=str(path), error=str(e))
        return {}

    servers_raw = raw.get("mcpServers", {})
    if not isinstance(servers_raw, dict):
        logger.error("mcp_config_invalid_format", path=str(path))
        return {}

    configs: dict[str, ServerConfig] = {}
    for name, spec in servers_raw.items():
        if not isinstance(spec, dict):
            continue
        command = spec.get("command")
        if not command:
            logger.warning("mcp_server_missing_command", server=name)
            continue
        configs[name] = ServerConfig(
            name=name,
            command=command,
            args=list(spec.get("args", [])),
            env=dict(spec.get("env", {})),
        )

    logger.info("mcp_config_loaded", path=str(path), count=len(configs))
    return configs
