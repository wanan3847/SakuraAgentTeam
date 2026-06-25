"""Sakura CLI 主入口 — typer 应用。

子命令：
  serve                  启动 Web 服务（后端 API）
  frontend               启动前端开发服务器
  start                  一键启动（后端 + 前端）
  chat                   CLI 模式和团队聊天
  agents                 列出所有 agent
  teams                  列出所有团队
  create-team            创建自定义团队
  history                查看历史记录
  task <requirement>     提交新任务（自动启动工作流）
  sessions               列出所有会话
  status <id>            查看会话详情
  logs <id>              跟踪会话事件流（SSE）
  artifacts <id>         列出产物
  cancel <id>            取消会话
  projects               列出项目
  login                  用户登录
  register               用户注册
  install                安装/更新前后端依赖
  config                 配置 API URL / token / LLM / 默认团队
  providers              列出支持的 LLM 提供商（litellm）
  llm-providers          列出后端注册的 254 个 LLM 供应商（含 base_url/文档）
  llm-test               测试任意 LLM 连接（用你自己的 key）
  llm-fetch-models       拉取可用模型列表
  llm-configs            列出已保存的 LLM 配置
  llm-save               保存一条 LLM 配置（私有 key + url + model）
  llm-delete             删除一条 LLM 配置
  llm-test-config       测试已保存配置的连接
  doctor                 诊断连接 / 健康检查
  version                打印版本
  repl                   交互式 REPL
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import typer

from . import __version__
from .client import SakuraAPIError, SakuraClient
from .config import CONFIG_FILE, get_config
from .output import emit, error, info, success

app = typer.Typer(
    name="sakura",
    help="SakuraAgentTeam 命令行客户端 — 调度多智能体工作流",
    no_args_is_help=True,
    add_completion=False,
)

config_app = typer.Typer(help="管理 CLI 配置（~/.sakura/config.toml）")
app.add_typer(config_app, name="config")


def _client() -> SakuraClient:
    return SakuraClient(get_config())


def _backend_dir() -> Path:
    """返回 backend 目录（cli 的上级目录）。"""
    return Path(__file__).resolve().parent.parent


def _project_root() -> Path:
    """返回项目根目录（backend 的上级目录）。"""
    return _backend_dir().parent


# ============================================================
# serve — 启动后端 Web 服务
# ============================================================


@app.command("serve")
def cmd_serve(
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    host: str = typer.Option("0.0.0.0", "--host", help="监听地址"),
    reload: bool = typer.Option(False, "--reload", help="热重载（开发模式）"),
) -> None:
    """启动后端 Web 服务（FastAPI + uvicorn）。"""
    info(f"启动后端服务: http://{host}:{port}")
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.api.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")
    try:
        subprocess.run(cmd, cwd=str(_backend_dir()))
    except KeyboardInterrupt:
        info("后端服务已停止")


# ============================================================
# frontend — 启动前端开发服务器
# ============================================================


@app.command("frontend")
def cmd_frontend(
    port: int = typer.Option(5173, "--port", "-p", help="监听端口"),
) -> None:
    """启动前端开发服务器（Vite）。"""
    frontend_dir = _project_root() / "frontend"
    if not frontend_dir.exists():
        error(f"前端目录不存在: {frontend_dir}")
        raise typer.Exit(1)
    info(f"启动前端服务: http://localhost:{port}")
    env = {**os.environ, "PORT": str(port)}
    try:
        subprocess.run(["npm", "run", "dev", "--", "--port", str(port)],
                       cwd=str(frontend_dir), env=env)
    except KeyboardInterrupt:
        info("前端服务已停止")


# ============================================================
# start — 一键启动（后端 + 前端）
# ============================================================


@app.command("start")
def cmd_start(
    backend_port: int = typer.Option(8000, "--backend-port", help="后端端口"),
    frontend_port: int = typer.Option(5173, "--frontend-port", help="前端端口"),
) -> None:
    """一键启动后端 + 前端。"""
    import signal

    frontend_dir = _project_root() / "frontend"
    backend_dir = _backend_dir()

    info(f"启动后端: http://localhost:{backend_port}")
    backend_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "app.api.main:app",
            "--host", "0.0.0.0",
            "--port", str(backend_port),
        ],
        cwd=str(backend_dir),
    )

    info(f"启动前端: http://localhost:{frontend_port}")
    frontend_proc = None
    if frontend_dir.exists():
        env = {**os.environ, "PORT": str(frontend_port)}
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(frontend_port)],
            cwd=str(frontend_dir),
            env=env,
        )
    else:
        error(f"前端目录不存在: {frontend_dir}（跳过前端）")

    def _cleanup(*_):
        info("正在停止服务…")
        for p in (frontend_proc, backend_proc):
            if p and p.poll() is None:
                p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    info("按 Ctrl+C 停止所有服务")
    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        _cleanup()


# ============================================================
# chat — CLI 模式和团队聊天
# ============================================================


@app.command("chat")
def cmd_chat(
    team: str = typer.Option(..., "--team", "-t", help="团队 ID"),
    message: str = typer.Option(..., "--message", "-m", help="消息内容"),
) -> None:
    """和指定团队聊天（流式输出）。"""
    cfg = get_config()
    with _client() as c:
        try:
            # 使用 SSE 流式接口
            import httpx
            url = f"{cfg.api_url.rstrip('/')}/api/v1/teams/{team}/chat"
            headers = {"Content-Type": "application/json"}
            if cfg.api_token:
                headers["Authorization"] = f"Bearer {cfg.api_token}"
            with httpx.Client(timeout=None) as client:
                with client.stream("POST", url, json={"message": message}, headers=headers) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line.startswith("data: "):
                            raw = line[6:]
                            try:
                                data = json.loads(raw)
                                msg_type = data.get("type", "")
                                if msg_type == "token":
                                    print(data.get("content", ""), end="", flush=True)
                                elif msg_type == "message":
                                    print()
                                    print(f"[{data.get('name', data.get('role', '?'))}] {data.get('content', '')}")
                                elif msg_type == "done":
                                    success("\n完成")
                                elif msg_type == "error":
                                    error(data.get("message", "未知错误"))
                                    raise typer.Exit(1)
                            except json.JSONDecodeError:
                                pass
        except httpx.ConnectError as e:
            error(f"无法连接后端 {cfg.api_url}: {e}")
            raise typer.Exit(1) from None
        except Exception as e:
            error(str(e))
            raise typer.Exit(1) from None


# ============================================================
# agents — 列出所有 agent
# ============================================================


@app.command("agents")
def cmd_agents(
    category: str | None = typer.Option(None, "--category", "-c", help="按分类过滤"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """列出所有 agent（可按分类过滤）。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    with _client() as c:
        try:
            url = "/api/v1/experts"
            if category:
                url += f"?category={category}"
            data = c._request("GET", url)
            agents = data.get("agents", data.get("data", []))
            emit(agents, output_format=fmt)
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None


# ============================================================
# teams — 列出所有团队
# ============================================================


@app.command("teams")
def cmd_teams(
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """列出所有预设团队。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    with _client() as c:
        try:
            data = c._request("GET", "/api/v1/teams")
            teams = data.get("teams", data.get("data", []))
            emit(teams, output_format=fmt)
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None


# ============================================================
# create-team — 创建自定义团队
# ============================================================


@app.command("create-team")
def cmd_create_team(
    name: str = typer.Option(..., "--name", "-n", help="团队名称"),
    members: str = typer.Option(..., "--members", "-m", help="成员 ID（逗号分隔）"),
    mode: str = typer.Option("group", "--mode", help="协作模式: group/pipeline/master/consensus/parallel/handoff/graph"),
    description: str = typer.Option("", "--description", "-d", help="团队描述"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """创建自定义团队。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    member_ids = [m.strip() for m in members.split(",") if m.strip()]
    if not member_ids:
        error("成员列表不能为空")
        raise typer.Exit(1)
    with _client() as c:
        try:
            data = c._request("POST", "/api/v1/teams", json={
                "name": name,
                "member_ids": member_ids,
                "mode": mode,
                "description": description,
            })
            emit(data.get("team", data.get("data", data)), output_format=fmt)
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None


# ============================================================
# history — 查看历史记录
# ============================================================


@app.command("history")
def cmd_history(
    limit: int = typer.Option(10, "--limit", "-n", help="返回条数"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """查看历史对话记录。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    if not cfg.api_token:
        error("未登录，请先 sakura login")
        raise typer.Exit(1)
    with _client() as c:
        try:
            data = c._request("GET", f"/api/v1/history?page=1&page_size={limit}")
            emit(data.get("data", []), output_format=fmt)
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None


# ============================================================
# config — 配置管理
# ============================================================


@config_app.command("show")
def config_show() -> None:
    """显示当前配置。"""
    cfg = get_config()
    emit(
        {
            "config_file": str(CONFIG_FILE),
            "exists": CONFIG_FILE.exists(),
            **cfg.to_dict(),
        },
        output_format=cfg.output_format,
    )


@config_app.command("set")
def config_set(
    api_url: str | None = typer.Option(None, "--api-url", help="后端 API 地址"),
    api_token: str | None = typer.Option(None, "--token", help="Bearer token"),
    workflow: str | None = typer.Option(
        None, "--workflow", help="默认 workflow（full_greenfield/brownfield/incremental）"
    ),
    output: str | None = typer.Option(None, "--output", help="输出格式 table/json"),
    default_team: str | None = typer.Option(None, "--default-team", help="默认团队 ID"),
) -> None:
    """更新配置并写入 ~/.sakura/config.toml。"""
    cfg = get_config()
    if api_url:
        cfg.api_url = api_url
    if api_token:
        cfg.api_token = api_token
    if workflow is not None:
        cfg.default_workflow = workflow
    if output:
        cfg.output_format = output
    if default_team:
        cfg.default_team = default_team
    cfg.save()
    success(f"配置已保存到 {CONFIG_FILE}")
    emit(cfg.to_dict())


@config_app.command("set-llm")
def config_set_llm(
    provider: str = typer.Option(..., "--provider", help="供应商: openai/anthropic/litellm/deepseek"),
    api_key: str = typer.Option(..., "--api-key", help="API Key"),
    api_base: str | None = typer.Option(None, "--api-base", help="API Base URL（可选）"),
    model: str | None = typer.Option(None, "--model", help="模型名（可选）"),
) -> None:
    """配置 LLM 供应商。"""
    cfg = get_config()
    cfg.llm_provider = provider
    cfg.llm_api_key = api_key
    if api_base:
        cfg.llm_api_base = api_base
    if model:
        cfg.llm_model = model
    cfg.save()
    success(f"LLM 配置已保存到 {CONFIG_FILE}")
    info(f"供应商: {provider}")
    info(f"模型: {model or '(默认)'}")
    info("提示: 重启后端服务使配置生效")


@config_app.command("list-providers")
def config_list_providers() -> None:
    """列出支持的 LLM 提供商。"""
    try:
        from app.foundation.llm import COMMON_PROVIDERS
        data = [{"prefix": p, "description": d} for p, d in COMMON_PROVIDERS]
        emit(data)
    except ImportError:
        # 不依赖 app 包时给出内置列表
        data = [
            {"prefix": "openai", "description": "OpenAI GPT 系列"},
            {"prefix": "anthropic", "description": "Anthropic Claude 系列"},
            {"prefix": "deepseek", "description": "DeepSeek 深度求索"},
            {"prefix": "dashscope", "description": "阿里通义千问"},
            {"prefix": "moonshot", "description": "月之暗面 Kimi"},
            {"prefix": "zhipu", "description": "智谱 GLM"},
            {"prefix": "baichuan", "description": "百川大模型"},
            {"prefix": "yi", "description": "零一万物"},
            {"prefix": "lite", "description": "LiteLLM 100+ 供应商统一接口"},
        ]
        emit(data)


@config_app.command("test-llm")
def config_test_llm() -> None:
    """测试 LLM 连接是否正常。"""
    cfg = get_config()
    if not cfg.llm_api_key:
        error("未配置 LLM API Key，请先 sakura config set-llm")
        raise typer.Exit(1)
    info(f"测试 LLM: provider={cfg.llm_provider}, model={cfg.llm_model or '默认'}")
    try:
        from app.foundation.llm import LLMProviderFactory
        provider_name = cfg.llm_provider or "openai"
        model = cfg.llm_model or "gpt-4o"
        provider = LLMProviderFactory.create(
            provider=provider_name,
            model=model,
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_api_base or None,
        )
        from app.foundation.llm.base import Message, MessageRole
        messages = [Message(role=MessageRole.USER, content="说'你好'两个字")]
        resp = provider.chat(messages)
        content = resp.content if hasattr(resp, "content") else str(resp)
        success(f"LLM 连接正常！回复: {content[:100]}")
    except ImportError:
        # 不依赖 app 包时用 httpx 直接测试
        import httpx
        api_base = cfg.llm_api_base or "https://api.openai.com/v1"
        url = f"{api_base.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {cfg.llm_api_key}", "Content-Type": "application/json"}
        body = {
            "model": cfg.llm_model or "gpt-4o",
            "messages": [{"role": "user", "content": "说'你好'两个字"}],
            "max_tokens": 10,
        }
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            success(f"LLM 连接正常！回复: {content}")
        except Exception as e:
            error(f"LLM 测试失败: {e}")
            raise typer.Exit(1) from None
    except Exception as e:
        error(f"LLM 测试失败: {e}")
        raise typer.Exit(1) from None


@config_app.command("path")
def config_path() -> None:
    """打印配置文件路径。"""
    # 通过模块属性访问以支持 monkeypatch（直接 import 是引用快照）
    import cli.config as _cfg_mod

    print(_cfg_mod.CONFIG_FILE)


# ============================================================
# login / register — 用户认证
# ============================================================


@app.command("login")
def cmd_login(
    username: str = typer.Option(..., "--username", "-u", help="用户名或邮箱"),
    password: str = typer.Option(..., "--password", "-p", help="密码"),
) -> None:
    """用户登录，保存 token 到配置。"""
    cfg = get_config()
    import httpx
    try:
        r = httpx.post(
            f"{cfg.api_url.rstrip('/')}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=30,
        )
        data = r.json()
        if not data.get("success"):
            error(data.get("error", "登录失败"))
            raise typer.Exit(1)
        token = data["token"]
        user = data["user"]
        cfg.api_token = token
        cfg.username = user.get("username", username)
        cfg.save()
        success(f"登录成功！欢迎 {cfg.username}")
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(f"登录失败: {e}")
        raise typer.Exit(1) from None


@app.command("register")
def cmd_register(
    username: str = typer.Option(..., "--username", "-u", help="用户名"),
    email: str = typer.Option(..., "--email", "-e", help="邮箱"),
    password: str = typer.Option(..., "--password", "-p", help="密码"),
) -> None:
    """注册新用户。"""
    cfg = get_config()
    import httpx
    try:
        r = httpx.post(
            f"{cfg.api_url.rstrip('/')}/api/v1/auth/register",
            json={"username": username, "email": email, "password": password},
            timeout=30,
        )
        data = r.json()
        if not data.get("success"):
            error(data.get("error", "注册失败"))
            raise typer.Exit(1)
        token = data["token"]
        user = data["user"]
        cfg.api_token = token
        cfg.username = user.get("username", username)
        cfg.save()
        success(f"注册成功！欢迎 {cfg.username}")
        info(f"角色: {user.get('role', 'user')}")
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(f"注册失败: {e}")
        raise typer.Exit(1) from None


# ============================================================
# install — 安装/更新依赖
# ============================================================


@app.command("install")
def cmd_install(
    frontend: bool = typer.Option(False, "--frontend", help="安装前端依赖"),
    backend: bool = typer.Option(False, "--backend", help="安装后端依赖"),
) -> None:
    """安装/更新前后端依赖。不指定参数时同时安装。"""
    if not frontend and not backend:
        frontend = True
        backend = True

    if backend:
        info("安装后端依赖…")
        backend_dir = _backend_dir()
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                cwd=str(backend_dir),
            )
            success("后端依赖安装完成")
        except Exception as e:
            error(f"后端安装失败: {e}")

    if frontend:
        info("安装前端依赖…")
        frontend_dir = _project_root() / "frontend"
        if not frontend_dir.exists():
            error(f"前端目录不存在: {frontend_dir}")
        else:
            try:
                subprocess.run(["npm", "install"], cwd=str(frontend_dir))
                success("前端依赖安装完成")
            except Exception as e:
                error(f"前端安装失败: {e}")


# ============================================================
# task
# ============================================================


@app.command("task")
def cmd_task(
    requirement: str = typer.Argument(..., help="需求描述（自然语言）"),
    project: str | None = typer.Option(None, "--project", "-p", help="关联 project_id"),
    workflow: str | None = typer.Option(
        None, "--workflow", "-w", help="工作流：full_greenfield / brownfield / incremental"
    ),
    no_wait: bool = typer.Option(False, "--no-wait", help="提交后不跟踪进度"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """提交一个新任务（自动启动工作流）。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    wf = workflow or cfg.default_workflow or None

    with _client() as c:
        try:
            data = c.create_session(requirement, project_id=project, workflow=wf)
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None

        success(f"任务已创建: {data['id']}")
        emit(data, output_format=fmt)

        if no_wait:
            return

        # 流式跟踪
        info("跟踪进度（Ctrl+C 中断跟踪，不取消任务）…")
        try:
            for evt in c.stream_events(data["id"]):
                ev = evt["event"]
                payload = evt["data"]
                if ev == "agent_started":
                    info(f"[{payload.get('agent_role')}] 开始…")
                elif ev == "agent_completed":
                    success(f"[{payload.get('agent_role')}] 完成")
                elif ev == "session_completed":
                    success("全部 Agent 流程完成！")
                    break
                elif ev == "session_failed":
                    error(f"任务失败: {payload.get('error')}")
                    raise typer.Exit(1) from None
        except KeyboardInterrupt:
            info("已中断跟踪，任务仍在后台运行。")


# ============================================================
# sessions / status / logs / artifacts / cancel
# ============================================================


@app.command("sessions")
def cmd_sessions(output_format: str | None = typer.Option(None, "--output", "-o")) -> None:
    """列出所有会话。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    with _client() as c:
        try:
            data = c.list_sessions()
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None
        emit(data, output_format=fmt)


@app.command("status")
def cmd_status(
    session_id: str = typer.Argument(..., help="会话 ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="持续刷新直到完成"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """查看会话详情。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    with _client() as c:
        try:
            while True:
                data = c.get_session(session_id)
                emit(data, output_format=fmt)
                if not watch or data["status"] in ("completed", "failed", "cancelled"):
                    break
                time.sleep(2)
                # 简单清屏（仅 watch 模式）
                if watch:
                    sys.stdout.write("\033[2J\033[H")
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None


@app.command("logs")
def cmd_logs(session_id: str = typer.Argument(..., help="会话 ID")) -> None:
    """流式打印会话事件（Ctrl+C 退出）。"""
    with _client() as c:
        try:
            for evt in c.stream_events(session_id):
                print(json.dumps(evt, ensure_ascii=False, default=str))
        except KeyboardInterrupt:
            pass
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None


@app.command("artifacts")
def cmd_artifacts(
    session_id: str = typer.Argument(..., help="会话 ID"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """列出某会话的所有产物。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    with _client() as c:
        try:
            data = c.get_artifacts(session_id)
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None
        emit(data, output_format=fmt)


@app.command("cancel")
def cmd_cancel(session_id: str = typer.Argument(..., help="会话 ID")) -> None:
    """取消一个进行中的会话。"""
    with _client() as c:
        try:
            data = c.cancel_session(session_id)
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None
        success(data.get("message", "已取消"))


# ============================================================
# projects
# ============================================================


@app.command("projects")
def cmd_projects(output_format: str | None = typer.Option(None, "--output", "-o")) -> None:
    """列出所有项目。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    with _client() as c:
        try:
            data = c.list_projects()
        except SakuraAPIError as e:
            error(str(e))
            raise typer.Exit(1) from None
        emit(data, output_format=fmt)


@app.command("providers")
def cmd_providers(
    full: bool = typer.Option(False, "--full", help="列出 litellm 注册的全部模型"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """列出支持的 LLM 提供商（默认常用 24 个，--full 全部 100+）。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    from app.foundation.llm import COMMON_PROVIDERS

    if full:
        try:
            import litellm

            models = sorted(litellm.model_cost.keys())
            data = [{"provider_model": m} for m in models]
        except ImportError:
            error("litellm 未安装")
            raise typer.Exit(1) from None
    else:
        data = [{"prefix": p, "description": d} for p, d in COMMON_PROVIDERS]

    emit(data, output_format=fmt)


# ============================================================
# llm-providers — 列出后端注册的 254 个 LLM 供应商
# ============================================================


@app.command("llm-providers")
def cmd_llm_providers(
    free: bool = typer.Option(False, "--free", help="只列出有免费额度的供应商"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """列出后端注册的 LLM 供应商（254 个，含 base_url/文档/免费额度）。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/llm/providers" + ("/free" if free else "")
    try:
        r = httpx.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        providers = data.get("data", [])
        if not providers:
            info("没有找到供应商")
            return
        info(f"共 {len(providers)} 个供应商" + ("（免费）" if free else ""))
        emit(providers, output_format=fmt)
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


# ============================================================
# llm-test — 测试任意 LLM 连接（用用户自己的 key）
# ============================================================


@app.command("llm-test")
def cmd_llm_test(
    base_url: str = typer.Option(..., "--base-url", help="API Base URL，如 https://api.deepseek.com/v1"),
    api_key: str = typer.Option(..., "--api-key", help="你的 API Key"),
    model: str = typer.Option(..., "--model", help="模型名，如 deepseek-chat"),
) -> None:
    """测试 LLM 连接（用你自己的 key 发一个最小请求）。"""
    cfg = get_config()
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/llm/test-connection"
    try:
        r = httpx.post(
            url,
            json={"base_url": base_url, "api_key": api_key, "model": model},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            success(f"连接成功！回复: {data.get('reply', '(空)')[:100]}")
        else:
            error(f"测试失败: {data.get('error', '未知错误')}")
            raise typer.Exit(1)
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


# ============================================================
# llm-fetch-models — 拉取可用模型列表
# ============================================================


@app.command("llm-fetch-models")
def cmd_llm_fetch_models(
    base_url: str = typer.Option(..., "--base-url", help="API Base URL"),
    api_key: str = typer.Option("", "--api-key", help="API Key（本地部署可留空）"),
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """用给定的 base_url + api_key 拉取可用模型列表。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/llm/fetch-models"
    try:
        r = httpx.post(
            url,
            json={"base_url": base_url, "api_key": api_key},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            models = data.get("models", [])
            success(f"发现 {len(models)} 个可用模型")
            emit(models, output_format=fmt)
        else:
            error(f"拉取失败: {data.get('error', '未知错误')}")
            raise typer.Exit(1)
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


# ============================================================
# llm-configs — 管理用户保存的 LLM 配置
# ============================================================


@app.command("llm-configs")
def cmd_llm_configs(
    output_format: str | None = typer.Option(None, "--output", "-o"),
) -> None:
    """列出当前用户保存的所有 LLM 配置。"""
    cfg = get_config()
    fmt = output_format or cfg.output_format
    if not cfg.api_token:
        error("未登录，请先 sakura login")
        raise typer.Exit(1)
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/llm/configs"
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {cfg.api_token}"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        configs = data.get("data", [])
        if not configs:
            info("还没有保存的 LLM 配置，用 sakura llm-save 添加")
            return
        info(f"共 {len(configs)} 个配置")
        emit(configs, output_format=fmt)
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


@app.command("llm-save")
def cmd_llm_save(
    provider_id: str = typer.Option(..., "--provider", help="内置厂商 ID（如 deepseek）或 custom"),
    api_key: str = typer.Option(..., "--api-key", help="你的 API Key"),
    model: str = typer.Option(..., "--model", help="默认模型名"),
    base_url: str = typer.Option("", "--base-url", help="自定义 Base URL（provider=custom 时必填）"),
    display_name: str = typer.Option("", "--name", help="显示名（可选）"),
    is_default: bool = typer.Option(False, "--default", help="设为默认配置"),
) -> None:
    """保存一条 LLM 配置（你的私有 key + url + model）。"""
    cfg = get_config()
    if not cfg.api_token:
        error("未登录，请先 sakura login")
        raise typer.Exit(1)
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/llm/configs"
    body: dict = {
        "provider_id": provider_id,
        "api_key": api_key,
        "model": model,
        "is_default": is_default,
    }
    if base_url:
        body["base_url"] = base_url
    if display_name:
        body["display_name"] = display_name
    try:
        r = httpx.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {cfg.api_token}", "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            success(f"配置已保存: {data.get('data', {}).get('display_name', provider_id)}")
        else:
            error(f"保存失败: {data.get('error', '未知错误')}")
            raise typer.Exit(1)
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


@app.command("llm-delete")
def cmd_llm_delete(
    config_id: int = typer.Option(..., "--id", help="配置 ID"),
) -> None:
    """删除一条已保存的 LLM 配置。"""
    cfg = get_config()
    if not cfg.api_token:
        error("未登录，请先 sakura login")
        raise typer.Exit(1)
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/llm/configs/{config_id}"
    try:
        r = httpx.delete(url, headers={"Authorization": f"Bearer {cfg.api_token}"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            success(f"配置 {config_id} 已删除")
        else:
            error(f"删除失败: {data.get('error', '未知错误')}")
            raise typer.Exit(1)
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


@app.command("llm-test-config")
def cmd_llm_test_config(
    config_id: int = typer.Option(..., "--id", help="配置 ID"),
) -> None:
    """测试已保存的某条 LLM 配置的连接。"""
    cfg = get_config()
    if not cfg.api_token:
        error("未登录，请先 sakura login")
        raise typer.Exit(1)
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/llm/configs/{config_id}/test"
    try:
        r = httpx.post(url, headers={"Authorization": f"Bearer {cfg.api_token}"}, timeout=60)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            success(f"连接成功！回复: {data.get('reply', '(空)')[:100]}")
        else:
            error(f"测试失败: {data.get('error', '未知错误')}")
            raise typer.Exit(1)
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


@app.command("me-llm")
def cmd_me_llm() -> None:
    """查看当前账号正在使用的 LLM 配置 — 是你自己保存的 key，还是开发者共享 key。

    借鉴 hermes-agent：每个用户可以保存自己的 LLM 配置。
    所有 agent team 协作都优先用你保存的 key（不再走开发者共享 key）。
    """
    cfg = get_config()
    if not cfg.api_token:
        error("未登录，请先 sakura login")
        raise typer.Exit(1)
    import httpx

    url = f"{cfg.api_url.rstrip('/')}/api/v1/me/llm-config"
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {cfg.api_token}"}, timeout=15)
        r.raise_for_status()
        data = r.json().get("data", {})
        if data.get("has_user_config"):
            c = data["config"]
            success("你的对话正在使用你自己保存的 LLM 配置 ↓")
            info(f"  名称:     {c.get('display_name')}")
            info(f"  提供商:   {c.get('provider_id')}")
            info(f"  模型:     {c.get('model')}")
            info(f"  Base URL: {c.get('base_url')}")
            info(f"  已保存 key: {c.get('has_api_key')}")
            if c.get("is_default"):
                info("  (默认配置)")
        else:
            error("你还没有保存任何 LLM 配置 — 当前用开发者共享 key")
            info(data.get("message", ""))
            info("用 sakura llm-save 添加你的 key（你的 key 你做主）。")
    except httpx.ConnectError as e:
        error(f"无法连接后端 {cfg.api_url}: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error(str(e))
        raise typer.Exit(1) from None


# ============================================================
# doctor
# ============================================================


@app.command("doctor")
def cmd_doctor() -> None:
    """诊断：API 连通性 / 健康检查 / 配置。"""
    cfg = get_config()
    info(f"API URL: {cfg.api_url}")
    info(f"配置文件: {CONFIG_FILE} ({'存在' if CONFIG_FILE.exists() else '未生成'})")
    with _client() as c:
        try:
            h = c.health()
            success(f"后端健康: {h}")
        except SakuraAPIError as e:
            error(f"后端不可达: {e}")
            raise typer.Exit(1) from None


# ============================================================
# version
# ============================================================


@app.command("version")
def cmd_version() -> None:
    """打印 CLI 版本。"""
    print(f"sakura {__version__}")


# ============================================================
# repl — 交互式 REPL（Claude Code 风格）
# ============================================================


@app.command("repl")
def cmd_repl() -> None:
    """启动交互式 REPL — 像 Claude Code 一样交互。

    支持：
    - 直接输入需求 → 7 Agent 协作生成全栈代码
    - /task /status /tokens /agents /skills /mcp /artifacts /env /help /exit
    - @agent_name 直接和特定 agent 对话
    - #team_id 切换团队
    - !command 执行 shell 命令
    - 实时 Agent 状态 + Token 监视
    - MCP 工具调用 + Skill 调用
    """
    import asyncio

    from cli.repl import run_repl

    run_repl()


# ============================================================
# main — 入口函数（供 pyproject.toml console_scripts 使用）
# ============================================================


def main() -> None:
    """CLI 入口函数。"""
    app()


if __name__ == "__main__":
    app()
