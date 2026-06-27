"""
TaskPlanner — 借鉴 Anthropic Orchestrator-Workers + CrewAI Process。

输入用户需求 + 团队成员,输出 TaskNode[]。
- 优先用 LLM 拆任务(JSON schema 输出)
- LLM 失败时用规则生成默认 DAG(analysis → solution → review → final)
- 对于简单需求也至少生成 2 个任务
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.registry.base import AgentDef, Crew
from app.foundation.llm.base import Message, MessageRole
from app.foundation.llm.meter import MeteredLLMProvider

from .collaboration_state import CollabTaskNode, new_task_id

logger = logging.getLogger(__name__)


def _build_planning_prompt(
    user_request: str,
    workers: list[AgentDef],
    manager: AgentDef | None = None,
) -> str:
    """组装任务拆解 prompt — 借鉴 Anthropic Orchestrator 的 planning 阶段。"""
    workers_desc = "\n".join(
        f"- id={w.id} | name={w.name} | role={w.role} | category={w.category} | skills={', '.join(w.skills[:3])}"
        for w in workers
    )
    manager_desc = ""
    if manager:
        manager_desc = f"\n主管:{manager.name}({manager.role})\n"

    return f"""你是一个任务规划器。根据用户需求,把任务拆解成可执行的 DAG。

## 用户需求
{user_request}

## 可用团队成员
{workers_desc}
{manager_desc}

## 拆解规则

1. 每个任务必须分配给一个合适的 agent(agent_id 必须从上面列表里选)
2. 任务之间可以有依赖关系(dependencies 是 task_id 列表)
3. 至少生成 2 个任务,最多 8 个
4. 最后一个任务应该是「整合/审核/最终交付」类型
5. 任务要具体,不要泛泛而谈

## 输出格式(必须是合法 JSON)

```json
{{
  "tasks": [
    {{
      "id": "task-1",
      "name": "需求分析",
      "description": "澄清用户目标、范围和验收标准",
      "expected_output": "结构化需求说明,包含目标、用户故事、验收标准",
      "agent_id": "product_manager",
      "dependencies": []
    }},
    {{
      "id": "task-2",
      "name": "方案设计",
      "description": "基于需求设计解决方案",
      "expected_output": "完整方案文档",
      "agent_id": "strategist",
      "dependencies": ["task-1"]
    }}
  ]
}}
```

只输出 JSON,不要输出其他内容。
"""


def _parse_plan(plan_text: str, workers: list[AgentDef]) -> list[dict[str, Any]] | None:
    """解析 LLM 返回的任务规划 JSON。"""
    # 尝试从 markdown code block 里提取
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", plan_text, re.DOTALL)
    if json_match:
        plan_text = json_match.group(1)
    else:
        # 尝试直接找 JSON 对象
        brace_match = re.search(r"\{.*\}", plan_text, re.DOTALL)
        if brace_match:
            plan_text = brace_match.group(0)

    try:
        plan = json.loads(plan_text)
        tasks = plan.get("tasks", [])
        if not tasks or not isinstance(tasks, list):
            return None

        # 校验 agent_id 是否合法
        valid_agent_ids = {w.id for w in workers}
        for t in tasks:
            if t.get("agent_id") not in valid_agent_ids:
                logger.warning(f"planner 返回未知 agent_id={t.get('agent_id')},跳过该任务")
                return None

        return tasks
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"planner JSON 解析失败: {e}")
        return None


def _fallback_plan(
    user_request: str,
    workers: list[AgentDef],
    manager: AgentDef | None = None,
) -> list[dict[str, Any]]:
    """规则兜底:生成默认 DAG(analysis → solution → review → final)。

    借鉴 MetaGPT SOP:需求 → 设计 → 实现 → 评审 → 交付。
    """
    # 选 2-4 个 worker
    selected = workers[:min(4, len(workers))]
    if len(selected) < 2:
        # 不足 2 个,复用第一个
        selected = [selected[0], selected[0]] if selected else []

    tasks: list[dict[str, Any]] = []
    task_ids: list[str] = []

    for i, w in enumerate(selected):
        tid = f"task-{i + 1}"
        task_ids.append(tid)
        if i == 0:
            name = "需求分析"
            desc = f"分析用户需求:{user_request[:200]}"
            expected = "结构化需求说明,包含目标、范围、验收标准"
        elif i == len(selected) - 1:
            name = "最终交付"
            desc = "整合所有上游产物,生成用户可直接使用的最终成果"
            expected = "完整最终方案,包含结论、具体内容、风险"
        elif i == len(selected) - 2:
            name = "审核"
            desc = "审核上游方案,发现问题并建议修复"
            expected = "审核报告,包含问题、严重级别、是否通过"
        else:
            name = f"{w.name}执行"
            desc = f"作为 {w.name}({w.role}),基于上游产物完成自己的职责"
            expected = f"{w.role}的专业产出"

        tasks.append({
            "id": tid,
            "name": name,
            "description": desc,
            "expected_output": expected,
            "agent_id": w.id,
            "dependencies": [task_ids[i - 1]] if i > 0 else [],
        })

    return tasks


def plan_tasks(
    user_request: str,
    crew: Crew,
    llm: MeteredLLMProvider | None = None,
    manager_id: str | None = None,
) -> list[dict[str, Any]]:
    """拆解任务 — 同步入口(规则兜底,不调 LLM)。

    异步版本见 plan_tasks_async。
    """
    workers = list(crew.agents)
    manager = None
    if manager_id:
        manager = next((a for a in workers if a.id == manager_id), None)
        workers = [a for a in workers if a.id != manager_id]
    if not workers:
        workers = list(crew.agents)

    tasks = _fallback_plan(user_request, workers, manager)
    logger.info(f"planner 规则兜底生成 {len(tasks)} 个任务")
    return tasks


async def plan_tasks_async(
    user_request: str,
    crew: Crew,
    llm: MeteredLLMProvider | None = None,
    manager_id: str | None = None,
) -> list[dict[str, Any]]:
    """拆解任务 — 优先 LLM,失败则规则兜底。

    Args:
        user_request: 用户需求
        crew: 团队定义
        llm: LLM provider(可选)
        manager_id: 主管 agent id(可选)

    Returns:
        任务列表,每个任务 dict 包含 id/name/description/expected_output/agent_id/dependencies
    """
    workers = list(crew.agents)
    manager = None
    if manager_id:
        manager = next((a for a in workers if a.id == manager_id), None)
        # worker 不含 manager
        workers = [a for a in workers if a.id != manager_id]

    if not workers:
        workers = list(crew.agents)

    # 优先用 LLM 拆任务
    if llm is not None:
        try:
            prompt = _build_planning_prompt(user_request, workers, manager)
            messages = [Message(role=MessageRole.USER, content=prompt)]
            if isinstance(llm, MeteredLLMProvider):
                resp = await llm.achat(messages, session_id="agent-team", agent_role="planner")
            else:
                resp = await llm.achat(messages)
            plan_text = resp.content or ""
            tasks = _parse_plan(plan_text, workers)
            if tasks:
                logger.info(f"planner LLM 拆出 {len(tasks)} 个任务")
                return tasks
            logger.warning("planner LLM 返回无效,用规则兜底")
        except Exception as e:
            logger.warning(f"planner LLM 调用失败: {e},用规则兜底")

    # 规则兜底
    tasks = _fallback_plan(user_request, workers, manager)
    logger.info(f"planner 规则兜底生成 {len(tasks)} 个任务")
    return tasks


def tasks_to_nodes(tasks: list[dict[str, Any]], agents: list[AgentDef]) -> list[CollabTaskNode]:
    """把 planner 输出的 task dict 列表转成 CollabTaskNode。"""
    agent_map = {a.id: a for a in agents}
    nodes: list[CollabTaskNode] = []
    for t in tasks:
        agent = agent_map.get(t.get("agent_id", ""))
        node = CollabTaskNode(
            id=t.get("id") or new_task_id(),
            name=t.get("name", "未命名任务"),
            description=t.get("description", ""),
            expected_output=t.get("expected_output", ""),
            agent_id=t.get("agent_id", ""),
            agent_name=agent.name if agent else t.get("agent_id", ""),
            dependencies=t.get("dependencies", []),
        )
        nodes.append(node)
    return nodes
