"""Agent 注册表基础数据模型（借鉴 CrewAI + AG2）。

从 app/orchestration/agent_team.py 提取的核心数据结构：
- ProcessType / SpeakerMode: 枚举
- AgentDef / Task / Crew:     dataclass
- build_agent_system_prompt:  system prompt 组装函数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 枚举
# ============================================================

class ProcessType(str, Enum):
    """借鉴 CrewAI：协作执行模式。"""
    SEQUENTIAL = "sequential"     # 任务按顺序执行
    HIERARCHICAL = "hierarchical" # 主管 agent 委派任务给 worker
    CONSENSUS = "consensus"       # 多 agent 群聊达成共识
    PARALLEL = "parallel"         # 借鉴 Anthropic Orchestrator-Workers: worker 并行


class SpeakerMode(str, Enum):
    """借鉴 AG2 GroupChat：发言选择模式。"""
    ROUND_ROBIN = "round_robin"   # 按顺序
    AUTO = "auto"                 # LLM 决定下一个发言者
    MANAGER = "manager"           # Manager agent 决定


# ============================================================
# 数据模型
# ============================================================

@dataclass
class AgentDef:
    """借鉴 CrewAI.Agent：四件套 + 扩展。

    对比 v1：
    - v1: 只用 system_prompt 一段话
    - v2 (现在): role (职位) + goal (目标) + backstory (背景) + skills (能力)
    """
    id: str
    name: str
    role: str               # 借鉴 CrewAI: 职位定位
    goal: str               # 借鉴 CrewAI: 这个 agent 存在的目标
    backstory: str          # 借鉴 CrewAI: 背景故事，让 agent 有性格
    category: str
    avatar: str
    color: str
    tagline: str
    skills: list[str] = field(default_factory=list)
    allow_delegation: bool = False  # CrewAI 概念：能否把任务委派给别的 agent
    verbose: bool = False           # 是否详细输出思考过程


@dataclass
class Task:
    """借鉴 CrewAI.Task：任务的完整定义。

    对比 v1：v1 根本不知道用户任务的具体期望
    v2 (现在)：明确描述 + 期望产出 + 谁来做 + 依赖谁 + 异步与否
    """
    id: str
    description: str             # 任务描述
    expected_output: str         # 借鉴 CrewAI: 期望的产出格式/内容
    agent_id: str                # 谁来做这个任务
    context_task_ids: list[str] = field(default_factory=list)  # 借鉴 CrewAI: 依赖哪些前置任务
    output_file: str | None = None  # 借鉴 CrewAI/AG2: 保存到文件
    async_execution: bool = False   # 借鉴 CrewAI: 是否可并行执行
    status: str = "pending"         # pending / running / done / failed
    output: str = ""                # 执行结果
    metadata: dict = field(default_factory=dict)


@dataclass
class Crew:
    """借鉴 CrewAI.Crew：协作团队。"""
    id: str
    name: str
    description: str
    icon: str
    color: str
    agents: list[AgentDef]      # 团队成员
    tasks: list[Task] = field(default_factory=list)  # 任务清单
    process: ProcessType = ProcessType.SEQUENTIAL
    manager_agent_id: str | None = None  # hierarchical 模式下的主管
    preset: bool = True
    tags: list[str] = field(default_factory=list)
    # 借鉴前端协议：mode (group/pipeline/master/consensus/parallel/handoff/graph)
    mode: str = ""
    # 共享白板 ID（MetaGPT 风格：每个 crew 一个 session）
    session_id: str = ""


# ============================================================
# Agent System Prompt 生成（借鉴 CrewAI 三件套组装）
# ============================================================

def build_agent_system_prompt(agent: AgentDef) -> str:
    """借鉴 CrewAI：把 role + goal + backstory 组装成完整的 system prompt。

    CrewAI 的做法是把三段拼起来，我们做得更精致一些。
    """
    skills_text = "、".join(agent.skills) if agent.skills else "通用"
    return (
        f"# 你的身份\n"
        f"你是「{agent.name}」，职位是 **{agent.role}**。\n\n"
        f"# 你的目标\n"
        f"{agent.goal}\n\n"
        f"# 你的背景\n"
        f"{agent.backstory}\n\n"
        f"# 你的能力\n"
        f"你擅长：{skills_text}\n\n"
        f"# 你的风格\n"
        f"- 直接、具体、可用\n"
        f"- 不讲废话，不堆术语\n"
        f"- 回复简洁有力（150-300 字）\n"
        f"- 看到前面的对话要'接话'，不要重复\n"
    )
