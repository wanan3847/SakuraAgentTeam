"""E2E 验证：检查 agent_progress 状态是否正确更新为 completed。"""
import asyncio
import os
import sys

# 让脚本能找到 backend 下的 app 包
sys.path.insert(0, "/Users/yangyazhou/SakuraAgentTeam/backend")
os.chdir("/Users/yangyazhou/SakuraAgentTeam/backend")

from httpx import AsyncClient, ASGITransport


async def main():
    from app.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/v1/sessions",
            json={"requirement": "a simple todo app"},
        )
        data = r.json().get("data", {})
        sid = data.get("id")
        if not sid:
            print("FAIL: 创建 session 失败", r.json())
            return
        print(f"Session created: {sid}")

        r = await c.post(
            f"/api/v1/sessions/{sid}/execute",
            json={"requirement": "a simple todo app"},
        )
        if r.status_code >= 400:
            print(f"FAIL: 启动 workflow 失败 {r.status_code}: {r.text}")
            return
        print(f"Workflow started: {r.json()}")

        status = "running"
        progress = {}
        for i in range(20):
            await asyncio.sleep(1)
            r = await c.get(f"/api/v1/sessions/{sid}")
            d = r.json().get("data", {})
            status = d.get("status")
            progress = d.get("agent_progress", {})
            completed = sum(
                1 for p in progress.values() if p.get("status") == "completed"
            )
            total = len(progress)
            print(f"  [{i+1}s] status={status} completed={completed}/{total}")
            if status in ("completed", "failed"):
                break

        print("\n=== agent_progress 详情 ===")
        for role, p in progress.items():
            print(f"  {role:20s} -> {p.get('status')}")

        all_completed = all(
            p.get("status") == "completed" for p in progress.values()
        )
        if all_completed and status == "completed":
            print("\n[OK] 全部 agent 状态为 completed，修复生效")
        else:
            print("\n[FAIL] 仍有 agent 不是 completed 状态")
            sys.exit(1)


asyncio.run(main())
