"""CLI smoke 测试 — 用 typer CliRunner 跑关键命令。

不依赖后端进程，只验证：
  - 子命令可调用
  - 配置读写
  - 后端不可达时优雅报错
"""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from cli.config import Config
from cli.main import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # 关键子命令都在
    for cmd in ("task", "sessions", "status", "logs", "artifacts", "cancel", "projects", "doctor"):
        assert cmd in result.stdout


def test_config_show_default(monkeypatch, tmp_path):
    """默认配置 + 不存在的文件路径。"""
    monkeypatch.setattr("cli.config.CONFIG_FILE", tmp_path / "nope.toml")
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "nope.toml" in result.stdout or "api_url" in result.stdout


def test_config_set_writes_file(monkeypatch, tmp_path):
    cfg_file = tmp_path / "sakura.toml"
    monkeypatch.setattr("cli.config.CONFIG_FILE", cfg_file)
    result = runner.invoke(app, ["config", "set", "--api-url", "http://x:1"])
    assert result.exit_code == 0
    assert cfg_file.exists()
    assert "http://x:1" in cfg_file.read_text()


def test_config_set_then_show(monkeypatch, tmp_path):
    cfg_file = tmp_path / "sakura.toml"
    monkeypatch.setattr("cli.config.CONFIG_FILE", cfg_file)
    runner.invoke(app, ["config", "set", "--api-url", "http://y:2", "--workflow", "brownfield"])
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "http://y:2" in result.stdout
    assert "brownfield" in result.stdout


def test_config_path_prints_file(monkeypatch, tmp_path):
    cfg_file = tmp_path / "sakura.toml"
    monkeypatch.setattr("cli.config.CONFIG_FILE", cfg_file)
    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert str(cfg_file) in result.stdout


def test_doctor_backend_unreachable(monkeypatch, tmp_path):
    """后端不可达时优雅退出非零码。"""
    cfg_file = tmp_path / "sakura.toml"
    monkeypatch.setattr("cli.config.CONFIG_FILE", cfg_file)
    runner.invoke(app, ["config", "set", "--api-url", "http://127.0.0.1:1"])  # 关闭端口
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "不可达" in result.stdout or "不可达" in (result.stderr or "")


def test_session_lifecycle_mocked(monkeypatch, tmp_path):
    """Mock SakuraClient，跑 task --no-wait → sessions → status 全流程。"""
    cfg_file = tmp_path / "sakura.toml"
    monkeypatch.setattr("cli.config.CONFIG_FILE", cfg_file)
    runner.invoke(app, ["config", "set", "--api-url", "http://mock"])

    fake_session = {
        "id": "abc123",
        "requirement": "做个 todo",
        "status": "completed",
        "created_at": "2026-06-20T00:00:00+00:00",
    }
    fake_list = [fake_session]
    fake_detail = {**fake_session, "agent_progress": {}, "artifacts": []}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def create_session(self, requirement, project_id=None, workflow=None, auto_start=True):
            return fake_session

        def list_sessions(self):
            return fake_list

        def get_session(self, sid):
            return fake_detail

        def health(self):
            return {"status": "healthy"}

    with patch("cli.main.SakuraClient", FakeClient):
        r1 = runner.invoke(app, ["task", "做个 todo", "--no-wait", "--output", "json"])
        assert r1.exit_code == 0
        assert "abc123" in r1.stdout

        r2 = runner.invoke(app, ["sessions"])
        assert r2.exit_code == 0
        assert "abc123" in r2.stdout or "做个 todo" in r2.stdout

        r3 = runner.invoke(app, ["status", "abc123", "--output", "json"])
        assert r3.exit_code == 0
        assert "abc123" in r3.stdout


def test_emit_json_format():
    """JSON 模式直接 dump。"""
    import io
    import sys

    from cli.output import emit

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        emit({"a": 1, "b": [1, 2]}, output_format="json")
    finally:
        sys.stdout = old
    out = buf.getvalue()
    obj = json.loads(out)
    assert obj == {"a": 1, "b": [1, 2]}


def test_get_config_env_override(monkeypatch, tmp_path):
    """环境变量 SAKURA_API_URL 覆盖配置文件。"""
    monkeypatch.setattr("cli.config.CONFIG_FILE", tmp_path / "nope.toml")
    monkeypatch.setenv("SAKURA_API_URL", "http://env:99")
    cfg = Config.load()
    assert cfg.api_url == "http://env:99"
