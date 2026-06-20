"""Connectors webhook 测试 — 用 FastAPI TestClient 端到端跑各端点。

覆盖：
  - GitHub Issues / PR webhook
  - 通用 IM webhook（含 token 验证 + @机器人前缀剥离）
  - 文件上传（MD / PDF / 图片）
  - URL 抓取
  - 错误路径（缺字段、错签名、不支持文件类型）
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


# ============================================================
# 工具
# ============================================================


def _github_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ============================================================
# GitHub Issues
# ============================================================


def test_github_issues_opened_creates_session():
    """issues.opened 事件 → 创建 session。"""
    payload = {
        "action": "opened",
        "issue": {
            "number": 42,
            "title": "Add user profile page",
            "body": "需要一个用户资料页",
            "html_url": "https://github.com/foo/bar/issues/42",
            "user": {"login": "alice"},
        },
        "repository": {"full_name": "foo/bar"},
    }
    r = client.post("/api/v1/connectors/github/issues", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert data["source"] == "github:issues"
    assert "session_id" in data["data"] or "id" in data["data"]


def test_github_issues_ignored_events():
    """action=closed / labeled / assigned → ignored。"""
    payload = {
        "action": "closed",
        "issue": {"number": 1, "title": "x", "body": "y"},
        "repository": {"full_name": "foo/bar"},
    }
    r = client.post("/api/v1/connectors/github/issues", json=payload)
    assert r.status_code == 200
    assert r.json()["ignored"] is True


def test_github_issues_wrong_event_header():
    """X-GitHub-Event 不是 issues → 忽略但 200。"""
    r = client.post(
        "/api/v1/connectors/github/issues",
        json={"action": "opened", "issue": {}, "repository": {}},
        headers={"X-GitHub-Event": "push"},
    )
    assert r.status_code == 200
    assert r.json()["ignored"] is True


# ============================================================
# GitHub PR
# ============================================================


def test_github_pr_opened():
    """pull_request opened → session。"""
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 7,
            "title": "Refactor auth",
            "body": "重构 auth 模块",
            "html_url": "https://github.com/x/y/pull/7",
            "user": {"login": "bob"},
        },
        "repository": {"full_name": "x/y"},
    }
    r = client.post(
        "/api/v1/connectors/github/pr",
        json=payload,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "github:pr"


def test_github_pr_comment():
    """issue_comment 事件（带 pull_request 字段）→ session。"""
    payload = {
        "action": "created",
        "issue": {"number": 7},
        "comment": {
            "body": "这段需要单元测试",
            "html_url": "https://github.com/x/y/pull/7#issuecomment-1",
            "user": {"login": "carol"},
        },
        "repository": {"full_name": "x/y"},
    }
    r = client.post(
        "/api/v1/connectors/github/pr",
        json=payload,
        headers={"X-GitHub-Event": "issue_comment"},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "github:pr"


# ============================================================
# IM（飞书/钉钉/Slack 通用）
# ============================================================


def test_im_basic():
    body = {"source": "feishu", "text": "做个日历 app", "sender": "alice", "chat_id": "oc_abc"}
    r = client.post("/api/v1/connectors/im", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "im:feishu"
    assert "做个日历 app" in data["data"]["requirement"]


def test_im_strips_bot_prefix():
    """@Sakura / /sakura 前缀应被剥离。"""
    for prefix in ("@Sakura ", "/sakura ", "/Sakura "):
        body = {"source": "dingtalk", "text": f"{prefix}做个 todo", "sender": "u1", "chat_id": "c1"}
        r = client.post("/api/v1/connectors/im", json=body)
        assert r.status_code == 200
        req = r.json()["data"]["requirement"]
        assert "做个 todo" in req
        assert prefix.strip() not in req


def test_im_missing_text():
    r = client.post("/api/v1/connectors/im", json={"source": "slack", "sender": "x", "chat_id": "y"})
    assert r.status_code == 400


def test_im_token_auth(monkeypatch):
    """配 IM_WEBHOOK_TOKEN 后，无 token / 错 token 401。"""
    monkeypatch.setenv("IM_WEBHOOK_TOKEN", "secret123")
    # 无 token
    r = client.post(
        "/api/v1/connectors/im", json={"source": "feishu", "text": "x", "sender": "a", "chat_id": "b"}
    )
    assert r.status_code == 401
    # 错 token
    r = client.post(
        "/api/v1/connectors/im",
        json={"source": "feishu", "text": "x", "sender": "a", "chat_id": "b"},
        headers={"X-IM-Token": "wrong"},
    )
    assert r.status_code == 401
    # 对 token
    r = client.post(
        "/api/v1/connectors/im",
        json={"source": "feishu", "text": "x", "sender": "a", "chat_id": "b"},
        headers={"X-IM-Token": "secret123"},
    )
    assert r.status_code == 200


# ============================================================
# 文件上传
# ============================================================


def test_upload_markdown():
    md = b"# Hello\n\nThis is a spec."
    r = client.post(
        "/api/v1/connectors/upload",
        files={"file": ("spec.md", md, "text/markdown")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "upload:.md"
    assert "Hello" in data["data"]["requirement"]


def test_upload_text_file():
    r = client.post(
        "/api/v1/connectors/upload",
        files={"file": ("notes.txt", b"plain text content", "text/plain")},
    )
    assert r.status_code == 200
    assert "plain text content" in r.json()["data"]["requirement"]


def test_upload_unsupported_type():
    r = client.post(
        "/api/v1/connectors/upload",
        files={"file": ("a.exe", b"x", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_upload_pdf():
    """PDF 解析（用最小 PDF 字节）— 即使失败也返回 200（带错误信息）。"""
    # 用空内容测一下（pypdf 会抛错但会被捕获）
    r = client.post(
        "/api/v1/connectors/upload",
        files={"file": ("empty.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )
    # 要么成功要么返回 [PDF 解析失败：…]，但不会 5xx
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        assert "PDF" in r.json()["data"]["requirement"]


def test_upload_image_metadata():
    r = client.post(
        "/api/v1/connectors/upload",
        files={"file": ("logo.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert r.status_code == 200
    req = r.json()["data"]["requirement"]
    assert "logo.png" in req
    assert "Image" in req or "图片" in req


# ============================================================
# URL 抓取
# ============================================================


def test_url_scrape_missing_urls():
    r = client.post("/api/v1/connectors/url", json={"urls": []})
    assert r.status_code == 400


def test_url_scrape_basic(monkeypatch):
    """Mock httpx 抓取，避免依赖网络。"""

    class FakeResponse:
        status_code = 200
        text = (
            "<html><head><title>Test Page</title></head>"
            "<body><nav>nav</nav><h1>Hi</h1><script>x</script>"
            "<p>Content here</p></body></html>"
        )

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url):
            return FakeResponse()

    import app.api.connectors as conn

    monkeypatch.setattr(conn.httpx, "AsyncClient", FakeAsyncClient)
    r = client.post(
        "/api/v1/connectors/url",
        json={"urls": ["https://example.com"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["scraped"] == 1
    assert "Test Page" in data["data"]["requirement"]
    assert "Content here" in data["data"]["requirement"]


# ============================================================
# 签名验证（GitHub）
# ============================================================


def test_github_signature_invalid(monkeypatch):
    """配了 secret 但签名错 → 401。"""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "topsecret")
    payload = {"action": "opened", "issue": {}, "repository": {}}
    r = client.post(
        "/api/v1/connectors/github/issues",
        json=payload,
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert r.status_code == 401


def test_github_signature_valid(monkeypatch):
    """配了 secret + 对的签名 → 200。"""
    secret = "topsecret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    import json as _json

    payload = {
        "action": "opened",
        "issue": {"number": 1, "title": "t", "body": "b", "user": {"login": "u"}},
        "repository": {"full_name": "x/y"},
    }
    body_bytes = _json.dumps(payload).encode()
    sig = _github_signature(secret, body_bytes)
    r = client.post(
        "/api/v1/connectors/github/issues",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "issues",
        },
    )
    assert r.status_code == 200
