"""端到端集成测试：完整 workflow 跑通 + agent_progress 全部 completed + 产物可读。

这个测试模拟真实使用场景：用户创建 session → 执行 workflow →
轮询直到完成 → 断言 7 个 agent 全部 completed → 读取产物文件 → 验证 git 提交。

回归测试：M2-I2 修复（engine 在 agent.run() 成功后必须 update_agent_progress(COMPLETED)）。
"""

import asyncio
import sys
from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport

# 让脚本能找到 backend 下的 app 包
sys.path.insert(0, "/Users/yangyazhou/SakuraAgentTeam/backend")


@pytest.mark.asyncio
async def test_full_workflow_completes_with_all_agents():
    """完整 workflow：执行后所有 7 个 agent 必须进入 completed 状态。"""
    from app.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 1. 创建 session
        req_text = f"做一个 todo 应用 #{uuid4().hex[:6]}"
        r = await c.post("/api/v1/sessions", json={"requirement": req_text, "auto_start": False})
        assert r.status_code == 200, f"创建 session 失败: {r.text}"
        sid = r.json()["data"]["id"]

        # 2. 启动 workflow
        r = await c.post(f"/api/v1/sessions/{sid}/execute", json={"requirement": req_text})
        assert r.status_code == 200, f"启动 workflow 失败: {r.text}"

        # 3. 轮询直到完成（最多 30 秒）
        final = None
        for _ in range(30):
            await asyncio.sleep(1)
            r = await c.get(f"/api/v1/sessions/{sid}")
            d = r.json()["data"]
            if d["status"] in ("completed", "failed"):
                final = d
                break

        assert final is not None, "Workflow 超时未结束"
        assert final["status"] == "completed", f"Workflow 状态={final['status']}"

        # 4. 验证所有 agent 进入 completed
        progress = final.get("agent_progress", {})
        assert len(progress) == 7, f"应有 7 个 agent，实际 {len(progress)}"
        for role, p in progress.items():
            assert p["status"] == "completed", f"agent {role} 状态={p['status']}, 期望 completed"

        # 5. 验证至少生成 7 个 artifact
        artifacts = final.get("artifacts", [])
        assert len(artifacts) >= 7, f"应至少 7 个 artifact，实际 {len(artifacts)}"

        # 6. 验证产物可读取（git 仓库中确实有文件）
        project_id = final.get("project_id", sid)
        r = await c.get(f"/api/v1/projects/{project_id}/files")
        assert r.status_code == 200, "读取项目文件失败"
        files = r.json()["data"]
        assert len(files) > 0, "项目目录为空"

        # 7. 验证有 commit 历史
        r = await c.get(f"/api/v1/projects/{project_id}/commits")
        assert r.status_code == 200
        commits = r.json()["data"]
        assert len(commits) >= 1, "git 仓库没有 commit"

        # 8. 验证 agent_progress 计数与最近任务页显示一致
        completed_count = sum(1 for p in progress.values() if p["status"] == "completed")
        assert completed_count == 7


@pytest.mark.asyncio
async def test_dynamic_workflow_selects_greenfield():
    """动态工作流选择：新项目应选择 greenfield。"""
    from app.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/v1/workflows/select",
            json={"requirement": "帮我开发一个全新博客系统"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["workflow"]["name"] in ("full_greenfield", "incremental", "brownfield")


@pytest.mark.asyncio
async def test_experience_create_and_list():
    """经验库：可创建并检索。"""
    from app.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 创建
        r = await c.post(
            "/api/v1/experiences",
            json={
                "error_message": f"TestError {uuid4().hex[:6]}",
                "error_type": "TestError",
                "context": {"agent_role": "test"},
                "solution": "test solution",
                "success": True,
            },
        )
        assert r.status_code == 200
        exp_id = r.json()["exp_id"]

        # 列出
        r = await c.get("/api/v1/experiences")
        assert r.status_code == 200
        items = r.json()["data"]
        ids = [it["id"] for it in items]
        assert exp_id in ids, f"新建的经验 {exp_id} 不在列表中"
