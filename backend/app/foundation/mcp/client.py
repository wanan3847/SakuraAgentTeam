"""MCP (Model Context Protocol) 客户端实现。

通过 stdio transport 与 MCP server 通信，使用 JSON-RPC 2.0 协议。
每行一个 JSON 对象，通过 subprocess 的 stdin/stdout 交换消息。
不依赖官方 MCP SDK，自行实现 JSON-RPC 通信。
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.foundation.mcp.config import ServerConfig

logger = get_logger(__name__)

# 请求超时时间（秒）
REQUEST_TIMEOUT = 30.0
# 启动握手超时时间（秒）
STARTUP_TIMEOUT = 30.0
# 终止进程后等待退出的超时（秒）
TERMINATE_TIMEOUT = 5.0
# MCP 协议版本
PROTOCOL_VERSION = "2024-11-05"
# 客户端信息
CLIENT_INFO = {"name": "sakura-agent-team", "version": "0.1.0"}


class MCPError(Exception):
    """MCP 通信错误。"""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"MCP error [{code}]: {message}")


@dataclass
class _ServerConnection:
    """单个 MCP server 连接的内部状态。"""

    process: asyncio.subprocess.Process
    reader_task: asyncio.Task[None] | None = None
    stderr_task: asyncio.Task[None] | None = None
    # 写锁，保证每行 JSON-RPC 消息原子写入 stdin
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # 等待响应的 future，按请求 id 索引
    pending: dict[int, asyncio.Future[dict[str, Any]]] = field(default_factory=dict)
    # 该 server 提供的工具列表
    tools: list[dict[str, Any]] = field(default_factory=list)


class MCPClient:
    """MCP 客户端，管理多个 MCP server 连接。

    使用 stdio transport（subprocess + JSON-RPC over stdin/stdout）。
    每行一个 JSON 对象进行通信。
    """

    def __init__(self) -> None:
        """初始化 MCP 客户端。"""
        self._servers: dict[str, _ServerConnection] = {}
        self._next_id: int = 1

    def _next_request_id(self) -> int:
        """获取下一个请求 id（自增计数器）。"""
        rid = self._next_id
        self._next_id += 1
        return rid

    def is_running(self, server_name: str) -> bool:
        """检查指定 server 是否正在运行。"""
        conn = self._servers.get(server_name)
        return conn is not None and conn.process.returncode is None

    async def start_server(self, name: str, config: ServerConfig) -> bool:
        """启动一个 MCP server subprocess 并完成初始化握手。

        启动后依次发送 initialize 请求、notifications/initialized 通知、
        tools/list 请求，拿到工具列表。

        Args:
            name: server 名称
            config: server 配置

        Returns:
            启动成功返回 True，失败返回 False
        """
        if self.is_running(name):
            logger.warning("mcp_server_already_running", server=name)
            return True

        # 合并环境变量：继承当前进程环境 + server 配置的 env
        env = {**os.environ, **config.env}

        try:
            process = await asyncio.create_subprocess_exec(
                config.command,
                *config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError:
            logger.error("mcp_server_command_not_found", server=name, command=config.command)
            return False
        except OSError as e:
            logger.error("mcp_server_start_failed", server=name, error=str(e))
            return False

        conn = _ServerConnection(process=process)
        conn.reader_task = asyncio.create_task(self._read_stdout(name, conn))
        conn.stderr_task = asyncio.create_task(self._read_stderr(name, process))
        self._servers[name] = conn

        try:
            # 1. 发送 initialize 请求
            init_result = await self._request(
                name,
                conn,
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": CLIENT_INFO,
                },
                timeout=STARTUP_TIMEOUT,
            )

            # 2. 发送 initialized 通知（无需响应）
            await self._notify(name, conn, "notifications/initialized")

            # 3. 发送 tools/list 请求获取工具列表
            tools_result = await self._request(
                name,
                conn,
                "tools/list",
                {},
                timeout=STARTUP_TIMEOUT,
            )
            conn.tools = tools_result.get("tools", [])

            logger.info(
                "mcp_server_started",
                server=name,
                tools_count=len(conn.tools),
                protocol_version=init_result.get("protocolVersion"),
            )
            return True

        except asyncio.TimeoutError:
            logger.error("mcp_server_init_timeout", server=name)
            await self._cleanup_server(name, conn)
            return False
        except MCPError as e:
            logger.error(
                "mcp_server_init_failed",
                server=name,
                code=e.code,
                message=e.message,
            )
            await self._cleanup_server(name, conn)
            return False
        except Exception as e:
            logger.error("mcp_server_init_error", server=name, error=str(e))
            await self._cleanup_server(name, conn)
            return False

    async def _read_stdout(self, name: str, conn: _ServerConnection) -> None:
        """后台任务：逐行读取 server stdout 并分发响应。"""
        stdout = conn.process.stdout
        if stdout is None:
            return
        try:
            while True:
                line = await stdout.readline()
                if not line:
                    # EOF，server 关闭了 stdout
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    logger.warning("mcp_invalid_json", server=name, line=text[:200])
                    continue

                # 通知（无 id 字段）暂不处理，仅记录
                if "id" not in msg:
                    logger.debug("mcp_notification", server=name, method=msg.get("method"))
                    continue

                # 响应：根据 id 找到对应的 future
                rid = msg["id"]
                future = conn.pending.pop(rid, None)
                if future is None or future.done():
                    continue
                if "error" in msg:
                    err = msg["error"]
                    future.set_exception(
                        MCPError(
                            err.get("code", -1),
                            err.get("message", "unknown error"),
                        )
                    )
                else:
                    future.set_result(msg.get("result", {}))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("mcp_reader_error", server=name, error=str(e))
        finally:
            # 读取结束，把所有 pending future 设为异常
            for fut in conn.pending.values():
                if not fut.done():
                    fut.set_exception(MCPError(-1, f"server {name} connection closed"))
            conn.pending.clear()
            logger.info("mcp_reader_stopped", server=name)

    async def _read_stderr(self, name: str, process: asyncio.subprocess.Process) -> None:
        """后台任务：读取 server stderr 并记录日志（避免缓冲区填满导致死锁）。"""
        stderr = process.stderr
        if stderr is None:
            return
        try:
            while True:
                line = await stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    logger.debug("mcp_server_stderr", server=name, line=text[:500])
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def _request(
        self,
        name: str,
        conn: _ServerConnection,
        method: str,
        params: dict[str, Any],
        timeout: float = REQUEST_TIMEOUT,
    ) -> dict[str, Any]:
        """发送 JSON-RPC 请求并等待响应。

        Raises:
            MCPError: server 进程已退出或返回错误
            asyncio.TimeoutError: 请求超时
        """
        if conn.process.returncode is not None:
            raise MCPError(-1, f"server {name} process exited")
        stdin = conn.process.stdin
        if stdin is None:
            raise MCPError(-1, f"server {name} stdin unavailable")

        rid = self._next_request_id()
        payload = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
        data = (json.dumps(payload) + "\n").encode("utf-8")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        conn.pending[rid] = future

        try:
            async with conn.write_lock:
                stdin.write(data)
                await stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            conn.pending.pop(rid, None)
            raise MCPError(-1, f"server {name} write failed: {e}") from e

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            conn.pending.pop(rid, None)
            raise

    async def _notify(
        self,
        name: str,
        conn: _ServerConnection,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """发送 JSON-RPC 通知（无 id，不等待响应）。"""
        if conn.process.returncode is not None:
            return
        stdin = conn.process.stdin
        if stdin is None:
            return

        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        data = (json.dumps(payload) + "\n").encode("utf-8")

        try:
            async with conn.write_lock:
                stdin.write(data)
                await stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """调用 MCP 工具，返回结果文本。

        Args:
            server_name: server 名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果文本

        Raises:
            MCPError: server 未运行、调用超时或返回错误
        """
        conn = self._servers.get(server_name)
        if conn is None or conn.process.returncode is not None:
            raise MCPError(-1, f"server {server_name} not running")

        try:
            result = await self._request(
                server_name,
                conn,
                "tools/call",
                {"name": tool_name, "arguments": arguments},
                timeout=REQUEST_TIMEOUT,
            )
        except asyncio.TimeoutError as e:
            raise MCPError(-1, f"tool call timeout: {tool_name}") from e

        # MCP 工具结果格式：{"content": [{"type": "text", "text": "..."}], "isError": bool}
        return self._extract_text(result)

    @staticmethod
    def _extract_text(result: dict[str, Any]) -> str:
        """从 MCP 工具调用结果中提取文本。"""
        content = result.get("content", [])
        if not isinstance(content, list):
            return json.dumps(result, ensure_ascii=False)
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(str(item.get("text", "")))
                else:
                    texts.append(json.dumps(item, ensure_ascii=False))
            else:
                texts.append(str(item))
        return "\n".join(texts)

    def list_all_tools(self) -> list[dict[str, Any]]:
        """列出所有正在运行的 server 的所有工具。

        Returns:
            工具列表，每项格式：
            {"server": name, "name": tool_name, "description": desc, "input_schema": schema}
        """
        result: list[dict[str, Any]] = []
        for server_name, conn in self._servers.items():
            if conn.process.returncode is not None:
                continue
            for tool in conn.tools:
                result.append(
                    {
                        "server": server_name,
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("inputSchema", {}),
                    }
                )
        return result

    async def stop_server(self, name: str) -> None:
        """停止指定 server。"""
        conn = self._servers.pop(name, None)
        if conn is None:
            return
        await self._cleanup_server(name, conn)

    async def _cleanup_server(self, name: str, conn: _ServerConnection) -> None:
        """清理 server 连接资源：取消读取任务、终止进程。"""
        # 取消后台读取任务
        for task in (conn.reader_task, conn.stderr_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        # 终止进程
        if conn.process.returncode is None:
            try:
                conn.process.terminate()
                await asyncio.wait_for(conn.process.wait(), timeout=TERMINATE_TIMEOUT)
            except asyncio.TimeoutError:
                conn.process.kill()
                await conn.process.wait()
            except ProcessLookupError:
                pass
            except Exception:
                pass

        logger.info("mcp_server_stopped", server=name)

    async def stop_all(self) -> None:
        """停止所有 server。"""
        names = list(self._servers.keys())
        for name in names:
            await self.stop_server(name)
