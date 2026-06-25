"""端到端测试：真 LLM 7 Agent 工作流 + Token 监视。

用法：
    cd backend
    python3 scripts/test_repl_e2e.py
"""

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

# 确保能 import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.agents import create_all_agents
from app.agents.types import Context
from app.core.logging import get_logger
from app.foundation.llm.meter import get_global_provider, set_global_provider
from app.orchestration.engine import WorkflowEngine
from app.orchestration.eventbus import Event, EventType, event_bus
from app.orchestration.session import session_manager, SessionStatus
from app.orchestration.workflows import FULL_GREENFIELD

logger = get_logger(__name__)

REQUIREMENT = "做一个 todo app 支持增删改查"


async def main():
    print("=" * 60)
    print("🧪 端到端测试：真 LLM 7 Agent 工作流")
    print(f"需求: {REQUIREMENT}")
    print("=" * 60)

    # 1. 创建 agents
    print("\n📋 步骤 1: 创建 7 Agent（注入 LLM provider）")
    agents = create_all_agents()
    llm_count = sum(1 for a in agents.values() if a.llm)
    print(f"   7 Agent 创建完成 · {llm_count}/7 有 LLM provider")

    if llm_count == 0:
        print("❌ 没有 LLM provider，检查 .env 配置")
        return

    # 设置全局 provider
    for agent in agents.values():
        if agent.llm:
            set_global_provider(agent.llm)
            print(f"   全局 provider: model={agent.llm.model}")
            break

    # 2. 创建 session
    session_id = uuid.uuid4().hex[:16]
    print(f"\n📋 步骤 2: 创建 session {session_id}")
    session = session_manager.create_session(
        requirement=REQUIREMENT,
        project_id=f"e2e-{session_id}",
    )
    session_id = session.id
    print(f"   Session: {session_id}")

    # 3. 订阅事件
    events_log = []
    token_events = []

    async def on_event(event: Event):
        payload = event.payload
        etype = event.event_type
        role = payload.get("agent_role", "")

        if etype == EventType.AGENT_STARTED.value:
            print(f"   🔄 {role} 开始...")
        elif etype == EventType.AGENT_COMPLETED.value:
            print(f"   ✅ {role} 完成")
        elif etype == EventType.AGENT_FAILED.value:
            print(f"   ❌ {role} 失败: {payload.get('error', '')}")
        elif etype == EventType.AGENT_LOG.value:
            msg = payload.get("message", "")
            if "LLM call" in msg:
                token_events.append((role, payload.get("token_usage", {})))
                print(f"   💰 {role} LLM: {msg}")
        elif etype == EventType.SESSION_COMPLETED.value:
            print(f"   🎉 Session 完成: {payload}")
        elif etype == EventType.SESSION_FAILED.value:
            print(f"   💥 Session 失败: {payload}")

        events_log.append((etype, role, payload))

    event_bus.subscribe_all(on_event)

    # 4. 构建 context
    projects_root = os.environ.get("PROJECTS_ROOT", "./data/projects")
    ctx = Context(
        session_id=session_id,
        project_id=f"e2e-{session_id}",
        user_requirement=REQUIREMENT,
        metadata={
            "projects_root": projects_root,
            "project_id": f"e2e-{session_id}",
        },
    )

    # 5. 运行工作流
    print(f"\n📋 步骤 3: 运行 FULL_GREENFIELD 工作流（7 Agent DAG）")
    print(f"   DAG: REQ → DESIGN → [FRONTEND ∥ BACKEND] → TESTING → REVIEW → DEPLOYMENT")
    print()

    engine = WorkflowEngine(agents)
    await session_manager.update_status(session_id, SessionStatus.RUNNING)

    t0 = time.perf_counter()
    try:
        await engine.run(session_id, REQUIREMENT, workflow=FULL_GREENFIELD)
        await session_manager.update_status(session_id, SessionStatus.COMPLETED)
        status = "completed"
    except Exception as e:
        await session_manager.set_error(session_id, str(e))
        status = "failed"
        print(f"   ❌ 工作流异常: {e}")

    elapsed = time.perf_counter() - t0
    print(f"\n⏱️  总耗时: {elapsed:.1f}s")

    # 6. 检查结果
    print("\n" + "=" * 60)
    print("📊 端到端测试报告")
    print("=" * 60)

    # Agent 状态
    session = session_manager.get_session(session_id)
    print(f"\nAgent 状态:")
    for role, progress in session.agent_progress.items():
        print(f"  {progress.status:>10}  {role}")

    # Token 统计
    provider = get_global_provider()
    if provider:
        usage = provider.get_session_usage(session_id)
        print(f"\nToken 统计:")
        print(f"  总计: {usage.total_tokens} tokens · ${usage.total_cost_usd:.6f} · {usage.call_count} calls")
        print(f"  按 Agent:")
        for role, data in usage.by_agent.items():
            print(f"    {role:>15}: {data['total_tokens']:>6} tokens · ${data['cost_usd']:.6f} · {data['calls']} calls")
        print(f"  按模型:")
        for model, data in usage.by_model.items():
            print(f"    {model:>20}: {data['total_tokens']:>6} tokens · ${data['cost_usd']:.6f}")

    # 产物
    print(f"\n产物 ({len(session.artifacts)} 个):")
    for art in session.artifacts:
        files = art.metadata.get("files", []) if art.metadata else []
        files_count = len(files) if isinstance(files, list) else 0
        print(f"  [{art.agent_role}] {art.name} ({art.artifact_type}, {files_count} files)")

    # 产物文件列表
    print(f"\n生成的文件:")
    for art in session.artifacts:
        files = art.metadata.get("files", []) if art.metadata else []
        if isinstance(files, list):
            for f in files:
                if isinstance(f, dict) and "path" in f:
                    content = f.get("content", "")
                    print(f"  📄 {f['path']} ({len(content)} bytes)")

    # 事件统计
    print(f"\n事件统计: {len(events_log)} 个事件")
    print(f"  Token 事件: {len(token_events)} 个")

    # 判定
    print("\n" + "=" * 60)
    all_completed = all(p.status.value == "completed" for p in session.agent_progress.values())
    has_tokens = provider and provider.get_session_usage(session_id).total_tokens > 0
    has_artifacts = len(session.artifacts) >= 4

    print(f"判定:")
    print(f"  {'✅' if all_completed else '❌'} 7 Agent 全完成: {all_completed}")
    print(f"  {'✅' if has_tokens else '❌'} Token 被计量: {has_tokens}")
    print(f"  {'✅' if has_artifacts else '❌'} 产物生成: {has_artifacts} ({len(session.artifacts)} 个)")

    if all_completed and has_tokens and has_artifacts:
        print("\n🎉 端到端测试通过！真 LLM 7 Agent 工作流正常工作。")
    else:
        print("\n⚠️  部分检查未通过，查看上方详情。")

    # Cleanup
    event_bus._wildcard_callbacks.remove(on_event)


if __name__ == "__main__":
    asyncio.run(main())
