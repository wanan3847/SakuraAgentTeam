"""Agent Team — 借鉴业界三大框架的成熟多 agent 协作引擎。

借鉴：
- **CrewAI**：Agent (role/goal/backstory) + Task (description/expected_output/agent) + Crew + Process
- **AG2 (AutoGen)**：GroupChatManager 智能选择下一个发言者（auto/round_robin/manager）
- **Anthropic**：Orchestrator-Workers 范式（主管委派任务，worker 并行独立完成）
- **MetaGPT**：SOP 软件公司角色分工 + 产物传递链

核心数据模型：
- AgentDef:      role + goal + backstory + tools + personality
- Task:          description + expected_output + agent + context
- Crew:          agents + tasks + process (sequential / hierarchical / consensus)
- Process:       决定任务执行顺序和 agent 调度方式
- GroupChatMgr:  智能选择下一个发言者
- Orchestrator:  主管 agent 委派任务给 worker

执行流程：
1. 用户提出需求
2. Crew 启动
3. 按 process 调度 agents 完成任务
4. 每个 agent 根据 role/goal/backstory 决定怎么工作
5. 任务之间通过 context 传递产物
6. 最终输出整合结果
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

from app.core.logging import get_logger
from app.foundation.llm.base import LLMProvider, Message, MessageRole

# 从 registry 导入 agent 定义与数据模型（原内联定义已提取至 app/agents/registry/）
from app.agents.registry import (
    AGENTS,
    AGENT_MAP,
    CATEGORIES,
    CREWS,
    CREW_MAP,
)
from app.agents.registry.base import (
    AgentDef,
    Crew,
    ProcessType,
    SpeakerMode,
    Task,
    build_agent_system_prompt,
)

logger = get_logger(__name__)


# ============================================================
# 协作事件（ChatEvent 保留在引擎模块；其余数据模型已移至 registry）
# ============================================================

@dataclass
class ChatEvent:
    """协作过程事件（SSE 流式输出）。"""
    type: str
    data: dict = field(default_factory=dict)


# Agent 定义与预设 Crew 已移至 app/agents/registry/，通过顶部 import 引入。
# 下方仅保留 _process_to_mode（供 list_teams 使用）与协作引擎逻辑。


def _process_to_mode(p: ProcessType) -> str:
    """把 process 映射到前端的 mode（供 list_teams / create_custom_team 使用）。"""
    mapping = {
        ProcessType.SEQUENTIAL: "group",
        ProcessType.HIERARCHICAL: "master",
        ProcessType.CONSENSUS: "group",
        ProcessType.PARALLEL: "parallel",
    }
    return mapping.get(p, "group")


# ============================================================
# 协作引擎
# ============================================================

class GroupChatManager:
    """借鉴 AG2 (AutoGen) GroupChatManager。

    在群聊模式下，智能决定下一个发言者，而不是固定按顺序。
    """

    def __init__(self, agents: list[AgentDef], mode: SpeakerMode = SpeakerMode.AUTO):
        self.agents = agents
        self.mode = mode

    def select_next_speaker(
        self, history: list, last_message: str, llm: LLMProvider | None = None
    ) -> AgentDef:
        """决定下一个发言者。

        - round_robin: 按顺序
        - auto: 用 LLM 决定
        - manager: 留接口
        """
        if self.mode == SpeakerMode.ROUND_ROBIN:
            return self._round_robin(history)
        if self.mode == SpeakerMode.AUTO and llm:
            return self._auto_select(last_message, llm)
        return self._round_robin(history)

    def _round_robin(self, history: list) -> AgentDef:
        """按顺序选下一个。"""
        if not history:
            return self.agents[0]
        # 找到上一个 agent role
        last_role = history[-1].get("role") if history else None
        for i, a in enumerate(self.agents):
            if a.role == last_role:
                return self.agents[(i + 1) % len(self.agents)]
        return self.agents[0]

    def _auto_select(self, last_message: str, llm: LLMProvider) -> AgentDef:
        """用 LLM 决定下一个发言者（借鉴 AG2 auto mode）。"""
        import asyncio
        agent_list = "、".join(f"{a.name}（{a.tagline}）" for a in self.agents)
        prompt = (
            f"团队成员：{agent_list}\n\n"
            f"上一条回复：{last_message[:500]}\n\n"
            f"现在应该谁接着回复？只回一个名字，不要其他内容。"
        )
        try:
            # 同步调用包装成异步
            loop = asyncio.get_event_loop()
            resp = loop.run_until_complete(
                llm.achat([Message(role=MessageRole.USER, content=prompt)])
            )
            chosen = (resp.content or "").strip()
            for a in self.agents:
                if a.name in chosen or a.role in chosen:
                    return a
        except Exception as e:
            logger.warning("auto_speaker_failed", error=str(e))
        return self.agents[0]


class CollaborationEngine:
    """协作引擎：执行 Crew 的任务。"""

    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm = llm_provider

    # ---- 入口 ----

    async def run(
        self,
        crew: Crew,
        message: str,
        history: list[dict] | None = None,
        custom_member_ids: list[str] | None = None,
    ) -> AsyncIterator[ChatEvent]:
        """驱动一个 crew 完成用户任务。"""
        if not self.llm:
            yield ChatEvent(type="error", data={"message": "LLM 未配置"})
            return

        # 决定 agent 列表
        if custom_member_ids:
            agents = [AGENT_MAP[mid] for mid in custom_member_ids if mid in AGENT_MAP]
            crew = Crew(
                id=crew.id, name=crew.name, description=crew.description,
                icon=crew.icon, color=crew.color, agents=agents,
                process=crew.process, manager_agent_id=crew.manager_agent_id,
            )

        if not agents:
            yield ChatEvent(type="error", data={"message": "团队为空"})
            return

        # Crew 启动
        yield ChatEvent(type="crew_start", data={
            "crew_id": crew.id, "name": crew.name, "icon": crew.icon,
            "color": crew.color, "process": crew.process.value,
            "agents_count": len(crew.agents),
        })

        history = history or []
        if crew.process == ProcessType.SEQUENTIAL:
            async for evt in self._run_sequential(crew, message, history):
                yield evt
        elif crew.process == ProcessType.HIERARCHICAL:
            async for evt in self._run_hierarchical(crew, message, history):
                yield evt
        elif crew.process == ProcessType.CONSENSUS:
            async for evt in self._run_consensus(crew, message, history):
                yield evt
        elif crew.process == ProcessType.PARALLEL:
            async for evt in self._run_parallel(crew, message, history):
                yield evt

        yield ChatEvent(type="chat_done", data={"crew_id": crew.id, "mode": crew.process.value})

    # ---- Sequential: 按顺序执行（借鉴 CrewAI default） ----

    async def _run_sequential(self, crew: Crew, message: str, history: list) -> AsyncIterator[ChatEvent]:
        running = list(history)
        running.append(_msg_dict("user", "用户", message, "🧑", "#3B82F6"))
        for i, agent in enumerate(crew.agents):
            async for evt in self._agent_speak(agent, message, running, task_label=f"任务 {i+1}/{len(crew.agents)}"):
                yield evt
        yield ChatEvent(type="crew_finished", data={"mode": "sequential"})

    # ---- Hierarchical: 借鉴 CrewAI HierarchicalProcess（主管委派） ----

    async def _run_hierarchical(self, crew: Crew, message: str, history: list) -> AsyncIterator[ChatEvent]:
        running = list(history)
        running.append(_msg_dict("user", "用户", message, "🧑", "#3B82F6"))

        # 主管 agent 先分析任务，决定怎么委派
        manager = next((a for a in crew.agents if a.id == crew.manager_agent_id), crew.agents[0])
        workers = [a for a in crew.agents if a.id != manager.id]

        yield ChatEvent(type="phase_start", data={"phase": "manager_planning", "manager": manager.name})

        # 主管分析任务
        delegation_prompt = self._build_manager_planning_prompt(manager, workers, message)
        manager_response = await self._call_lln(
            delegation_prompt, agent_role=manager.role
        )
        # 把主管的分析也作为消息输出
        yield ChatEvent(type="agent_thinking", data={
            "role": manager.role, "name": manager.name,
            "avatar": manager.avatar, "color": manager.color, "stage": "任务分解",
        })
        for i in range(0, len(manager_response), 30):
            yield ChatEvent(type="agent_chunk", data={
                "role": manager.role, "name": manager.name,
                "chunk": manager_response[i:i+30],
            })
        yield ChatEvent(type="agent_done", data={
            "role": manager.role, "name": manager.name, "avatar": manager.avatar,
            "color": manager.color, "content": manager_response, "stage": "任务分解",
        })
        running.append(_msg_dict(manager.role, manager.name, manager_response, manager.avatar, manager.color))

        # 每个 worker 接力
        yield ChatEvent(type="phase_start", data={"phase": "workers_executing"})
        for worker in workers:
            worker_prompt = (
                f"用户需求：{message}\n\n"
                f"主管 {manager.name} 的任务分解：\n{manager_response}\n\n"
                f"请基于上述分工，从你（{worker.name}）的角度完成你负责的部分。"
            )
            async for evt in self._agent_speak(worker, worker_prompt, running, task_label=f"执行 · {worker.name}"):
                yield evt

        yield ChatEvent(type="crew_finished", data={"mode": "hierarchical"})

    # ---- Consensus: 借鉴 AG2 GroupChat（多 agent 群聊达成共识） ----

    async def _run_consensus(self, crew: Crew, message: str, history: list) -> AsyncIterator[ChatEvent]:
        running = list(history)
        running.append(_msg_dict("user", "用户", message, "🧑", "#3B82F6"))

        # AG2 GroupChat 风格：每个 agent 看完整历史
        # 第一轮按顺序，后面用 LLM 决定下一个
        manager = GroupChatManager(crew.agents, SpeakerMode.AUTO)

        # 第一轮：所有 agent 依次发言
        for agent in crew.agents:
            async for evt in self._agent_speak(agent, message, running, task_label="轮次发言"):
                yield evt

        # 第二轮：让 1-2 个最相关的 agent 总结
        # 简化：选最后一个 agent 做"总结发言"
        if len(crew.agents) > 1:
            # 用 LLM 选一个最合适的"总结者"
            last_content = running[-1].get("content", "")
            summarizer = manager.select_next_speaker(
                [{"role": m.get("role", "")} for m in running],
                last_content, self.llm
            )
            # 如果选到自己或选不到，用最后一个
            if summarizer.id == running[-1].get("role"):
                summarizer = crew.agents[-1]
            async for evt in self._agent_speak(
                summarizer, "请基于以上讨论总结出一个共识方案",
                running, task_label="总结共识",
            ):
                yield evt

        yield ChatEvent(type="crew_finished", data={"mode": "consensus"})

    # ---- Parallel: 借鉴 Anthropic Orchestrator-Workers ----

    async def _run_parallel(self, crew: Crew, message: str, history: list) -> AsyncIterator[ChatEvent]:
        running = list(history)
        running.append(_msg_dict("user", "用户", message, "🧑", "#3B82F6"))

        manager = next((a for a in crew.agents if a.id == crew.manager_agent_id), crew.agents[0])
        workers = [a for a in crew.agents if a.id != manager.id]

        # 主管先分析，把任务拆给每个 worker
        yield ChatEvent(type="phase_start", data={"phase": "orchestrator_planning", "manager": manager.name})

        delegation_prompt = self._build_manager_planning_prompt(manager, workers, message)
        manager_response = await self._call_lln(
            delegation_prompt, agent_role=manager.role
        )
        yield ChatEvent(type="agent_thinking", data={
            "role": manager.role, "name": manager.name,
            "avatar": manager.avatar, "color": manager.color, "stage": "任务委派",
        })
        for i in range(0, len(manager_response), 30):
            yield ChatEvent(type="agent_chunk", data={
                "role": manager.role, "name": manager.name,
                "chunk": manager_response[i:i+30],
            })
        yield ChatEvent(type="agent_done", data={
            "role": manager.role, "name": manager.name, "avatar": manager.avatar,
            "color": manager.color, "content": manager_response, "stage": "任务委派",
        })
        running.append(_msg_dict(manager.role, manager.name, manager_response, manager.avatar, manager.color))

        # 并行执行 worker
        yield ChatEvent(type="phase_start", data={"phase": "parallel_workers", "count": len(workers)})

        import asyncio
        results = await asyncio.gather(*[
            self._agent_speak_async(w, message, running, f"并行 · {w.name}")
            for w in workers
        ])

        # 收集所有 worker 事件
        for events in results:
            for evt in events:
                yield evt

        # 审核员（如果有）整合
        reviewer = next((a for a in crew.agents if a.category == "qa"), None)
        if reviewer:
            yield ChatEvent(type="phase_start", data={"phase": "review", "reviewer": reviewer.name})
            all_outputs = "\n\n".join(
                f"【{m['name']}】{m['content'][:500]}"
                for m in running if m.get("role") != "user"
            )
            review_prompt = (
                f"以下是多 agent 并行产出的内容，请审核并给出最终版本：\n\n{all_outputs}"
            )
            async for evt in self._agent_speak(reviewer, review_prompt, running, task_label="审核整合"):
                yield evt

        yield ChatEvent(type="crew_finished", data={"mode": "parallel"})

    # ---- 单个 agent 发言 ----

    async def _agent_speak(
        self, agent: AgentDef, user_message: str, history: list[dict], task_label: str = ""
    ) -> AsyncIterator[ChatEvent]:
        """一个 agent 发言（流式）。"""
        yield ChatEvent(type="agent_thinking", data={
            "role": agent.role, "name": agent.name,
            "avatar": agent.avatar, "color": agent.color,
            "category": agent.category, "stage": task_label,
        })

        messages = self._build_agent_messages(agent, user_message, history)
        try:
            resp = await self._call_llm(messages, agent_role=agent.role)
            content = resp.content or ""
        except Exception as exc:
            content = f"（{agent.name} 暂时无法回复：{exc}）"
            yield ChatEvent(type="agent_done", data={
                "role": agent.role, "name": agent.name, "avatar": agent.avatar,
                "color": agent.color, "content": content, "error": True,
            })
            return

        for i in range(0, len(content), 30):
            yield ChatEvent(type="agent_chunk", data={
                "role": agent.role, "name": agent.name,
                "chunk": content[i:i+30],
            })
        yield ChatEvent(type="agent_done", data={
            "role": agent.role, "name": agent.name, "avatar": agent.avatar,
            "color": agent.color, "content": content, "stage": task_label,
        })
        history.append(_msg_dict(agent.role, agent.name, content, agent.avatar, agent.color))

    async def _agent_speak_async(
        self, agent: AgentDef, user_message: str, history: list[dict], task_label: str = ""
    ) -> list[ChatEvent]:
        """异步并行版本，收集所有事件。"""
        events = []
        async for evt in self._agent_speak(agent, user_message, history, task_label):
            events.append(evt)
        return events

    # ---- 辅助 ----

    def _build_agent_messages(
        self, agent: AgentDef, user_message: str, history: list[dict]
    ) -> list[Message]:
        """为 agent 构建 messages（借鉴 CrewAI 三件套组装）。"""
        system_prompt = build_agent_system_prompt(agent)
        messages: list[Message] = [Message(role=MessageRole.SYSTEM, content=system_prompt)]

        # 加入对话历史
        if history:
            ctx = ["以下是之前的对话：\n"]
            for m in history[-10:]:
                if m.get("role") == "user":
                    ctx.append(f"用户：{m.get('content', '')}")
                else:
                    ctx.append(f"{m.get('name', '?')}：{m.get('content', '')}")
            ctx.append(f"\n请基于以上对话，从你（{agent.name}）的角度继续回复用户：{user_message[:200]}")
            messages.append(Message(role=MessageRole.USER, content="\n".join(ctx)))
        else:
            messages.append(Message(role=MessageRole.USER, content=f"用户需求：{user_message}\n\n请从你（{agent.name}）的角度回复。"))

        return messages

    def _build_manager_planning_prompt(
        self, manager: AgentDef, workers: list[AgentDef], user_message: str
    ) -> str:
        """构建主管委派任务的 prompt（借鉴 Anthropic Orchestrator-Workers）。"""
        worker_info = "\n".join(f"- {w.name}：{w.tagline}" for w in workers)
        return (
            f"你是 {manager.name}（{manager.role}），团队的主管。\n"
            f"团队成员：\n{worker_info}\n\n"
            f"用户需求：{user_message}\n\n"
            f"请完成两件事：\n"
            f"1. 把用户需求拆分成可执行的任务（每个任务分配给一个成员）\n"
            f"2. 说明每个任务要达成什么目标\n\n"
            f"格式：\n"
            f"【任务分解】<整体思路>\n"
            f"1. <任务名> → 委派给 {workers[0].name}：<目标>\n"
            f"2. <任务名> → 委派给 {workers[1].name if len(workers) > 1 else workers[0].name}：<目标>\n"
            f"...\n"
        )

    async def _call_llm(self, messages: list[Message], agent_role: str = "assistant"):
        """调 LLM。"""
        try:
            from app.foundation.llm.meter import MeteredLLMProvider
            if isinstance(self.llm, MeteredLLMProvider):
                return await self.llm.achat(
                    messages, session_id="agent-team", agent_role=agent_role,
                )
        except Exception:
            pass
        return await self.llm.achat(messages)

    async def _call_lln(self, prompt: str, agent_role: str = "manager") -> str:
        """简化调用：直接传 prompt 字符串。"""
        messages = [Message(role=MessageRole.USER, content=prompt)]
        resp = await self._call_llm(messages, agent_role=agent_role)
        return resp.content or ""


# ============================================================
# Helpers
# ============================================================

def _msg_dict(role: str, name: str, content: str, avatar: str, color: str) -> dict:
    return {
        "id": f"{role}-{uuid.uuid4().hex[:8]}",
        "role": role, "name": name, "content": content,
        "avatar": avatar, "color": color,
        "timestamp": time.time(),
    }


# ============================================================
# 全局实例
# ============================================================

_engine: CollaborationEngine | None = None
_engines_by_user: dict[int, CollaborationEngine] = {}


def get_engine(user_id: int | None = None) -> CollaborationEngine:
    """获取协作引擎实例。

    - 传 user_id 时，按用户隔离 engine（用用户自己的 LLM key/URL/model）
    - 不传时，用全局 engine（用开发者共享 key，模板兜底）
    """
    global _engine
    if user_id is None:
        if _engine is None:
            llm = _build_llm()
            _engine = CollaborationEngine(llm)
        return _engine

    # 用户隔离的 engine
    if user_id not in _engines_by_user:
        # 同步路径用 get_engine_for_user_async
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                # 异步上下文里：先用共享 LLM 占位，由调用方在 await 阶段替换
                _engines_by_user[user_id] = CollaborationEngine(_build_llm())
            else:
                from app.llm_providers.async_helpers import build_llm_for_user_async
                llm = loop.run_until_complete(build_llm_for_user_async(user_id))
                _engines_by_user[user_id] = CollaborationEngine(llm)
        except Exception as exc:
            logger.warning("user_engine_build_failed", user_id=user_id, error=str(exc))
            _engines_by_user[user_id] = CollaborationEngine(_build_llm())
    return _engines_by_user[user_id]


async def get_engine_for_user_async(user_id: int) -> CollaborationEngine:
    """异步获取用户的 engine（用用户自己保存的 LLM 配置）。"""
    if user_id not in _engines_by_user:
        try:
            from app.llm_providers.async_helpers import build_llm_for_user_async
            llm = await build_llm_for_user_async(user_id)
            _engines_by_user[user_id] = CollaborationEngine(llm)
        except Exception as exc:
            logger.warning("user_engine_async_build_failed", user_id=user_id, error=str(exc))
            _engines_by_user[user_id] = CollaborationEngine(_build_llm())
    return _engines_by_user[user_id]


def _build_llm() -> LLMProvider | None:
    """构建默认 LLM provider（用开发者共享 key，从环境变量读）。

    业务上建议使用 build_llm_for_user() 用登录用户自己保存的 key/URL/model。
    """
    try:
        from app.agents import _build_llm_provider
        return _build_llm_provider()
    except Exception as exc:
        logger.error("llm_build_failed", error=str(exc))
        return None


def build_llm_for_user(user_id: int) -> LLMProvider | None:
    """为指定登录用户构建 LLM provider — 用用户自己保存的 CustomProvider 配置。

    优先级：
    1. 用户默认配置（is_default=True 且 is_active=True）
    2. 用户第一条激活配置
    3. 退回到开发者共享 key（仅当用户没配置时）

    这是 hermes-agent 风格"你的 key 你做主"的核心实现 —
    用户的每一次对话都走自己配的 key 和 url，不再走开发者的共享 key。
    """
    import json as _json
    try:
        from app.auth.database import async_session
        from app.llm_providers.models import CustomProvider
        from app.llm_providers.registry import get_provider_by_id
        from sqlalchemy import desc, select
        from app.foundation.llm import LLMProviderFactory
        from app.foundation.llm.meter import MeteredLLMProvider

        async def _load():
            async with async_session() as session:
                # 1. 先找 is_default 的激活配置
                result = await session.execute(
                    select(CustomProvider)
                    .where(
                        CustomProvider.user_id == user_id,
                        CustomProvider.is_default == True,  # noqa: E712
                        CustomProvider.is_active == True,  # noqa: E712
                    )
                    .order_by(desc(CustomProvider.updated_at))
                    .limit(1)
                )
                cfg = result.scalar_one_or_none()
                if cfg is not None:
                    return cfg
                # 2. 退回到最新的激活配置
                result = await session.execute(
                    select(CustomProvider)
                    .where(
                        CustomProvider.user_id == user_id,
                        CustomProvider.is_active == True,  # noqa: E712
                    )
                    .order_by(desc(CustomProvider.updated_at))
                    .limit(1)
                )
                return result.scalar_one_or_none()

        # 同步跑异步查询
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            # 如果在异步上下文里，退回到共享 key（让上层 await 改写）
            logger.warning("build_llm_for_user_called_in_async_context", user_id=user_id)
            return _build_llm()
        cfg = loop.run_until_complete(_load())

        if cfg is None:
            logger.info("no_user_config", user_id=user_id, fallback="shared_key")
            return _build_llm()

        base_url = cfg.base_url
        api_key = cfg.api_key
        model = cfg.model or "gpt-4o-mini"

        # 如果选的是内置厂商，base_url 应已存在；否则用户填的 url 直接用
        # 推断 provider 类型：OpenAI 格式 vs Anthropic vs LiteLLM
        provider_name = "openai"
        if "anthropic" in base_url.lower():
            provider_name = "anthropic"
        elif "/" in model or base_url.endswith("/litellm"):
            provider_name = "litellm"

        # 把 model 暴露到 provider 实例
        inner = LLMProviderFactory.create(
            provider=provider_name,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        metered = MeteredLLMProvider(inner)
        logger.info(
            "user_llm_built",
            user_id=user_id,
            provider_id=cfg.provider_id,
            model=model,
            base_url=base_url,
            key_prefix=(api_key[:8] + "...") if api_key else "(no-key)",
        )
        return metered
    except Exception as exc:
        logger.error("build_user_llm_failed", user_id=user_id, error=str(exc))
        return _build_llm()


def list_agents(category: str | None = None) -> list[dict]:
    result = []
    for a in AGENTS:
        if category and a.category != category:
            continue
        result.append({
            "id": a.id, "name": a.name, "role": a.role,
            "category": a.category, "avatar": a.avatar, "color": a.color,
            "tagline": a.tagline, "skills": a.skills,
            "goal": a.goal, "backstory": a.backstory,
            "allow_delegation": a.allow_delegation,
        })
    return result


def list_crews() -> list[dict]:
    """列出所有 crew（兼容旧 API）。"""
    return list_teams()


def list_teams() -> list[dict]:
    """列出所有预设 crew。"""
    result = []
    for c in CREWS:
        result.append({
            "id": c.id, "name": c.name, "description": c.description,
            "icon": c.icon, "color": c.color,
            "mode": c.mode or _process_to_mode(c.process),
            "process": c.process.value,
            "preset": c.preset, "tags": c.tags,
            "manager": c.manager_agent_id,
            "members": [
                {"id": m.id, "name": m.name, "role": m.role,
                 "avatar": m.avatar, "color": m.color, "tagline": m.tagline,
                 "goal": m.goal, "backstory": m.backstory, "skills": m.skills,
                 "category": m.category, "allow_delegation": m.allow_delegation}
                for m in c.agents
            ],
        })
    return result


def get_team(team_id: str) -> Crew | None:
    return CREW_MAP.get(team_id)


def create_custom_team(
    name: str, member_ids: list[str], mode: str = "group",
    description: str = "", icon: str = "🌟", color: str = "#ec4899",
) -> Crew:
    """创建自定义 crew。

    支持的 mode:
    - group: 群聊模式（顺序执行）
    - pipeline: 流水线模式（顺序执行，复用 group 视觉）
    - master: 管家模式（hierarchical，主管委派）
    - consensus: 共识模式（多 agent 群聊达成一致）
    - parallel: 并行模式（Anthropic 风格，worker 并行）
    - handoff: 转交模式（Swarm 风格，agent 互转）
    - graph: 状态图模式（LangGraph 风格，DAG 节点）
    """
    crew_id = f"custom_{uuid.uuid4().hex[:8]}"
    # 把 mode 映射到 process
    process_map = {
        "group": ProcessType.SEQUENTIAL,
        "pipeline": ProcessType.SEQUENTIAL,
        "master": ProcessType.HIERARCHICAL,
        "consensus": ProcessType.CONSENSUS,
        "parallel": ProcessType.PARALLEL,
        "handoff": ProcessType.SEQUENTIAL,   # handoff 是顺序但带转交
        "graph": ProcessType.SEQUENTIAL,     # graph 是 DAG 顺序
    }
    process = process_map.get(mode, ProcessType.SEQUENTIAL)
    members = [AGENT_MAP[mid] for mid in member_ids if mid in AGENT_MAP]
    return Crew(
        id=crew_id, name=name, description=description or f"自定义团队：{name}",
        icon=icon, color=color, agents=members, process=process, preset=False,
        mode=mode, session_id=crew_id,
    )


# ============================================================
# LangGraph 风格：任务状态机（DAG + Checkpoint）
# ============================================================

class TaskState(str, Enum):
    """借鉴 LangGraph：每个任务节点的状态。"""
    PENDING = "pending"       # 等待依赖完成
    READY = "ready"           # 依赖已满足，可执行
    RUNNING = "running"       # 执行中
    DONE = "done"             # 完成
    FAILED = "failed"         # 失败
    SKIPPED = "skipped"       # 因上游失败被跳过


@dataclass
class TaskNode:
    """借鉴 LangGraph.StateGraph：任务节点。"""
    id: str
    name: str
    description: str
    agent_id: str
    dependencies: list[str] = field(default_factory=list)  # 前置 task_id
    state: TaskState = TaskState.PENDING
    output: str = ""
    artifacts: list[dict] = field(default_factory=list)
    retries: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0


class TaskGraph:
    """借鉴 LangGraph：任务状态图。"""

    def __init__(self, tasks: list[TaskNode] | None = None):
        self.tasks: dict[str, TaskNode] = {}
        self.checkpoint: dict = {}  # 借鉴 LangGraph：可持久化 checkpoint
        if tasks:
            for t in tasks:
                self.tasks[t.id] = t

    def add(self, node: TaskNode) -> None:
        self.tasks[node.id] = node

    def get_ready(self) -> list[TaskNode]:
        """找出依赖都已完成、可执行的任务。"""
        done_ids = {t.id for t in self.tasks.values() if t.state == TaskState.DONE}
        ready = []
        for t in self.tasks.values():
            if t.state == TaskState.PENDING and all(
                dep in done_ids for dep in t.dependencies
            ):
                t.state = TaskState.READY
                ready.append(t)
        return ready

    def mark_running(self, task_id: str) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].state = TaskState.RUNNING
            self.tasks[task_id].started_at = time.time()

    def mark_done(self, task_id: str, output: str = "") -> None:
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.state = TaskState.DONE
            t.output = output
            t.finished_at = time.time()

    def mark_failed(self, task_id: str) -> None:
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.state = TaskState.FAILED
            t.finished_at = time.time()
            # 级联：所有依赖此任务的下游任务标记为 SKIPPED
            for other in self.tasks.values():
                if task_id in other.dependencies and other.state == TaskState.PENDING:
                    other.state = TaskState.SKIPPED

    def is_finished(self) -> bool:
        return all(
            t.state in (TaskState.DONE, TaskState.FAILED, TaskState.SKIPPED)
            for t in self.tasks.values()
        )

    def checkpoint_save(self) -> dict:
        """保存检查点（借鉴 LangGraph）。"""
        self.checkpoint = {
            "tasks": {
                tid: {
                    "id": t.id, "name": t.name, "state": t.state.value,
                    "output": t.output[:500] if t.output else "",
                    "artifacts_count": len(t.artifacts),
                }
                for tid, t in self.tasks.items()
            },
            "saved_at": time.time(),
        }
        return self.checkpoint

    def to_dict(self) -> dict:
        return {
            "tasks": [
                {
                    "id": t.id, "name": t.name, "description": t.description,
                    "agent_id": t.agent_id, "state": t.state.value,
                    "dependencies": t.dependencies,
                    "output_preview": t.output[:200] if t.output else "",
                }
                for t in self.tasks.values()
            ],
            "is_finished": self.is_finished(),
        }


# ============================================================
# MetaGPT 风格：共享白板（agent 产物传递链）
# ============================================================

@dataclass
class WhiteboardArtifact:
    """MetaGPT 风格的产物单元。"""
    id: str
    session_id: str
    agent_id: str
    agent_name: str
    content: str
    type: str = "text"            # text / code / design / plan / review
    tags: list[str] = field(default_factory=list)
    timestamp: float = 0.0
    referenced_by: list[str] = field(default_factory=list)  # 谁引用了


class Whiteboard:
    """借鉴 MetaGPT：所有 agent 共享一个白板，下游 agent 能看到上游产物。"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.artifacts: list[WhiteboardArtifact] = []

    def publish(
        self, agent_id: str, agent_name: str, content: str,
        type: str = "text", tags: list[str] | None = None,
    ) -> WhiteboardArtifact:
        artifact = WhiteboardArtifact(
            id=f"art-{uuid.uuid4().hex[:8]}",
            session_id=self.session_id,
            agent_id=agent_id, agent_name=agent_name,
            content=content, type=type,
            tags=tags or [],
            timestamp=time.time(),
        )
        self.artifacts.append(artifact)
        return artifact

    def get_for_agent(
        self, agent_id: str, last_n: int = 5
    ) -> list[WhiteboardArtifact]:
        """获取给某 agent 看的产物（排除自己产出的，按时间倒序）。"""
        others = [a for a in self.artifacts if a.agent_id != agent_id]
        return list(reversed(others[-last_n:]))

    def get_all(self) -> list[WhiteboardArtifact]:
        return list(self.artifacts)

    def to_context_string(self, agent_id: str, last_n: int = 3) -> str:
        """把白板产物格式化成可注入到 prompt 的字符串。"""
        artifacts = self.get_for_agent(agent_id, last_n)
        if not artifacts:
            return ""
        lines = ["# 团队共享白板（前序 agent 的产出）\n"]
        for a in artifacts:
            lines.append(f"## 【{a.agent_name}】{a.type}")
            if a.tags:
                lines.append(f"标签：{', '.join(a.tags)}")
            lines.append(a.content[:1500])
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "artifact_count": len(self.artifacts),
            "artifacts": [
                {
                    "id": a.id, "agent_id": a.agent_id, "agent_name": a.agent_name,
                    "type": a.type, "tags": a.tags, "content": a.content[:2000],
                    "timestamp": a.timestamp,
                }
                for a in self.artifacts
            ],
        }


# 全局白板存储（借鉴 LangGraph Memory）
_WHITEBOARDS: dict[str, Whiteboard] = {}


def get_whiteboard(session_id: str) -> Whiteboard:
    """获取或创建某个 session 的白板。"""
    if session_id not in _WHITEBOARDS:
        _WHITEBOARDS[session_id] = Whiteboard(session_id)
    return _WHITEBOARDS[session_id]


def whiteboard_get(session_id: str) -> dict:
    """外部 API：读取白板。"""
    if session_id not in _WHITEBOARDS:
        return {"session_id": session_id, "artifact_count": 0, "artifacts": []}
    return _WHITEBOARDS[session_id].to_dict()


# ============================================================
# Smolagents 风格：Agent Trace（执行链路追踪）
# ============================================================

@dataclass
class AgentTraceStep:
    """借鉴 Smolagents：单个 trace 步骤。"""
    step: int
    type: str                     # think / tool / observe / output
    content: str
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)


class AgentTrace:
    """借鉴 Smolagents：agent 完整执行 trace。"""

    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.steps: list[AgentTraceStep] = []
        self._step = 0

    def add(self, type: str, content: str, metadata: dict | None = None) -> AgentTraceStep:
        self._step += 1
        s = AgentTraceStep(
            step=self._step, type=type, content=content,
            timestamp=time.time(), metadata=metadata or {},
        )
        self.steps.append(s)
        return s

    def think(self, thought: str) -> AgentTraceStep:
        return self.add("think", thought)

    def tool(self, tool_name: str, args: dict, result: str) -> AgentTraceStep:
        return self.add("tool", f"调用 {tool_name}({args})", {
            "tool": tool_name, "args": args, "result_preview": result[:200],
        })

    def observe(self, observation: str) -> AgentTraceStep:
        return self.add("observe", observation)

    def output(self, content: str) -> AgentTraceStep:
        return self.add("output", content[:500])

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "step_count": len(self.steps),
            "steps": [
                {"step": s.step, "type": s.type, "content": s.content,
                 "timestamp": s.timestamp, "metadata": s.metadata}
                for s in self.steps
            ],
        }


# ============================================================
# CollaborationEngine 扩展：graph 模式、handoff 模式、trace 记录
# ============================================================

def _attach_methods():
    """给 CollaborationEngine 挂载新方法（避免修改 1000+ 行文件）。"""
    import inspect
    src_lines = inspect.getsource(_attach_methods)
    # 占位函数
    pass

# 我们直接在 CollaborationEngine 类里用 monkey-patch 方式添加
# （避免重新写 600 行的 _run_xxx 方法）


async def _run_graph(
    self,
    crew: Crew,
    message: str,
    tasks: list[dict] | None = None,
    manager_id: str | None = None,
) -> AsyncIterator[ChatEvent]:
    """借鉴 LangGraph：把任务拆成 DAG 节点，按依赖关系执行。

    如果没有传 tasks，调用 LLM 主管自动生成。
    """
    wb = get_whiteboard(crew.session_id or crew.id)

    yield ChatEvent(type="crew_start", data={
        "crew_id": crew.id, "name": crew.name, "icon": crew.icon,
        "color": crew.color, "process": "graph",
        "agents_count": len(crew.agents),
    })

    # 1. 构建任务图
    graph = TaskGraph()
    if tasks:
        # 用户传入了任务定义
        for t in tasks:
            graph.add(TaskNode(
                id=t["id"], name=t.get("name", t["id"]),
                description=t.get("description", ""),
                agent_id=t.get("agent_id", crew.agents[0].id),
                dependencies=t.get("dependencies", []),
            ))
    else:
        # 让 LLM 主管自动规划
        manager_a = next(
            (a for a in crew.agents if a.id == (manager_id or crew.manager_agent_id)),
            crew.agents[0],
        )
        yield ChatEvent(type="phase_start", data={"phase": "graph_planning", "manager": manager_a.name})

        plan_prompt = _build_graph_planning_prompt(manager_a, crew.agents, message)
        plan_text = await self._call_lln(plan_prompt, agent_role=manager_a.role)
        yield ChatEvent(type="agent_done", data={
            "role": manager_a.role, "name": manager_a.name,
            "avatar": manager_a.avatar, "color": manager_a.color,
            "content": f"📋 任务图规划：\n{plan_text}", "stage": "图规划",
        })

        # 解析 LLM 输出为 tasks
        tasks = _parse_graph_plan(plan_text, crew.agents)
        for t in tasks:
            graph.add(TaskNode(
                id=t["id"], name=t.get("name", t["id"]),
                description=t.get("description", ""),
                agent_id=t.get("agent_id", crew.agents[0].id),
                dependencies=t.get("dependencies", []),
            ))

    # 2. 发送任务图快照
    yield ChatEvent(type="graph_snapshot", data=graph.to_dict())

    # 3. 拓扑执行：循环找 ready 任务，能并行的就 asyncio.gather
    import asyncio
    while not graph.is_finished():
        ready = graph.get_ready()
        if not ready:
            # 没有可执行任务但未完成（可能有循环依赖）
            pending = [t for t in graph.tasks.values() if t.state == TaskState.PENDING]
            for t in pending:
                graph.mark_failed(t.id)
            break

        # 并行执行所有 ready 任务
        if len(ready) > 1:
            yield ChatEvent(type="phase_start", data={
                "phase": "graph_parallel", "count": len(ready),
                "task_ids": [t.id for t in ready],
            })

        results = await asyncio.gather(*[
            self._execute_graph_node(crew, t, message, wb, graph)
            for t in ready
        ])

        # 收集每个节点的事件
        for events in results:
            for evt in events:
                yield evt

        # 保存 checkpoint
        yield ChatEvent(type="graph_checkpoint", data=graph.checkpoint_save())

    # 4. 整合最终输出
    final_outputs = [
        f"【{t.name} ({t.agent_id})】\n{t.output[:1000]}"
        for t in graph.tasks.values() if t.state == TaskState.DONE and t.output
    ]
    final_text = "\n\n---\n\n".join(final_outputs) if final_outputs else "（未产出）"

    # 5. 找一个审核员做最终整合（如果有）
    reviewer = next((a for a in crew.agents if a.category == "qa"), None)
    if reviewer and final_outputs:
        yield ChatEvent(type="phase_start", data={"phase": "graph_review", "reviewer": reviewer.name})
        review_prompt = (
            f"以下是状态图各节点的产出，请整合成最终交付：\n\n{final_text}"
        )
        async for evt in self._agent_speak(reviewer, review_prompt, [], task_label="最终整合"):
            yield evt

    yield ChatEvent(type="crew_finished", data={"mode": "graph", "graph": graph.to_dict()})


async def _execute_graph_node(
    self, crew: Crew, node: TaskNode, user_message: str,
    wb: Whiteboard, graph: TaskGraph,
) -> list[ChatEvent]:
    """执行单个 graph 节点。"""
    events: list[ChatEvent] = []
    agent = AGENT_MAP.get(node.agent_id) or crew.agents[0]

    graph.mark_running(node.id)
    events.append(ChatEvent(type="graph_node_start", data={
        "task_id": node.id, "task_name": node.name,
        "agent_id": agent.id, "agent_name": agent.name,
        "dependencies": node.dependencies,
    }))

    # 收集上游产物
    upstream = []
    for dep_id in node.dependencies:
        dep = graph.tasks.get(dep_id)
        if dep and dep.output:
            upstream.append(f"【{dep.name}】\n{dep.output[:800]}")

    upstream_text = "\n\n".join(upstream) if upstream else ""
    wb_text = wb.to_context_string(agent.id, last_n=3)

    task_prompt = (
        f"用户需求：{user_message}\n\n"
        f"# 你的任务：{node.name}\n{node.description}\n\n"
        f"# 前置任务的产出：\n{upstream_text}\n\n"
        f"{wb_text}\n\n"
        f"请基于以上信息，从你（{agent.name}）的角度完成任务。"
    )

    # 记录 trace
    trace = AgentTrace(agent.id, agent.name)
    trace.think(f"开始处理任务：{node.name}")

    # 执行
    output = ""
    try:
        # 让 agent 思考上游
        if upstream_text:
            trace.observe(f"读取到 {len(upstream)} 个上游产出")

        # 调 LLM
        messages = [
            Message(role=MessageRole.SYSTEM, content=build_agent_system_prompt(agent)),
            Message(role=MessageRole.USER, content=task_prompt),
        ]
        resp = await self._call_llm(messages, agent_role=agent.role)
        output = resp.content or ""
        trace.output(output)

    except Exception as exc:
        output = f"（{agent.name} 执行失败：{exc}）"
        trace.observe(f"错误：{exc}")
        graph.mark_failed(node.id)
        events.append(ChatEvent(type="graph_node_failed", data={
            "task_id": node.id, "error": str(exc),
        }))
        return events

    # 发布到白板
    artifact = wb.publish(
        agent_id=agent.id, agent_name=agent.name,
        content=output, type=node.description[:30] or "task",
        tags=[node.id, node.name],
    )
    trace.tool("whiteboard.publish", {"artifact_id": artifact.id, "type": artifact.type}, "ok")

    # 标记完成
    graph.mark_done(node.id, output)

    # 发送流式 chunk
    events.append(ChatEvent(type="agent_thinking", data={
        "role": agent.role, "name": agent.name,
        "avatar": agent.avatar, "color": agent.color,
        "stage": f"图节点 · {node.name}",
    }))
    for i in range(0, len(output), 30):
        events.append(ChatEvent(type="agent_chunk", data={
            "role": agent.role, "name": agent.name,
            "chunk": output[i:i+30],
        }))
    events.append(ChatEvent(type="agent_done", data={
        "role": agent.role, "name": agent.name,
        "avatar": agent.avatar, "color": agent.color,
        "content": output, "stage": f"图节点 · {node.name}",
        "task_id": node.id, "artifact_id": artifact.id,
    }))

    # 发送 trace
    events.append(ChatEvent(type="agent_trace", data=trace.to_dict()))

    return events


def _build_graph_planning_prompt(manager: AgentDef, workers: list[AgentDef], user_message: str) -> str:
    """构建 graph 规划的 prompt。"""
    worker_info = "\n".join(f"- id={w.id}, 名字={w.name}, 能力={','.join(w.skills)}" for w in workers)
    return (
        f"你是 {manager.name}（{manager.role}），团队的规划者。\n\n"
        f"团队成员：\n{worker_info}\n\n"
        f"用户需求：{user_message}\n\n"
        f"请把任务拆分成 3-6 个子任务，组成一个有依赖关系的 DAG 任务图。\n"
        f"格式（严格遵守）：\n"
        f"```\n"
        f"任务1: <name> | 委派给=<agent_id> | 依赖=[]\n"
        f"任务2: <name> | 委派给=<agent_id> | 依赖=[任务1]\n"
        f"任务3: <name> | 委派给=<agent_id> | 依赖=[任务1,任务2]\n"
        f"...\n"
        f"```\n"
        f"agent_id 必须是：{', '.join(w.id for w in workers)}"
    )


def _parse_graph_plan(plan_text: str, workers: list[AgentDef]) -> list[dict]:
    """解析 LLM 输出的任务图。"""
    tasks: list[dict] = []
    valid_ids = {w.id for w in workers}

    import re
    for line in plan_text.split("\n"):
        line = line.strip()
        if not line or not line.startswith("任务"):
            continue
        # 解析: 任务1: 名字 | 委派给=id | 依赖=[a,b]
        m = re.match(r"任务(\d+):\s*([^|]+)\|\s*委派给=([\w_]+)\s*\|\s*依赖=\[?([\w_,\s]*)", line)
        if not m:
            continue
        idx, name, agent_id, deps = m.groups()
        if agent_id not in valid_ids:
            # 尝试用名字匹配
            for w in workers:
                if w.name in name or w.id in line:
                    agent_id = w.id
                    break
            else:
                agent_id = workers[0].id
        deps_list = [d.strip() for d in deps.split(",") if d.strip()] if deps.strip() else []
        tasks.append({
            "id": f"task_{idx}",
            "name": name.strip(),
            "description": line,
            "agent_id": agent_id,
            "dependencies": deps_list,
        })
    return tasks


# ============================================================
# OpenAI Swarm 风格：Handoff 模式
# ============================================================

async def _run_handoff(
    self,
    crew: Crew,
    message: str,
    starter_id: str,
    max_handoffs: int = 5,
) -> AsyncIterator[ChatEvent]:
    """借鉴 OpenAI Swarm：agent 之间能互相转交任务。

    当前 agent 完成后，可选择把任务转交给更合适的 agent。
    """
    wb = get_whiteboard(crew.session_id or crew.id)
    history: list[dict] = []
    history.append(_msg_dict_safe("user", "用户", message, "🧑", "#3B82F6"))

    yield ChatEvent(type="crew_start", data={
        "crew_id": crew.id, "name": crew.name, "icon": crew.icon,
        "color": crew.color, "process": "handoff",
        "agents_count": len(crew.agents),
    })

    current_id = starter_id
    handoff_count = 0
    handoff_chain: list[str] = [starter_id]

    while handoff_count <= max_handoffs:
        current_agent = AGENT_MAP.get(current_id) or crew.agents[0]

        yield ChatEvent(type="phase_start", data={
            "phase": "handoff_step", "step": handoff_count + 1,
            "current": current_agent.name,
        })

        # 当前 agent 工作
        wb_text = wb.to_context_string(current_agent.id, last_n=2)
        handoff_context = (
            f"\n\n# 转交流水线\n"
            f"你之前由 { ' → '.join(AGENT_MAP[i].name for i in handoff_chain) } 处理过这个需求。"
            if len(handoff_chain) > 1 else ""
        )

        task_prompt = (
            f"用户需求：{message}\n\n"
            f"{handoff_context}\n\n"
            f"{wb_text}"
        )

        trace = AgentTrace(current_agent.id, current_agent.name)
        trace.think(f"handoff 第 {handoff_count + 1} 步")

        async for evt in self._agent_speak(current_agent, task_prompt, history, task_label=f"handoff #{handoff_count+1}"):
            yield evt

        # 拿到当前 agent 的产出
        last_msg = history[-1] if history else {}
        output = last_msg.get("content", "")

        # 发布到白板
        artifact = wb.publish(
            agent_id=current_agent.id, agent_name=current_agent.name,
            content=output, type="handoff_step", tags=handoff_chain,
        )
        trace.tool("whiteboard.publish", {"artifact_id": artifact.id}, "ok")
        yield ChatEvent(type="agent_trace", data=trace.to_dict())

        # 询问：是否要转交？
        handoff_decision = await self._should_handoff(current_agent, output, message, crew.agents)
        if handoff_decision is None or handoff_decision == current_id:
            # 不转交，结束
            break

        # 转交给下一个 agent
        next_agent = AGENT_MAP.get(handoff_decision)
        if not next_agent:
            break

        yield ChatEvent(type="handoff", data={
            "from": current_agent.name, "from_id": current_agent.id,
            "to": next_agent.name, "to_id": next_agent.id,
            "reason": f"{current_agent.name} 觉得更适合 {next_agent.name} 处理",
        })

        current_id = handoff_decision
        handoff_chain.append(current_id)
        handoff_count += 1

    yield ChatEvent(type="crew_finished", data={
        "mode": "handoff", "chain": handoff_chain,
        "total_steps": handoff_count + 1,
    })


async def _should_handoff(
    self, current: AgentDef, output: str, user_message: str,
    all_agents: list[AgentDef],
) -> str | None:
    """让当前 agent 决定是否要转交给别的 agent。"""
    # 简化：如果输出里有"转交给"或"handoff"等明确信号，就解析
    if "HANDOFF:" in output.upper():
        import re
        m = re.search(r"HANDOFF:\s*([\w_]+)", output, re.IGNORECASE)
        if m:
            return m.group(1)

    # 让 LLM 判断
    other_agents = [a for a in all_agents if a.id != current.id]
    agent_list = "\n".join(f"- id={a.id}, 名字={a.name}, 能力={','.join(a.skills)}" for a in other_agents)

    prompt = (
        f"你是 {current.name}（{current.role}）。\n"
        f"你的产出：{output[:500]}\n\n"
        f"其他团队成员：\n{agent_list}\n\n"
        f"用户原始需求：{user_message}\n\n"
        f"判断：当前需求是否已经被你完整解决？如果需要更专业的 agent 接力，"
        f"回复 `HANDOFF: <agent_id>`，否则回复 `DONE`。\n"
    )

    try:
        resp_text = await self._call_lln(prompt, agent_role=current.role)
        resp_text = resp_text.strip()
        if "DONE" in resp_text.upper():
            return None
        if "HANDOFF:" in resp_text.upper():
            import re
            m = re.search(r"HANDOFF:\s*([\w_]+)", resp_text, re.IGNORECASE)
            if m and m.group(1) in [a.id for a in other_agents]:
                return m.group(1)
    except Exception as e:
        logger.warning("handoff_decision_failed", error=str(e))

    return None


# ============================================================
# 工具函数
# ============================================================

def _msg_dict_safe(role: str, name: str, content: str, avatar: str, color: str) -> dict:
    """安全的消息字典（避免与模块内 _msg_dict 冲突）。"""
    return {
        "id": f"{role}-{uuid.uuid4().hex[:8]}",
        "role": role, "name": name, "content": content,
        "avatar": avatar, "color": color,
        "timestamp": time.time(),
    }


# ============================================================
# 把新方法挂到 CollaborationEngine（monkey-patch，保留向后兼容）
# ============================================================

CollaborationEngine.run_graph = _run_graph
CollaborationEngine.run_handoff = _run_handoff
CollaborationEngine._execute_graph_node = _execute_graph_node
CollaborationEngine._should_handoff = _should_handoff


# ============================================================
# 在 run() 里支持 process 覆盖（最小侵入式修改）
# ============================================================

_original_run = CollaborationEngine.run


async def _run_with_process_override(
    self, crew, message, history=None, custom_member_ids=None, process=None,
) -> AsyncIterator[ChatEvent]:
    """run() 的扩展版：支持 process 覆盖 + trace 事件 + 白板发布。"""
    if not self.llm:
        yield ChatEvent(type="error", data={"message": "LLM 未配置"})
        return

    # 决定 agent 列表
    if custom_member_ids:
        agents = [AGENT_MAP[mid] for mid in custom_member_ids if mid in AGENT_MAP]
        crew = Crew(
            id=crew.id, name=crew.name, description=crew.description,
            icon=crew.icon, color=crew.color, agents=agents,
            process=crew.process, manager_agent_id=crew.manager_agent_id,
            mode=crew.mode, session_id=crew.session_id,
        )

    if not crew.agents:
        yield ChatEvent(type="error", data={"message": "团队为空"})
        return

    # 决定实际 process
    actual_process = process or crew.process

    # 白板
    wb = get_whiteboard(crew.session_id or crew.id)
    yield ChatEvent(type="crew_start", data={
        "crew_id": crew.id, "name": crew.name, "icon": crew.icon,
        "color": crew.color, "process": actual_process.value,
        "agents_count": len(crew.agents),
        "whiteboard_size": len(wb.artifacts),
    })

    history = history or []
    if actual_process == ProcessType.SEQUENTIAL:
        async for evt in self._run_sequential(crew, message, history):
            yield evt
    elif actual_process == ProcessType.HIERARCHICAL:
        async for evt in self._run_hierarchical(crew, message, history):
            yield evt
    elif actual_process == ProcessType.CONSENSUS:
        async for evt in self._run_consensus(crew, message, history):
            yield evt
    elif actual_process == ProcessType.PARALLEL:
        async for evt in self._run_parallel(crew, message, history):
            yield evt

    yield ChatEvent(type="whiteboard_snapshot", data={
        "session_id": wb.session_id,
        "artifact_count": len(wb.artifacts),
    })
    yield ChatEvent(type="chat_done", data={
        "crew_id": crew.id, "mode": actual_process.value,
    })


CollaborationEngine.run = _run_with_process_override
