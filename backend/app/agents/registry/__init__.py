"""Agent 注册表。

对外暴露核心数据结构与全部 agent / crew 定义：
- AgentDef / Crew / Task / ProcessType / SpeakerMode:  数据模型
- build_agent_system_prompt:                            system prompt 组装
- AGENTS / AGENT_MAP:                                   全部 agent
- CATEGORIES:                                           分类元数据
- CREWS / CREW_MAP:                                     预设 crew
"""

from .loader import AGENTS, AGENT_MAP, CATEGORIES, CREWS, CREW_MAP
from .base import AgentDef, Crew, Task, ProcessType, SpeakerMode, build_agent_system_prompt

__all__ = [
    "AGENTS",
    "AGENT_MAP",
    "CATEGORIES",
    "CREWS",
    "CREW_MAP",
    "AgentDef",
    "Crew",
    "Task",
    "ProcessType",
    "SpeakerMode",
    "build_agent_system_prompt",
]
