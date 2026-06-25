"""Interactive REPL for SakuraAgentTeam — Claude Code style.

Features:
- Real-time agent status display (rich.Live)
- Token usage monitoring (per-agent + session total)
- MCP tool listing and calling
- Skill invocation
- Artifact browsing
- Command system: /task /status /tokens /agents /skills /mcp /artifacts /help /exit
- Readline tab completion for /commands and /skill names

Usage:
    python -m cli repl
    sakura repl
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.layout import Layout
    from rich.align import Align
    from rich import box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Readline for tab completion + history
try:
    import readline

    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

from app.core.logging import get_logger

logger = get_logger(__name__)

# Agent display info
AGENT_INFO = {
    "requirements": ("📋", "需求分析"),
    "design": ("🎨", "架构设计"),
    "frontend": ("⚛️", "前端开发"),
    "backend": ("⚙️", "后端开发"),
    "testing": ("🧪", "测试生成"),
    "review": ("🔍", "代码审查"),
    "deployment": ("📦", "部署配置"),
}

# Status colors
STATUS_STYLE = {
    "pending": "dim",
    "running": "bold yellow",
    "completed": "bold green",
    "failed": "bold red",
    "skipped": "dim cyan",
}


class SakuraREPL:
    """Interactive REPL session."""

    # 完整命令清单（仿 Hermes 的 CommandDef）
    # 格式: (name, description, category, aliases, args_hint)
    COMMAND_DEFS: list[tuple[str, str, str, tuple, str]] = [
        # === Task / 任务执行 ===
        ("/task", "提交全栈开发任务（7 Agent 协作）", "Task", ("/build", "/do"), "<需求>"),
        ("/ask", "问 LLM 一个问题（不走 agent pipeline）", "Task", ("/chat",), "<问题>"),

        # === Session / 会话管理 ===
        ("/status", "显示当前 session 的 Agent 状态", "Session", (), ""),
        ("/tokens", "显示 token 使用统计（per-agent + 总计）", "Session", ("/cost",), ""),
        ("/agents", "列出所有 Agent 角色", "Session", (), ""),
        ("/team", "查看 Agent 间通信消息（团队协作）", "Session", (), ""),
        ("/logs", "查看 Agent 日志流", "Session", (), "[N]"),
        ("/session", "显示或重置当前 session ID", "Session", ("/sid",), "[new]"),
        ("/clear", "清屏", "Session", ("/cls",), ""),
        ("/history", "显示 REPL 历史", "Session", (), "[N]"),

        # === Skills / 能力 ===
        ("/skills", "列出所有可用 Skill", "Skills", (), ""),
        ("/skill", "调用指定 Skill", "Skills", ("/s",), "<name> [args]"),
        ("/mcp", "列出 MCP server 和工具（无参数时）/ 调用 MCP 工具（有参数时）", "Skills", ("/m",), "[call <server> <tool> [args]]"),

        # === Files / 文件操作 ===
        ("/file", "读文件内容（问文件在哪里不按流程）", "Files", ("/cat", "/read"), "<path>"),
        ("/find", "在工作目录中查找文件", "Files", ("/search",), "<pattern>"),
        ("/ls", "列出当前工作目录", "Files", ("/dir",), "[path]"),
        ("/pwd", "显示当前工作目录", "Files", ("/cwd",), ""),

        # === Artifacts / 产物 ===
        ("/artifacts", "查看所有生成的产物", "Artifacts", ("/arts",), ""),
        ("/artifact", "查看指定产物内容", "Artifacts", ("/art",), "<name|#>"),

        # === Config / 配置 ===
        ("/env", "查看当前 LLM/环境配置", "Config", (), ""),
        ("/model", "查看或切换 LLM 模型", "Config", (), "[model-name]"),
        ("/reload", "重新加载 .env 配置 + skill 目录", "Config", (), ""),

        # === Meta ===
        ("/commands", "列出所有命令（按分类）", "Meta", ("/cmds", "/?"), ""),
        ("/help", "显示简短帮助", "Meta", (), ""),
        ("/exit", "退出 REPL", "Meta", ("/quit", "/q", "/bye"), ""),

        # === Quick shortcuts ===
        ("@<agent>", "直接和特定 agent 对话", "Quick", (), "<agent_name> <消息>"),
        ("#<team_id>", "切换默认团队", "Quick", (), "<team_id>"),
        ("!<command>", "执行 shell 命令", "Quick", (), "<command>"),
    ]

    @property
    def COMMANDS(self) -> list[str]:
        """所有命令的扁平列表（含别名），供补全用。"""
        names: list[str] = []
        seen: set[str] = set()
        for name, _desc, _cat, aliases, _args in self.COMMAND_DEFS:
            for n in (name, *aliases):
                if n not in seen:
                    seen.add(n)
                    names.append(n)
        return names

    def __init__(self):
        self.console = Console() if HAS_RICH else None
        self.session_id: str | None = None
        self.current_requirement: str | None = None
        self.agents_status: dict[str, str] = {}  # role -> status
        self.artifacts: list[dict] = []
        self.token_total = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "calls": 0}
        self.agent_tokens: dict[str, dict] = {}  # role -> {prompt, completion, total, cost}
        self.agent_logs: list[tuple[str, str, str]] = []  # (role, message, level)
        self.team_messages: list[dict] = []  # agent 间通信消息
        self._event_task: asyncio.Task | None = None
        self._running = False
        self._setup_readline()

    def _setup_readline(self) -> None:
        """配置 readline 补全 + 历史记录。"""
        if not HAS_READLINE:
            return

        # 历史文件
        histfile = os.path.expanduser("~/.sakura/repl_history")
        try:
            os.makedirs(os.path.dirname(histfile), exist_ok=True)
        except Exception:
            pass
        try:
            readline.read_history_file(histfile)
        except Exception:
            pass  # 文件不存在 / 权限问题 / 格式错误，都静默跳过
        try:
            readline.set_history_length(1000)
        except Exception:
            pass
        # 不在 __init__ 里 write，避免权限问题导致启动崩溃
        # 历史会在退出时写入

        # 补全函数
        def completer(text: str, state: int) -> str | None:
            try:
                line = readline.get_line_buffer()
            except Exception:
                line = text

            matches: list[str] = []

            # 构建命令名 → description 映射
            cmd_meta: dict[str, str] = {}
            for name, desc, _cat, aliases, args_hint in self.COMMAND_DEFS:
                full = f"{name} {args_hint}".strip() if args_hint else name
                cmd_meta[name] = desc
                for a in aliases:
                    cmd_meta[a] = desc

            if text.startswith("/"):
                # 匹配所有以 text 开头的命令
                base_matches = [cmd for cmd in cmd_meta if cmd.startswith(text)]
            elif line.startswith("/skill ") and text:
                try:
                    from app.foundation.skills import skill_registry
                    skills = skill_registry.list_skills()
                    base_matches = [s["name"] for s in skills if s["name"].startswith(text)]
                    cmd_meta = {s: s for s in base_matches}  # skill 自身就是描述
                except Exception:
                    base_matches = []
            elif line.startswith("/mcp call ") and text:
                try:
                    from app.foundation.mcp import load_mcp_config
                    configs = load_mcp_config()
                    base_matches = [name for name in configs if name.startswith(text)]
                    cmd_meta = {n: n for n in base_matches}
                except Exception:
                    base_matches = []
            elif line.startswith("/artifact ") and text:
                base_matches = [a.get("name", "") for a in self.artifacts if a.get("name", "").startswith(text)]
                cmd_meta = {n: n for n in base_matches}
            else:
                base_matches = []

            # 返回 "cmd\tdescription" 格式，让 readline 在 tab 时显示描述
            if state == 0:
                self._completer_matches = []
                for cmd in base_matches:
                    desc = cmd_meta.get(cmd, "")
                    # 用 \t 分隔，readline 启用 set completion-map-case 后会显示
                    self._completer_matches.append(f"{cmd}\t{desc}")
                matches = self._completer_matches

            if state < len(matches):
                return matches[state]
            return None

        try:
            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("set show-all-if-ambiguous on")
            readline.parse_and_bind("set show-all-if-unmodified on")
            readline.set_completer_delims(" \t\n")
        except Exception:
            pass  # readline 绑定失败不阻止 REPL 启动

    def _print(self, msg: str, style: str = "") -> None:
        if self.console:
            self.console.print(msg, style=style)
        else:
            print(msg)

    def _banner(self) -> None:
        # 启动时加载 markdown skills
        try:
            from app.foundation.skills import load_markdown_skills
            count = load_markdown_skills()
            if count > 0:
                logger.info("markdown_skills_loaded_at_startup", count=count)
        except Exception as e:
            logger.warning("markdown_skills_load_failed", error=str(e))

        if not HAS_RICH:
            print("SakuraAgentTeam Interactive REPL")
            return
        banner = Text()
        banner.append("🌸 SakuraAgentTeam", style="bold magenta")
        banner.append(" Interactive REPL", style="bold")
        banner.append("\n多智能体全栈开发系统 · 像 Claude Code 一样交互", style="dim")
        # 统计 skill 数
        try:
            from app.foundation.skills import skill_registry
            skill_count = len(skill_registry.list_skills())
            banner.append(f"\n🎯 {skill_count} 个 Skill 可用 · Tab 键补全 · 输入 /help 查看命令", style="cyan")
        except Exception:
            banner.append("\n输入 /help 查看命令 · 输入需求直接生成全栈代码", style="cyan")
        self.console.print(Panel(banner, border_style="magenta", box=box.ROUNDED))

    def _help(self) -> None:
        commands = Table(title="可用命令", show_header=True, header_style="bold cyan", box=box.ROUNDED)
        commands.add_column("命令", style="bold")
        commands.add_column("说明")
        commands.add_row("/task <需求>", "提交全栈开发任务，7 Agent 协作生成代码")
        commands.add_row("/status", "查看当前 session 的 Agent 状态")
        commands.add_row("/tokens", "查看 token 使用统计（per-agent + 总计）")
        commands.add_row("/agents", "列出所有 Agent 角色")
        commands.add_row("/skills", "列出可用 Skill")
        commands.add_row("/skill <name> [args]", "调用 Skill")
        commands.add_row("/mcp", "列出 MCP server 和工具")
        commands.add_row("/mcp call <server> <tool> [args]", "调用 MCP 工具")
        commands.add_row("/artifacts", "查看生成的产物文件")
        commands.add_row("/artifact <name>", "查看指定产物内容")
        commands.add_row("/team", "查看 Agent 间通信消息（团队协作）")
        commands.add_row("/logs", "查看 Agent 日志流")
        commands.add_row("/env", "查看当前 LLM 配置")
        commands.add_row("/help", "显示此帮助")
        commands.add_row("/exit", "退出 REPL")
        commands.add_row("", "")
        commands.add_row("<直接输入需求>", "等同于 /task <需求>")
        commands.add_row("", "")
        commands.add_row("[dim]💡 Tab 键补全命令和 skill 名[/]", "")
        if self.console:
            self.console.print(commands)
        else:
            print(commands)

    def _show_commands(self) -> None:
        """按分类显示所有命令（仿 Hermes 的 /commands）。"""
        from collections import defaultdict

        groups: dict[str, list[tuple[str, str, tuple, str]]] = defaultdict(list)
        for name, desc, cat, aliases, args in self.COMMAND_DEFS:
            groups[cat].append((name, desc, aliases, args))

        if HAS_RICH:
            for cat, items in groups.items():
                t = Table(title=f"📂 {cat}", show_header=True, header_style="bold cyan", box=box.ROUNDED)
                t.add_column("命令", style="bold", no_wrap=True)
                t.add_column("说明")
                t.add_column("别名", style="dim")
                for name, desc, aliases, args_hint in items:
                    full_cmd = f"{name} {args_hint}".strip() if args_hint else name
                    alias_str = ", ".join(aliases) if aliases else ""
                    t.add_row(full_cmd, desc, alias_str)
                self.console.print(t)
        else:
            for cat, items in groups.items():
                self._print(f"\n📂 {cat}")
                for name, desc, aliases, args_hint in items:
                    full_cmd = f"{name} {args_hint}".strip() if args_hint else name
                    alias_str = f"  (别名: {', '.join(aliases)})" if aliases else ""
                    self._print(f"  {full_cmd:30s}  {desc}{alias_str}")

    def _do_clear(self) -> None:
        """清屏。"""
        os.system("clear" if os.name == "posix" else "cls")

    def _show_history(self, n: int = 20) -> None:
        """显示 REPL 历史。"""
        if not HAS_READLINE:
            self._print("⚠️  readline 不可用", "yellow")
            return
        try:
            length = readline.get_current_history_length()
            self._print(f"📜 历史 (最近 {min(n, length)} 条 / 共 {length} 条):", "cyan")
            start = max(1, length - n + 1)
            for i in range(start, length + 1):
                item = readline.get_history_item(i)
                if item:
                    self._print(f"  {i:4d}  {item}")
        except Exception as exc:
            self._print(f"⚠️  无法读取历史: {exc}", "yellow")

    def _do_session(self, args: str) -> None:
        """显示或重置 session ID。"""
        if args:
            self.session_id = args.strip()
            self._print(f"✅ Session ID 已设为: {self.session_id}", "green")
        else:
            if self.session_id:
                self._print(f"📋 当前 Session ID: {self.session_id}", "cyan")
                self._print(f"   用 /session <new-id> 重置", "dim")
            else:
                self._print("📋 当前无 Session（任务执行时自动生成）", "dim")

    def _do_pwd(self) -> None:
        self._print(f"📁 {os.getcwd()}", "cyan")

    def _do_ls(self, path: str = "") -> None:
        target = path.strip() or "."
        try:
            entries = sorted(os.listdir(target))
            if HAS_RICH:
                t = Table(title=f"📁 {os.path.abspath(target)}", show_header=True, header_style="bold cyan", box=box.ROUNDED)
                t.add_column("名称")
                t.add_column("类型")
                t.add_column("大小", justify="right")
                for e in entries:
                    full = os.path.join(target, e)
                    is_dir = os.path.isdir(full)
                    try:
                        size = "" if is_dir else f"{os.path.getsize(full)} B"
                    except OSError:
                        size = "?"
                    t.add_row(e, "📁 目录" if is_dir else "📄 文件", size)
                self.console.print(t)
            else:
                self._print(f"📁 {os.path.abspath(target)}:")
                for e in entries:
                    print(f"  {e}")
        except Exception as exc:
            self._print(f"⚠️  无法列出 {target}: {exc}", "yellow")

    def _do_find(self, pattern: str) -> None:
        """在工作目录中按名字找文件（排除 .venv / __pycache__ / .git 等）。"""
        if not pattern.strip():
            self._print("用法: /find <pattern>   如 /find repl.py", "yellow")
            return
        from pathlib import Path
        root = Path(".")
        # 排除目录
        EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", ".pytest_cache", "node_modules", ".mypy_cache", ".ruff_cache", "site-packages"}
        matches = []
        for p in root.rglob(f"*{pattern}*"):
            try:
                if p.is_file():
                    # 检查路径中是否含排除目录
                    parts = set(p.parts)
                    if parts & EXCLUDE_DIRS:
                        continue
                    matches.append(p)
            except OSError:
                continue
        if not matches:
            self._print(f"⚠️  没找到匹配 *{pattern}* 的文件（已排除 .venv / __pycache__ / .git）", "yellow")
            return
        matches = matches[:50]
        if HAS_RICH:
            t = Table(title=f"🔍 找到 {len(matches)} 个文件 (匹配 *{pattern}*)", show_header=True, header_style="bold cyan", box=box.ROUNDED)
            t.add_column("路径")
            t.add_column("大小", justify="right")
            for p in matches:
                try:
                    t.add_row(str(p), f"{p.stat().st_size} B")
                except OSError:
                    t.add_row(str(p), "?")
            self.console.print(t)
        else:
            for p in matches:
                print(f"  {p}")

    def _do_file(self, path: str) -> None:
        """读文件内容。"""
        path = path.strip()
        if not path:
            self._print("用法: /file <path>   如 /file cli/repl.py", "yellow")
            return
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            self._print(f"⚠️  找不到文件: {path}", "yellow")
            # 给出建议
            matches = list(Path(".").rglob(f"*{Path(path).name}*"))[:3]
            if matches:
                self._print("💡 可能是你想找的:", "cyan")
                for m in matches:
                    self._print(f"   - {m}")
            return
        if not p.is_file():
            self._print(f"⚠️  这是一个目录: {path}  (用 /ls {path} 看内容)", "yellow")
            return
        try:
            content = p.read_text(encoding="utf-8")
            size = p.stat().st_size
            self._print(f"📄 {p.absolute()}  ({size} B, {len(content.splitlines())} 行)\n", "cyan")
            # 输出前 200 行避免刷屏
            lines = content.splitlines()
            max_lines = 200
            for line in lines[:max_lines]:
                self._print(line)
            if len(lines) > max_lines:
                self._print(f"\n... 省略 {len(lines) - max_lines} 行 ({len(content)} 字符) ...", "dim")
        except UnicodeDecodeError:
            self._print(f"⚠️  {path} 不是文本文件", "yellow")
        except Exception as exc:
            self._print(f"⚠️  读文件失败: {exc}", "yellow")

    async def _do_model(self, args: str) -> None:
        """查看或切换模型。"""
        if not args:
            from app.core.config import settings
            self._print(f"当前模型: {settings.default_llm_model}", "cyan")
            self._print("用 /model <model-name> 切换（本次 session 生效）", "dim")
            return
        new_model = args.strip()
        try:
            from app.core.config import settings
            settings.default_llm_model = new_model
            # 重建 provider
            from app.agents import _build_llm_provider
            provider = _build_llm_provider()
            if provider:
                self._print(f"✅ 已切换到 {new_model}", "green")
            else:
                self._print(f"⚠️  模型设为 {new_model} 但 provider 构建失败", "yellow")
        except Exception as exc:
            self._print(f"⚠️  切换失败: {exc}", "yellow")

    async def _do_reload(self) -> None:
        """重新加载 .env + skill 目录。"""
        try:
            from app.core.config import settings
            # 重新读 .env
            import os
            from pathlib import Path
            env_path = Path(__file__).parent.parent / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        os.environ[k] = v
                        # 同步到 settings
                        field_name = k.lower()
                        if hasattr(settings, field_name):
                            setattr(settings, field_name, v)
            # 重载 skill
            from app.foundation.skills import load_markdown_skills
            from app.foundation.skills.base import skill_registry
            n = load_markdown_skills()
            self._print(f"✅ 已重载: .env + {n} 个 markdown skill (总 {len(skill_registry.list_skills())} 个)", "green")
        except Exception as exc:
            self._print(f"⚠️  重载失败: {exc}", "yellow")

    async def _chat_with_agent(self, agent_name: str, message: str) -> None:
        """直接和特定 agent 对话（@agent_name message）。

        走 /ask 的 fast-path，但在 system prompt 里指定 agent 角色。
        """
        if not message:
            self._print(f"用法: @{agent_name} <消息>   直接和 {agent_name} 对话", "yellow")
            return

        # 尝试从注册表找 agent 定义，构造角色 system prompt
        agent_desc = ""
        try:
            from app.agents.registry import AGENT_MAP
            agent = AGENT_MAP.get(agent_name)
            if agent:
                agent_desc = f"\n你现在的角色是 {agent.name}（{agent.role}）。\n目标: {agent.goal}\n背景: {agent.backstory}\n"
            else:
                self._print(f"⚠️  未找到 agent '{agent_name}'，将用默认助手回答", "yellow")
        except Exception:
            pass

        from app.agents import _build_llm_provider
        from app.agents.types import Context
        import uuid

        provider = _build_llm_provider()
        if not provider:
            self._print("⚠️  没配 LLM key，无法和 agent 对话", "yellow")
            return

        from app.agents import create_all_agents
        agents = create_all_agents(provider)
        req = agents["requirements"]

        ctx = Context(
            session_id=self.session_id or f"agent_{agent_name}_{uuid.uuid4().hex[:8]}",
            project_id="agent_chat",
            user_requirement=message,
        )

        system_prompt = (
            f"你是 SakuraAgentTeam 的 agent。{agent_desc}"
            "直接、简洁地回答用户问题。回答用中文。"
        )

        self._print(f"💬 @{agent_name}:", "cyan")
        try:
            response = await req.run_agentic_loop(
                prompt=message,
                ctx=ctx,
                system_prompt=system_prompt,
                max_iterations=8,
            )
            self._print(response)
        except Exception as exc:
            self._print(f"⚠️  调用失败: {exc}", "red")

    def _switch_team(self, team_id: str) -> None:
        """切换默认团队（#team_id）。"""
        team_id = team_id.strip()
        if not team_id:
            # 显示当前团队
            try:
                from cli.config import get_config
                cfg = get_config()
                current = cfg.default_team or "(未设置)"
                self._print(f"📋 当前默认团队: {current}", "cyan")
                self._print("用 #<team_id> 切换", "dim")
            except Exception:
                self._print("📋 用 #<team_id> 切换默认团队", "cyan")
            return

        try:
            from cli.config import get_config
            cfg = get_config()
            cfg.default_team = team_id
            cfg.save()
            self._print(f"✅ 默认团队已切换为: {team_id}", "green")
        except Exception as exc:
            self._print(f"⚠️  切换团队失败: {exc}", "yellow")

    def _exec_shell(self, command: str) -> None:
        """执行 shell 命令（!command）。"""
        command = command.strip()
        if not command:
            self._print("用法: !<command>   执行 shell 命令", "yellow")
            return
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                self._print(result.stdout, "dim")
            if result.stderr:
                self._print(result.stderr, "yellow")
            self._print(f"[exit code: {result.returncode}]", "dim")
        except subprocess.TimeoutExpired:
            self._print("⚠️  命令超时（30s）", "yellow")
        except Exception as exc:
            self._print(f"⚠️  执行失败: {exc}", "red")

    async def _ask_llm(self, question: str) -> None:
        """Fast-path: 直接调 LLM 回答问题，不走 agent pipeline。

        问文件在哪里、改一行代码、解释一段代码 → 都走这里。
        完整任务用 /task。

        智能上下文：
        - 检测到"文件在哪里"/"where is"类问题 → 先搜文件，把结果喂给 LLM
        - 检测到"解释"/"explain"类问题 + 文件名 → 先读文件，把内容喂给 LLM
        """
        from app.agents import _build_llm_provider
        from app.agents.types import Context, Plan
        from pathlib import Path
        import re

        provider = _build_llm_provider()
        if not provider:
            self._print("⚠️  没配 LLM key，直接回显你的输入（无 LLM）:", "yellow")
            self._print(f"   {question}", "dim")
            return

        # 复用 requirements agent 的 llm_chat 路径
        from app.agents import create_all_agents
        agents = create_all_agents(provider)
        req = agents["requirements"]

        ctx = Context(
            session_id=self.session_id or "ask_" + str(uuid.uuid4())[:8],
            project_id="ask",
            user_requirement=question,
        )

        # 智能上下文收集
        context_hint = ""
        q_lower = question.lower()

        # 检测"文件在哪里"类问题
        file_location_patterns = [
            r"文件在哪里", r"文件在哪", r"哪个文件", r"在哪.*文件",
            r"where is.*file", r"find.*file", r"which file",
        ]
        is_location_q = any(re.search(p, q_lower) for p in file_location_patterns)

        # 检测"解释/看"类问题 + 提取文件名
        explain_patterns = [r"解释", r"explain", r"看一下", r"看看", r"读一下", r"show"]
        is_explain_q = any(re.search(p, q_lower) for p in explain_patterns)

        # 提取可能的文件名（xxx.py / xxx.ts / xxx.md 等）
        file_candidates = re.findall(r"[\w/]+\.\w{1,5}", question)

        if is_location_q and file_candidates:
            # 搜文件
            fname = Path(file_candidates[0]).name
            self._print(f"🔍 先搜文件: {fname}", "dim")
            EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", ".pytest_cache", "node_modules", "site-packages"}
            matches = []
            for p in Path(".").rglob(f"*{fname}*"):
                try:
                    if p.is_file() and not (set(p.parts) & EXCLUDE_DIRS):
                        matches.append(str(p))
                except OSError:
                    continue
            if matches:
                context_hint = f"\n\n## 文件搜索结果（在工作目录中找到）\n" + "\n".join(f"- {m}" for m in matches[:20])
                self._print(f"   找到 {len(matches)} 个匹配", "dim")
            else:
                context_hint = f"\n\n## 文件搜索结果\n未找到匹配 *{fname}* 的文件。"
                self._print(f"   未找到", "dim")
        elif is_explain_q and file_candidates:
            # 读文件
            fpath = file_candidates[0]
            try:
                p = Path(fpath)
                if p.exists() and p.is_file():
                    content = p.read_text(encoding="utf-8")
                    # 截断到 4000 字符避免 token 爆炸
                    if len(content) > 4000:
                        content = content[:4000] + f"\n... (截断，共 {len(content)} 字符)"
                    context_hint = f"\n\n## 文件内容: {fpath}\n```\n{content}\n```"
                    self._print(f"📄 已读文件: {fpath}", "dim")
            except Exception:
                pass

        # 构造 prompt
        full_prompt = question + context_hint if context_hint else question

        system_prompt = (
            "你是 SakuraAgentTeam 的助手。直接、简洁地回答用户问题。"
            "如果提供了文件搜索结果或文件内容，基于这些信息回答。"
            "不要问澄清问题。回答用中文。"
        )

        self._print(f"💭 问: {question}", "cyan")
        try:
            # Real-time progress callbacks (Claude Code style)
            def _on_iteration(it: int, msg_count: int) -> None:
                self._print(f"  🔄 迭代 {it} (消息 {msg_count})", "dim")

            def _on_tool_call(name: str, args: str) -> None:
                self._print(f"  🔧 调用工具: {name}({args[:100]}...)", "yellow")

            def _on_tool_result(name: str, success: bool, preview: str) -> None:
                icon = "✅" if success else "❌"
                # Show first line of result only
                first_line = preview.split("\n")[0][:120] if preview else ""
                self._print(f"  {icon} {name}: {first_line}", "dim")

            def _on_llm_response(content: str, has_tool_calls: bool) -> None:
                if has_tool_calls:
                    # LLM is thinking / requesting tools
                    if content:
                        self._print(f"  💭 {content[:150]}...", "dim")
                # If no tool calls, the final answer will be printed below

            # Use the agentic loop so the LLM can call file_read/glob/grep
            # to inspect the codebase when answering. If no tools are needed,
            # the loop exits after one iteration with a direct answer.
            response = await req.run_agentic_loop(
                prompt=full_prompt,
                ctx=ctx,
                system_prompt=system_prompt,
                max_iterations=8,
                on_iteration=_on_iteration,
                on_tool_call=_on_tool_call,
                on_tool_result=_on_tool_result,
                on_llm_response=_on_llm_response,
            )
            self._print("\n💬 答:", "green")
            self._print(response)
            # token 累加
            try:
                session_usage = provider.get_session_usage(ctx.session_id)
                t = session_usage.total_tokens
                c = session_usage.total_cost_usd
                self._print(f"\n📊 本次: {t} tokens, ${c:.6f}", "dim")
            except Exception:
                pass
        except Exception as exc:
            self._print(f"⚠️  LLM 调用失败: {type(exc).__name__}: {exc}", "red")

    def _show_env(self) -> None:
        try:
            from app.core.config import settings
            api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
            api_base = settings.openai_api_base or os.environ.get("OPENAI_API_BASE", "")
            model = settings.default_llm_model or os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o")
        except Exception:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            api_base = os.environ.get("OPENAI_API_BASE", "")
            model = os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o")
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else ("***" if api_key else "未配置")
        if HAS_RICH:
            t = Table(title="LLM 配置", show_header=True, header_style="bold cyan", box=box.ROUNDED)
            t.add_column("配置项")
            t.add_column("值")
            t.add_row("API Key", masked)
            t.add_row("API Base", api_base or "默认")
            t.add_row("Model", model)
            t.add_row("LLM 模式", "✅ 真 LLM" if api_key and "your-" not in api_key else "⚠️ 模板模式（无 key）")
            self.console.print(t)
        else:
            print(f"API Key: {masked}")
            print(f"API Base: {api_base}")
            print(f"Model: {model}")

    def _show_agents(self) -> None:
        if HAS_RICH:
            t = Table(title="Agent 角色", show_header=True, header_style="bold cyan", box=box.ROUNDED)
            t.add_column("角色")
            t.add_column("图标")
            t.add_column("说明")
            for role, (icon, desc) in AGENT_INFO.items():
                t.add_row(role, icon, desc)
            self.console.print(t)
        else:
            for role, (icon, desc) in AGENT_INFO.items():
                print(f"  {icon} {role}: {desc}")

    def _show_status(self) -> None:
        if not self.session_id:
            self._print("⚠️  当前没有活跃的 session，用 /task <需求> 创建", "yellow")
            return
        if HAS_RICH:
            t = Table(
                title=f"Session {self.session_id} — Agent 状态",
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED,
            )
            t.add_column("图标")
            t.add_column("Agent")
            t.add_column("状态")
            t.add_column("Tokens")
            for role, (icon, desc) in AGENT_INFO.items():
                status = self.agents_status.get(role, "pending")
                style = STATUS_STYLE.get(status, "")
                tokens = self.agent_tokens.get(role, {})
                tok_str = ""
                if tokens:
                    tok_str = f"{tokens.get('total', 0)} (${tokens.get('cost', 0):.4f})"
                t.add_row(icon, f"{role} ({desc})", Text(status, style=style), tok_str)
            self.console.print(t)
        else:
            for role, (icon, desc) in AGENT_INFO.items():
                status = self.agents_status.get(role, "pending")
                print(f"  {icon} {role}: {status}")

    def _show_tokens(self) -> None:
        if not self.token_total["calls"]:
            self._print("⚠️  还没有 LLM 调用记录", "yellow")
            return
        if HAS_RICH:
            t = Table(
                title="Token 使用统计",
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED,
            )
            t.add_column("维度")
            t.add_column("Prompt", justify="right")
            t.add_column("Completion", justify="right")
            t.add_column("Total", justify="right")
            t.add_column("Cost (USD)", justify="right")
            t.add_column("Calls", justify="right")

            # Per-agent
            for role, tokens in sorted(self.agent_tokens.items()):
                t.add_row(
                    role,
                    str(tokens.get("prompt", 0)),
                    str(tokens.get("completion", 0)),
                    str(tokens.get("total", 0)),
                    f"${tokens.get('cost', 0):.6f}",
                    str(tokens.get("calls", 0)),
                )

            # Total
            t.add_section()
            t.add_row(
                "[bold]总计[/]",
                f"[bold]{self.token_total['prompt']}[/]",
                f"[bold]{self.token_total['completion']}[/]",
                f"[bold]{self.token_total['total']}[/]",
                f"[bold]${self.token_total['cost']:.6f}[/]",
                f"[bold]{self.token_total['calls']}[/]",
            )
            self.console.print(t)
        else:
            print(f"总计: {self.token_total['total']} tokens, ${self.token_total['cost']:.6f}, {self.token_total['calls']} calls")
            for role, tokens in self.agent_tokens.items():
                print(f"  {role}: {tokens.get('total', 0)} tokens")

    def _show_artifacts(self) -> None:
        if not self.artifacts:
            self._print("⚠️  还没有生成产物", "yellow")
            return
        if HAS_RICH:
            t = Table(
                title=f"产物列表 ({len(self.artifacts)} 个)",
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED,
            )
            t.add_column("#")
            t.add_column("Agent")
            t.add_column("名称")
            t.add_column("类型")
            t.add_column("文件数")
            for i, art in enumerate(self.artifacts):
                files = art.get("metadata", {}).get("files", [])
                t.add_row(str(i + 1), art.get("agent_role", ""), art.get("name", ""),
                          art.get("artifact_type", ""), str(len(files) if isinstance(files, list) else 0))
            self.console.print(t)
        else:
            for i, art in enumerate(self.artifacts):
                print(f"  {i+1}. [{art.get('agent_role')}] {art.get('name')}")

    def _show_artifact(self, name_or_idx: str) -> None:
        if not self.artifacts:
            self._print("⚠️  还没有生成产物", "yellow")
            return
        art = None
        try:
            idx = int(name_or_idx) - 1
            if 0 <= idx < len(self.artifacts):
                art = self.artifacts[idx]
        except ValueError:
            for a in self.artifacts:
                if name_or_idx in a.get("name", ""):
                    art = a
                    break
        if not art:
            self._print(f"⚠️  找不到产物: {name_or_idx}", "yellow")
            return

        files = art.get("metadata", {}).get("files", [])
        if isinstance(files, list) and files:
            for f in files:
                if isinstance(f, dict) and "path" in f:
                    path = f["path"]
                    content = f.get("content", "")
                    lines = content.count("\n") + 1
                    size = len(content)
                    self._print(f"\n📄 {path} ({lines} 行, {size} 字节)", "cyan")
                    # Show first 80 lines
                    content_lines = content.split("\n")
                    for line in content_lines[:80]:
                        print(f"  {line}")
                    if len(content_lines) > 80:
                        self._print(f"  ... ({len(content_lines) - 80} more lines)", "dim")
        else:
            content = art.get("content", "")
            self._print(content[:5000], "cyan")

    async def _show_skills(self) -> None:
        try:
            from app.foundation.skills import skill_registry

            skills = skill_registry.list_skills()
            if HAS_RICH:
                t = Table(title="可用 Skill", show_header=True, header_style="bold cyan", box=box.ROUNDED)
                t.add_column("名称")
                t.add_column("说明")
                t.add_column("标签")
                for s in skills:
                    t.add_row(s["name"], s["description"], ", ".join(s.get("tags", [])))
                self.console.print(t)
            else:
                for s in skills:
                    print(f"  {s['name']}: {s['description']}")
        except Exception as e:
            self._print(f"⚠️  Skill 系统不可用: {e}", "red")

    async def _call_skill(self, args_str: str) -> None:
        parts = args_str.split(maxsplit=1)
        if not parts:
            self._print("用法: /skill <name> [JSON args]", "yellow")
            return
        name = parts[0]
        skill_args = {}
        if len(parts) > 1:
            try:
                skill_args = json.loads(parts[1])
            except json.JSONDecodeError:
                skill_args = {"input": parts[1]}

        try:
            from app.foundation.skills import skill_registry, SkillContext

            ctx = SkillContext(
                session_id=self.session_id or "repl",
                project_id="repl-project",
                workdir=os.getcwd(),
                metadata={},
            )
            self._print(f"⏳ 调用 Skill: {name}...", "cyan")
            result = await skill_registry.call(name, skill_args, ctx)
            if result.success:
                self._print(f"✅ Skill {name} 执行成功", "green")
                self._print(result.output[:3000], "cyan")
                if result.data:
                    self._print(f"\n数据: {json.dumps(result.data, indent=2, ensure_ascii=False)[:1000]}", "dim")
            else:
                self._print(f"❌ Skill {name} 失败: {result.error}", "red")
        except Exception as e:
            self._print(f"⚠️  Skill 调用异常: {e}", "red")

    async def _show_mcp(self) -> None:
        try:
            from app.foundation.mcp import mcp_client, load_mcp_config

            configs = load_mcp_config()
            if not configs:
                self._print("⚠️  未配置 MCP server。编辑 ~/.sakura/mcp.json 添加", "yellow")
                self._print('格式: {"mcpServers": {"name": {"command": "...", "args": [...]}}}', "dim")
                return

            if HAS_RICH:
                t = Table(title="MCP Server 配置", show_header=True, header_style="bold cyan", box=box.ROUNDED)
                t.add_column("名称")
                t.add_column("命令")
                t.add_column("状态")
                for name, cfg in configs.items():
                    running = mcp_client.is_running(name)
                    status = "[green]运行中[/]" if running else "[dim]未启动[/]"
                    t.add_row(name, f"{cfg.command} {' '.join(cfg.args)}", status)
                self.console.print(t)
            else:
                for name, cfg in configs.items():
                    running = mcp_client.is_running(name)
                    print(f"  {name}: {cfg.command} {' '.join(cfg.args)} [{'running' if running else 'stopped'}]")

            # List tools from running servers
            tools = mcp_client.list_all_tools()
            if tools:
                self._print(f"\n🔧 可用工具 ({len(tools)} 个):", "cyan")
                for tool in tools:
                    self._print(f"  [{tool['server']}] {tool['name']}: {tool.get('description', '')[:80]}", "dim")
        except Exception as e:
            self._print(f"⚠️  MCP 系统不可用: {e}", "red")

    async def _mcp_call(self, args_str: str) -> None:
        parts = args_str.split(maxsplit=2)
        if len(parts) < 2:
            self._print("用法: /mcp call <server> <tool> [JSON args]", "yellow")
            return
        server_name = parts[0]
        tool_name = parts[1]
        arguments = {}
        if len(parts) > 2:
            try:
                arguments = json.loads(parts[2])
            except json.JSONDecodeError:
                arguments = {"input": parts[2]}

        try:
            from app.foundation.mcp import mcp_client, load_mcp_config

            if not mcp_client.is_running(server_name):
                configs = load_mcp_config()
                if server_name not in configs:
                    self._print(f"⚠️  未找到 MCP server: {server_name}", "red")
                    return
                self._print(f"⏳ 启动 {server_name}...", "cyan")
                ok = await mcp_client.start_server(server_name, configs[server_name])
                if not ok:
                    self._print(f"❌ 启动 {server_name} 失败", "red")
                    return

            self._print(f"⏳ 调用 {server_name}.{tool_name}...", "cyan")
            result = await mcp_client.call_tool(server_name, tool_name, arguments)
            self._print(f"✅ 结果:", "green")
            self._print(result[:3000], "cyan")
        except Exception as e:
            self._print(f"⚠️  MCP 调用异常: {e}", "red")

    async def _run_task(self, requirement: str) -> None:
        """Run a full multi-agent task with real-time display."""
        from app.agents import create_all_agents
        from app.agents.types import Context
        from app.orchestration.eventbus import Event, EventType, event_bus
        from app.orchestration.session import session_manager, SessionStatus
        from app.orchestration.workflows import FULL_GREENFIELD
        from app.orchestration.engine import WorkflowEngine

        self.session_id = uuid.uuid4().hex[:16]
        self.current_requirement = requirement
        self.agents_status = {role: "pending" for role in AGENT_INFO}
        self.artifacts = []
        self.token_total = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "calls": 0}
        self.agent_tokens = {}
        self.agent_logs = []
        self.team_messages = []
        self._running = True

        # Subscribe to events
        async def on_event(event: Event):
            payload = event.payload
            etype = event.event_type

            if etype == EventType.AGENT_STARTED.value:
                role = payload.get("agent_role", "")
                self.agents_status[role] = "running"
            elif etype == EventType.AGENT_COMPLETED.value:
                role = payload.get("agent_role", "")
                self.agents_status[role] = "completed"
            elif etype == EventType.AGENT_FAILED.value:
                role = payload.get("agent_role", "")
                self.agents_status[role] = "failed"
            elif etype == EventType.AGENT_LOG.value:
                role = payload.get("agent_role", "")
                msg = payload.get("message", "")
                level = payload.get("level", "info")
                self.agent_logs.append((role, msg, level))

                # Track token usage from LLM log events
                token_usage = payload.get("token_usage")
                if token_usage:
                    prompt_t = token_usage.get("prompt_tokens", 0)
                    completion_t = token_usage.get("completion_tokens", 0)
                    total_t = token_usage.get("total_tokens", prompt_t + completion_t)

                    # Get cost from meter
                    cost = 0.0
                    try:
                        from app.foundation.llm.meter import get_global_provider

                        provider = get_global_provider()
                        if provider and self.session_id:
                            session_usage = provider.get_session_usage(self.session_id)
                            cost = session_usage.total_cost_usd
                    except Exception:
                        pass

                    self.token_total["prompt"] += prompt_t
                    self.token_total["completion"] += completion_t
                    self.token_total["total"] += total_t
                    self.token_total["calls"] += 1
                    self.token_total["cost"] = cost

                    if role not in self.agent_tokens:
                        self.agent_tokens[role] = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "calls": 0}
                    self.agent_tokens[role]["prompt"] += prompt_t
                    self.agent_tokens[role]["completion"] += completion_t
                    self.agent_tokens[role]["total"] += total_t
                    self.agent_tokens[role]["calls"] += 1

                    # Update per-agent cost from session usage
                    try:
                        from app.foundation.llm.meter import get_global_provider

                        provider = get_global_provider()
                        if provider and self.session_id:
                            session_usage = provider.get_session_usage(self.session_id)
                            agent_data = session_usage.by_agent.get(role)
                            if agent_data:
                                self.agent_tokens[role]["cost"] = agent_data.get("cost_usd", 0.0)
                    except Exception:
                        pass

            elif etype == EventType.AGENT_COMPLETED.value:
                # 兜底：agent 完成时如果没收到 token_usage 事件，从 meter 读该 agent 的 token
                role = payload.get("agent_role", "")
                if role and (role not in self.agent_tokens or self.agent_tokens[role].get("total", 0) == 0):
                    try:
                        from app.foundation.llm.meter import get_global_provider

                        provider = get_global_provider()
                        if provider and self.session_id:
                            session_usage = provider.get_session_usage(self.session_id)
                            agent_data = session_usage.by_agent.get(role)
                            if agent_data and agent_data.get("total_tokens", 0) > 0:
                                prompt_t = agent_data.get("prompt_tokens", 0)
                                completion_t = agent_data.get("completion_tokens", 0)
                                total_t = agent_data.get("total_tokens", 0)
                                cost = agent_data.get("cost_usd", 0.0)
                                # 全局去重：检查是否已累加
                                already_total = self.agent_tokens.get(role, {}).get("total", 0)
                                if total_t > already_total:
                                    delta = total_t - already_total
                                    delta_p = max(0, prompt_t - self.agent_tokens.get(role, {}).get("prompt", 0))
                                    delta_c = max(0, completion_t - self.agent_tokens.get(role, {}).get("completion", 0))
                                    if role not in self.agent_tokens:
                                        self.agent_tokens[role] = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "calls": 0}
                                    self.agent_tokens[role]["prompt"] += delta_p
                                    self.agent_tokens[role]["completion"] += delta_c
                                    self.agent_tokens[role]["total"] += delta
                                    self.agent_tokens[role]["cost"] = cost
                                    self.agent_tokens[role]["calls"] += 1
                                    self.token_total["prompt"] += delta_p
                                    self.token_total["completion"] += delta_c
                                    self.token_total["total"] += delta
                                    self.token_total["cost"] = cost
                    except Exception:
                        pass

            elif etype == EventType.ARTIFACT_CREATED.value:
                role = payload.get("agent_role", "")
                name = payload.get("name", "")
                self._print(f"  📦 [{role}] 产物: {name}", "green")

        event_bus.subscribe_all(on_event)

        # Create session
        session = session_manager.create_session(
            requirement=requirement,
            project_id=f"repl-{self.session_id}",
        )
        self.session_id = session.id

        # Build agents with LLM
        agents = create_all_agents()

        # Set global provider for token tracking
        try:
            from app.foundation.llm.meter import get_global_provider, set_global_provider

            for agent in agents.values():
                if agent.llm:
                    set_global_provider(agent.llm)
                    break
        except Exception:
            pass

        # Build context
        projects_root = os.environ.get("PROJECTS_ROOT", "./data/projects")
        ctx = Context(
            session_id=self.session_id,
            project_id=f"repl-{self.session_id}",
            user_requirement=requirement,
            metadata={
                "projects_root": projects_root,
                "project_id": f"repl-{self.session_id}",
            },
        )

        # Create engine — 传 session_manager 和 event_bus
        engine = WorkflowEngine(agents)
        # 修复：用 SessionStatus 枚举而不是字符串
        await session_manager.update_status(self.session_id, SessionStatus.RUNNING)

        llm_mode = "真 LLM" if any(a.llm for a in agents.values()) else "模板模式（无 key）"
        self._print(f"\n🚀 启动任务: {requirement[:80]}", "bold cyan")
        self._print(f"📋 Session: {self.session_id}", "dim")
        self._print(f"🤖 模式: {llm_mode} · 7 Agent · DAG 工作流", "dim")
        self._print(f"📐 DAG: REQ → DESIGN → [FRONTEND ∥ BACKEND] → TESTING → REVIEW → DEPLOYMENT\n", "dim")

        # Run workflow in background
        async def run_workflow():
            try:
                await engine.run(
                    self.session_id,
                    requirement,
                    workflow=FULL_GREENFIELD,
                )
                # engine.run 内部已经更新了 session status，这里不重复
            except Exception as e:
                logger.error("repl_workflow_failed", error=str(e))
                await session_manager.set_error(self.session_id, str(e))
            finally:
                self._running = False

        # Start workflow
        wf_task = asyncio.create_task(run_workflow())

        # Monitor and display progress — 实时刷新
        last_render_time = 0
        try:
            while self._running or not wf_task.done():
                # 只在有变化时渲染
                now = asyncio.get_event_loop().time()
                if now - last_render_time >= 1.0:  # 每 1 秒刷新一次
                    self._render_live_status()
                    last_render_time = now
                await asyncio.sleep(0.3)
                if wf_task.done():
                    break
        except KeyboardInterrupt:
            self._print("\n⚠️  中断任务...", "yellow")
            wf_task.cancel()

        # Final status
        await asyncio.sleep(0.3)
        self._render_live_status(final=True)

        # Fetch artifacts
        session = session_manager.get_session(self.session_id)
        if session:
            for art in session.artifacts:
                self.artifacts.append(art.to_dict() if hasattr(art, "to_dict") else art)
            # 收集 team messages
            if session.context and hasattr(session.context, "team_messages"):
                for msg in session.context.team_messages:
                    self.team_messages.append({
                        "from": msg.from_role,
                        "to": msg.to_role,
                        "type": msg.message_type,
                        "content": msg.content[:200],
                    })

        # Summary
        self._print("\n" + "=" * 60, "bold magenta")
        self._print("📊 任务完成报告", "bold magenta")
        self._print("=" * 60, "bold magenta")
        self._show_status()
        self._print("")
        self._show_tokens()
        self._print("")
        self._show_artifacts()
        if self.team_messages:
            self._print("")
            self._show_team_messages()

        # Cleanup
        try:
            event_bus._wildcard_callbacks.remove(on_event)
        except ValueError:
            pass

    def _show_team_messages(self) -> None:
        """显示 Agent 间通信消息。"""
        if HAS_RICH:
            t = Table(
                title=f"Agent 团队通信 ({len(self.team_messages)} 条)",
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED,
            )
            t.add_column("发送者", width=12)
            t.add_column("接收者", width=12)
            t.add_column("类型", width=10)
            t.add_column("内容", width=50)
            for msg in self.team_messages:
                t.add_row(msg["from"], msg["to"], msg["type"], msg["content"][:50])
            self.console.print(t)
        else:
            for msg in self.team_messages:
                print(f"  [{msg['from']}] → [{msg['to']}] ({msg['type']}): {msg['content'][:50]}")

    def _show_logs(self) -> None:
        """显示 Agent 日志流。"""
        if HAS_RICH:
            t = Table(
                title=f"Agent 日志 ({len(self.agent_logs)} 条)",
                show_header=True,
                header_style="bold cyan",
                box=box.ROUNDED,
            )
            t.add_column("Agent", width=15)
            t.add_column("级别", width=8)
            t.add_column("消息", width=60)
            for role, msg, level in self.agent_logs[-50:]:  # 最近 50 条
                level_style = {"error": "red", "warn": "yellow"}.get(level, "")
                t.add_row(role, Text(level, style=level_style) if level_style else level, msg[:60])
            self.console.print(t)
        else:
            for role, msg, level in self.agent_logs[-50:]:
                print(f"  [{role}] {level}: {msg}")

    def _render_live_status(self, final: bool = False) -> None:
        """Render current agent status to console.

        中间过程：只打印一行进度（不刷屏）。
        最终（final=True）：打印完整状态表 + 产物列表。
        """
        # 统计
        n_done = sum(1 for s in self.agents_status.values() if s == "completed")
        n_run = sum(1 for s in self.agents_status.values() if s == "running")
        n_fail = sum(1 for s in self.agents_status.values() if s == "failed")
        total = len(AGENT_INFO)

        # 当前正在跑的 agent 名
        running_names = [r for r, s in self.agents_status.items() if s == "running"]
        running_str = ", ".join(running_names) if running_names else ""

        if not final:
            # 中间过程：一行进度
            progress_bar = "█" * n_done + "░" * (total - n_done)
            status_line = f"  [{progress_bar}] {n_done}/{total} 完成"
            if running_str:
                status_line += f"  🔄 {running_str}"
            if n_fail:
                status_line += f"  ❌ {n_fail} failed"
            if self.token_total["calls"]:
                status_line += f"  💰 {self.token_total['total']} tokens (${self.token_total['cost']:.4f})"
            # 用 \r 回到行首覆盖上一行（不换行）
            print(f"\r{status_line}", end="", flush=True)
            return

        # 最终状态：换行 + 完整表
        print()  # 换行，覆盖上面的 \r 行
        if not HAS_RICH:
            for role, (icon, desc) in AGENT_INFO.items():
                status = self.agents_status.get(role, "pending")
                marker = {"pending": "⬜", "running": "🔄", "completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "⬜")
                print(f"  {marker} {icon} {role}: {status}")
            if self.token_total["calls"]:
                print(f"  💰 Tokens: {self.token_total['total']} (${self.token_total['cost']:.4f})")
            return

        # Rich mode - 最终状态表
        t = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.ROUNDED,
            title="📊 任务完成",
            title_style="bold magenta",
        )
        t.add_column("图标", width=3)
        t.add_column("Agent", width=15)
        t.add_column("状态", width=12)
        t.add_column("Tokens", width=20)

        for role, (icon, desc) in AGENT_INFO.items():
            status = self.agents_status.get(role, "pending")
            style = STATUS_STYLE.get(status, "")
            marker = {"pending": "⬜", "running": "🔄", "completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "⬜")

            tokens = self.agent_tokens.get(role, {})
            tok_str = ""
            if tokens and tokens.get("total", 0):
                tok_str = f"{tokens['total']} (${tokens['cost']:.4f})"

            t.add_row(f"{marker}{icon}", f"{role} ({desc})", Text(status, style=style), tok_str)

        # Token summary row
        if self.token_total["calls"]:
            t.add_section()
            t.add_row(
                "💰",
                "[bold]总计[/]",
                f"[bold]{self.token_total['calls']} calls[/]",
                f"[bold]{self.token_total['total']} (${self.token_total['cost']:.6f})[/]",
            )

        self.console.print(t)

    async def repl_loop(self) -> None:
        """Main REPL loop."""
        self._banner()

        loop = asyncio.get_event_loop()
        all_cmds = self.COMMANDS  # 含别名

        while True:
            try:
                prompt_text = "🌸 sakura> "
                user_input = await loop.run_in_executor(None, lambda: input(prompt_text))
                user_input = user_input.strip()

                if not user_input:
                    continue

                # / 命令 → 走命令系统
                if user_input.startswith("/"):
                    parts = user_input[1:].split(maxsplit=1)
                    cmd = "/" + parts[0].lower()  # 保持 /
                    args = parts[1] if len(parts) > 1 else ""

                    # 只输入 / 或空命令名 → 自动显示所有命令
                    if cmd == "/" or not parts[0]:
                        self._show_commands()
                        continue

                    if cmd in ("/exit", "/quit", "/q", "/bye"):
                        self._print("👋 再见!", "magenta")
                        break
                    elif cmd == "/help":
                        self._help()
                    elif cmd in ("/commands", "/cmds", "/?"):
                        self._show_commands()
                    elif cmd in ("/clear", "/cls"):
                        self._do_clear()
                    elif cmd in ("/history",):
                        self._show_history(int(args) if args.isdigit() else 20)
                    elif cmd == "/env":
                        self._show_env()
                    elif cmd == "/model":
                        await self._do_model(args)
                    elif cmd == "/reload":
                        await self._do_reload()
                    elif cmd in ("/session", "/sid"):
                        self._do_session(args)
                    elif cmd in ("/pwd", "/cwd"):
                        self._do_pwd()
                    elif cmd in ("/ls", "/dir"):
                        self._do_ls(args)
                    elif cmd in ("/find", "/search"):
                        self._do_find(args)
                    elif cmd in ("/file", "/cat", "/read"):
                        self._do_file(args)
                    elif cmd == "/agents":
                        self._show_agents()
                    elif cmd == "/status":
                        self._show_status()
                    elif cmd in ("/tokens", "/cost"):
                        self._show_tokens()
                    elif cmd in ("/artifacts", "/arts"):
                        self._show_artifacts()
                    elif cmd in ("/artifact", "/art"):
                        self._show_artifact(args)
                    elif cmd == "/team":
                        if self.team_messages:
                            self._show_team_messages()
                        else:
                            self._print("⚠️  还没有团队通信消息，先跑一个任务", "yellow")
                    elif cmd == "/logs":
                        if self.agent_logs:
                            self._show_logs()
                        else:
                            self._print("⚠️  还没有日志，先跑一个任务", "yellow")
                    elif cmd == "/skills":
                        await self._show_skills()
                    elif cmd in ("/skill", "/s"):
                        await self._call_skill(args)
                    elif cmd in ("/mcp", "/m"):
                        if args.startswith("call "):
                            await self._mcp_call(args[5:])
                        else:
                            await self._show_mcp()
                    elif cmd in ("/task", "/build", "/do"):
                        if not args:
                            self._print("用法: /task <需求描述>", "yellow")
                        else:
                            await self._run_task(args)
                    elif cmd in ("/ask", "/chat"):
                        if not args:
                            self._print("用法: /ask <问题>   直接问 LLM，不走 agent 流程", "yellow")
                        else:
                            await self._ask_llm(args)
                    else:
                        # 未知命令 → 显示所有命令菜单
                        self._print(f"⚠️  未知命令: {cmd}", "yellow")
                        self._print("所有可用命令 (按 Tab 自动补全):", "cyan")
                        self._show_commands()
                else:
                    # Fast-path: 直接调 LLM 回答问题，不走 7-agent pipeline
                    # 长任务用 /task 显式触发
                    # 但 exit/quit/bye 这类短词直接退出
                    if user_input.lower() in ("exit", "quit", "bye", "q"):
                        self._print("👋 再见!", "magenta")
                        break

                    # @agent_name <message> — 直接和特定 agent 对话
                    if user_input.startswith("@"):
                        parts = user_input[1:].split(maxsplit=1)
                        agent_name = parts[0] if parts else ""
                        msg = parts[1] if len(parts) > 1 else ""
                        if agent_name:
                            await self._chat_with_agent(agent_name, msg)
                        else:
                            self._print("用法: @<agent_name> <消息>", "yellow")
                        continue

                    # #team_id — 切换默认团队
                    if user_input.startswith("#"):
                        team_id = user_input[1:].strip()
                        self._switch_team(team_id)
                        continue

                    # !command — 执行 shell 命令
                    if user_input.startswith("!"):
                        command = user_input[1:]
                        self._exec_shell(command)
                        continue

                    await self._ask_llm(user_input)

            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                self._print("\n👋 再见!", "magenta")
                break
            except Exception as e:
                self._print(f"⚠️  错误: {e}", "red")
                logger.error("repl_error", error=str(e))


async def main():
    """Entry point for the REPL."""
    repl = SakuraREPL()
    await repl.repl_loop()


def run_repl():
    """Sync entry point."""
    # 初始化日志，REPL 模式下把级别设到 WARNING，避免 skill 注册等 debug/info 日志淹没交互输出
    try:
        from app.core.logging import setup_logging
        setup_logging()
        import logging
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("app").setLevel(logging.WARNING)
    except Exception:
        pass
    asyncio.run(main())


if __name__ == "__main__":
    run_repl()
