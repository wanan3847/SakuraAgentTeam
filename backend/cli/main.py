"""Sakura CLI 主入口 — typer 应用。

子命令：
  config                 配置 API URL / token / 默认工作流
  task <requirement>     提交新任务（自动启动工作流）
  sessions               列出所有会话
  status <id>            查看会话详情
  logs <id>              跟踪会话事件流（SSE）
  artifacts <id>         列出产物
  cancel <id>            取消会话
  projects               列出项目
  doctor                 诊断连接 / 健康检查
  version                打印版本
"""

from __future__ import annotations

import json
import sys
import time

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


# ============================================================
# config
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
    cfg.save()
    success(f"配置已保存到 {CONFIG_FILE}")
    emit(cfg.to_dict())


@config_app.command("path")
def config_path() -> None:
    """打印配置文件路径。"""
    # 通过模块属性访问以支持 monkeypatch（直接 import 是引用快照）
    import cli.config as _cfg_mod

    print(_cfg_mod.CONFIG_FILE)


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


if __name__ == "__main__":
    app()
