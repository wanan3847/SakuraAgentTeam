"""CLI 输出格式化 — table / json 两种模式。"""

from __future__ import annotations

import json
import sys
from typing import Any

try:
    from rich.console import Console
    from rich.table import Table

    HAS_RICH = True
    _err_console = Console(stderr=True)
except ImportError:  # pragma: no cover
    HAS_RICH = False


def emit(data: Any, output_format: str = "table") -> None:
    """统一输出：table 走 rich，其他走 JSON。"""
    if output_format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        _print_table(data)


def _print_table(data: Any) -> None:
    if not HAS_RICH:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return
    if isinstance(data, list) and data and isinstance(data[0], dict):
        table = Table(show_header=True, header_style="bold magenta")
        cols = list(data[0].keys())
        for c in cols:
            table.add_column(c)
        for row in data:
            table.add_row(*[str(row.get(c, ""))[:120] for c in cols])
        Console().print(table)
    elif isinstance(data, dict):
        Console().print_json(data=data)
    else:
        print(data)


def error(msg: str) -> None:
    """错误输出到 stderr。"""
    if HAS_RICH:
        _err_console.print(f"[bold red]错误[/] {msg}")
    else:
        print(f"错误 {msg}", file=sys.stderr)


def success(msg: str) -> None:
    if HAS_RICH:
        Console().print(f"[bold green]✓[/] {msg}")
    else:
        print(f"✓ {msg}")


def info(msg: str) -> None:
    if HAS_RICH:
        Console().print(f"[cyan]ℹ[/] {msg}")
    else:
        print(f"ℹ {msg}")
