"""多源头输入连接器 — Webhook 端点。

支持的源头：
  - GitHub Issues / PR / Comments   POST /api/v1/connectors/github/{issues,pr,discussion}
  - 通用 IM（飞书 / 钉钉 / Slack）   POST /api/v1/connectors/im
  - 文件上传（PDF/MD/图片）          POST /api/v1/connectors/upload
  - URL 抓取                        POST /api/v1/connectors/url

设计原则：
  - 每个端点最终都调用同一个 session_manager.create_session()，
    与 CLI / Web UI 走同一条主路径。
  - 签名验证可选（环境变量配置 secret），未配置则跳过（开发友好）。
  - 所有响应都用统一的 {"success": ..., "data": ...} 格式。
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile

from app.core.logging import get_logger
from app.orchestration import session_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


# ============================================================
# 工具：复用 routes.py 的 _execute_workflow
# ============================================================


async def _trigger_workflow(
    requirement: str,
    project_id: str | None = None,
    workflow: str | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> dict[str, Any]:
    """创建 session 并（可选）触发工作流。复用 routes._execute_workflow。"""
    from app.api.routes import _execute_workflow

    session = session_manager.create_session(requirement, project_id)
    logger.info(
        "connector_session_created",
        session_id=session.id,
        project_id=project_id,
        workflow=workflow,
    )
    if background_tasks is not None:
        background_tasks.add_task(_execute_workflow, session.id, requirement, workflow)
    return {
        "id": session.id,
        "requirement": session.requirement,
        "status": session.status.value,
        "created_at": session.created_at,
    }


def _verify_github_signature(secret: str | None, body: bytes, signature: str | None) -> bool:
    """验证 GitHub webhook 签名（X-Hub-Signature-256: sha256=...）。无 secret 则跳过。"""
    if not secret:
        return True
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ============================================================
# GitHub Issues
# ============================================================


@router.post("/github/issues")
async def github_issue_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """GitHub Issues webhook — issues.opened / edited / reopened 触发。

    Headers:
      X-Hub-Signature-256: sha256=...   (可选，需配 GITHUB_WEBHOOK_SECRET)
      X-GitHub-Event: issues
    """
    body = await request.body()
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    sig = request.headers.get("X-Hub-Signature-256")
    if not _verify_github_signature(secret, body, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    if event and event != "issues":
        # 不是 issues 事件，原样接收但不触发
        return {"success": True, "ignored": True, "reason": f"event={event}"}

    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    action = payload.get("action")
    if action not in ("opened", "reopened", "edited"):
        return {"success": True, "ignored": True, "reason": f"action={action}"}

    issue = payload.get("issue", {})
    repo = payload.get("repository", {}).get("full_name", "unknown/repo")
    title = issue.get("title", "")
    body_md = issue.get("body", "") or ""
    number = issue.get("number", "?")
    user = (issue.get("user") or {}).get("login", "anonymous")
    url = issue.get("html_url", "")

    requirement = (
        f"[GitHub Issue] {repo}#{number} by @{user}\n"
        f"标题：{title}\n\n"
        f"描述：\n{body_md}\n\n"
        f"链接：{url}"
    )

    data = await _trigger_workflow(
        requirement=requirement,
        project_id=f"github:{repo}",
        background_tasks=background_tasks,
    )
    return {"success": True, "source": "github:issues", "data": data}


# ============================================================
# GitHub PR
# ============================================================


@router.post("/github/pr")
async def github_pr_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """GitHub Pull Request webhook — pull_request / issue_comment 触发。"""
    body = await request.body()
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    sig = request.headers.get("X-Hub-Signature-256")
    if not _verify_github_signature(secret, body, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    repo = payload.get("repository", {}).get("full_name", "unknown/repo")
    user = (
        (payload.get("pull_request") or {}).get("user", {}).get("login")
        or (payload.get("comment") or {}).get("user", {}).get("login")
        or "anonymous"
    )

    if event == "pull_request":
        pr = payload.get("pull_request", {})
        action = payload.get("action")
        if action not in ("opened", "reopened", "ready_for_review", "synchronize"):
            return {"success": True, "ignored": True, "reason": f"action={action}"}
        title = pr.get("title", "")
        body_md = pr.get("body", "") or ""
        number = pr.get("number", "?")
        url = pr.get("html_url", "")
        requirement = (
            f"[GitHub PR Review] {repo}#{number} by @{user}\n"
            f"标题：{title}\n\n"
            f"描述：\n{body_md}\n\n"
            f"链接：{url}"
        )
    elif event == "issue_comment":
        # PR 评论也走这里
        comment = payload.get("comment", {})
        body_md = comment.get("body", "") or ""
        issue = payload.get("issue", {})
        number = issue.get("number", "?")
        url = comment.get("html_url", "")
        requirement = (
            f"[GitHub PR Comment] {repo}#{number} by @{user}\n\n"
            f"评论：\n{body_md}\n\n"
            f"链接：{url}"
        )
    else:
        return {"success": True, "ignored": True, "reason": f"event={event}"}

    data = await _trigger_workflow(
        requirement=requirement,
        project_id=f"github:{repo}",
        background_tasks=background_tasks,
    )
    return {"success": True, "source": "github:pr", "data": data}


# ============================================================
# 通用 IM（飞书 / 钉钉 / Slack）
# ============================================================


@router.post("/im")
async def im_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """通用 IM webhook — 飞书 / 钉钉 / Slack 通用适配。

    Body 格式（统一抽象）:
      {
        "source": "feishu" | "dingtalk" | "slack" | "wechatwork",
        "text": "需求描述",
        "sender": "user_id",
        "chat_id": "oc_xxx / DTxxx / Cxxx / wrxxx",
        "project_id": "可选",
        "workflow": "可选"
      }
    """
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    source = body.get("source", "im").lower()
    text = (body.get("text") or "").strip()
    sender = body.get("sender", "anonymous")
    chat_id = body.get("chat_id", "")
    project_id = body.get("project_id")
    workflow = body.get("workflow")

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # 简单 secret 验证：环境变量 IM_WEBHOOK_TOKEN，客户端通过 X-IM-Token 头传入
    expected_token = os.environ.get("IM_WEBHOOK_TOKEN")
    if expected_token:
        client_token = request.headers.get("X-IM-Token")
        if not hmac.compare_digest(expected_token, client_token or ""):
            raise HTTPException(status_code=401, detail="Invalid IM token")

    # 去掉 @机器人 前缀（飞书/钉钉常见）
    for prefix in ("@Sakura", "@sakura", "/sakura", "/Sakura"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()

    requirement = (
        f"[IM:{source}] from {sender} in {chat_id}\n\n"
        f"{text}"
    )

    data = await _trigger_workflow(
        requirement=requirement,
        project_id=project_id or f"im:{source}:{chat_id}" if chat_id else None,
        workflow=workflow,
        background_tasks=background_tasks,
    )
    return {"success": True, "source": f"im:{source}", "data": data}


# ============================================================
# 文件上传（PDF / MD / 图片）
# ============================================================


_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_TEXT_EXT = {".md", ".markdown", ".txt"}
_ALLOWED_PDF_EXT = {".pdf"}
_ALLOWED_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _read_text_file(content: bytes, filename: str) -> str:
    return content.decode("utf-8", errors="replace")


def _read_pdf(content: bytes) -> str:
    try:
        import pypdf  # type: ignore
    except ImportError:
        return "[PDF 解析失败：未安装 pypdf。pip install pypdf 后重试。]"
    try:
        reader = pypdf.PdfReader(__import__("io").BytesIO(content))
        parts = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(parts).strip() or "[PDF 无可提取文本（可能是扫描件）]"
    except Exception as e:
        return f"[PDF 解析失败：{e}]"


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008
    project_id: str | None = Form(None),
    workflow: str | None = Form(None),
) -> dict[str, Any]:
    """文件上传端点 — 解析内容拼成 session requirement。

    支持：
      - .md / .markdown / .txt → 原文
      - .pdf                  → pypdf 抽文本
      - .png/.jpg/.jpeg/.gif/.webp → metadata 占位（无 vision model 不解析）
    """
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"文件过大（>{_MAX_FILE_SIZE} bytes）")

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()

    if ext in _ALLOWED_TEXT_EXT:
        text = _read_text_file(content, filename)
        prefix = "[Markdown/Text 文件]"
    elif ext in _ALLOWED_PDF_EXT:
        text = _read_pdf(content)
        prefix = "[PDF 文件]"
    elif ext in _ALLOWED_IMG_EXT:
        # 暂不解析图片（需要 multimodal LLM），只存 metadata
        text = (
            f"[图片文件] {filename} ({len(content)} bytes, type={file.content_type})\n"
            f"（当前未启用 vision 解析，仅作为元数据记录）"
        )
        prefix = "[Image 文件]"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {ext}（支持 {sorted(_ALLOWED_TEXT_EXT | _ALLOWED_PDF_EXT | _ALLOWED_IMG_EXT)}）",
        )

    requirement = (
        f"{prefix} {filename}\n"
        f"Content-Type: {file.content_type}\n"
        f"Size: {len(content)} bytes\n\n"
        f"{text}"
    )

    data = await _trigger_workflow(
        requirement=requirement,
        project_id=project_id,
        workflow=workflow,
        background_tasks=background_tasks,
    )
    return {"success": True, "source": f"upload:{ext}", "data": data}


# ============================================================
# URL 抓取
# ============================================================


import httpx  # noqa: E402
from bs4 import BeautifulSoup  # type: ignore # noqa: E402


@router.post("/url")
async def url_scrape(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """URL 抓取端点 — 抓取网页内容拼成 session requirement。

    Body:
      {
        "urls": ["https://...", ...],
        "project_id": "可选",
        "workflow": "可选"
      }
    """
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    urls = body.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    if not urls or not isinstance(urls, list):
        raise HTTPException(status_code=400, detail="urls must be a non-empty list")

    project_id = body.get("project_id")
    workflow = body.get("workflow")

    contents: list[str] = []
    errors: list[str] = []
    async with httpx.AsyncClient(
        timeout=15.0, follow_redirects=True, headers={"User-Agent": "SakuraAgentTeam/0.1"}
    ) as http:
        for url in urls[:10]:  # 最多 10 个
            try:
                r = await http.get(str(url))
                r.raise_for_status()
                html = r.text
                soup = BeautifulSoup(html, "html.parser")
                # 移除 script / style
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)[:8000]  # 限 8K
                title = (soup.title.string if soup.title else url) or url
                contents.append(f"## {title}\nURL: {url}\n\n{text}")
            except Exception as e:
                errors.append(f"{url}: {e}")

    if not contents:
        raise HTTPException(status_code=502, detail=f"所有 URL 抓取失败: {errors}")

    requirement = "[URL 抓取] 来源：\n\n" + "\n\n---\n\n".join(contents)
    if errors:
        requirement += f"\n\n（部分 URL 抓取失败：{errors}）"

    data = await _trigger_workflow(
        requirement=requirement,
        project_id=project_id,
        workflow=workflow,
        background_tasks=background_tasks,
    )
    return {
        "success": True,
        "source": "url",
        "scraped": len(contents),
        "failed": len(errors),
        "data": data,
    }
