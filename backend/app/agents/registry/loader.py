"""Agent 注册表加载器。

汇总所有分类的 agent 定义 + 预设 crew，对外暴露：
- AGENTS / AGENT_MAP:  全部 agent 列表与字典
- CATEGORIES:          分类元数据
- CREWS / CREW_MAP:    预设 crew 列表与字典
"""

from .base import AgentDef, Crew, ProcessType, SpeakerMode, Task, build_agent_system_prompt
from .creative import CREATIVE_AGENTS
from .design import DESIGN_AGENTS
from .tech import TECH_AGENTS
from .research import RESEARCH_AGENTS
from .strategy import STRATEGY_AGENTS
from .qa import QA_AGENTS
from .industry import INDUSTRY_AGENTS
from .extra import EXTRA_AGENTS
from .academic import ACADEMIC_AGENTS
from .extended import EXTENDED_AGENTS
from .presets import CREWS


# ============================================================
# 汇总所有 agent
# ============================================================

ALL_AGENTS = (
    CREATIVE_AGENTS + DESIGN_AGENTS + TECH_AGENTS + RESEARCH_AGENTS
    + STRATEGY_AGENTS + QA_AGENTS + INDUSTRY_AGENTS + EXTRA_AGENTS
    + ACADEMIC_AGENTS + EXTENDED_AGENTS
)

AGENTS: list[AgentDef] = ALL_AGENTS
AGENT_MAP: dict[str, AgentDef] = {a.id: a for a in AGENTS}


# ============================================================
# 分类元数据（原有 7 个 + 新增 10 个）
# ============================================================

CATEGORIES = [
    {"id": "creative",   "name": "创意",   "icon": "✨", "color": "#ec4899", "desc": "文字与故事的工匠"},
    {"id": "design",     "name": "设计",   "icon": "🎨", "color": "#8b5cf6", "desc": "视觉与体验的塑造者"},
    {"id": "tech",       "name": "技术",   "icon": "⚡", "color": "#3b82f6", "desc": "把想法变成产品的人"},
    {"id": "research",   "name": "研究",   "icon": "🔍", "color": "#f59e0b", "desc": "用数据寻找真相"},
    {"id": "strategy",   "name": "策略",   "icon": "♟", "color": "#6366f1", "desc": "在不确定中找方向"},
    {"id": "qa",         "name": "审核",   "icon": "🛡", "color": "#ef4444", "desc": "质量的最后一道关"},
    {"id": "industry",   "name": "行业",   "icon": "🏛", "color": "#14b8a6", "desc": "垂直领域的专家"},
    # 新增分类
    {"id": "education",  "name": "教育",   "icon": "📚", "color": "#0891b2", "desc": "传道授业解惑"},
    {"id": "finance",    "name": "金融",   "icon": "💰", "color": "#059669", "desc": "让财富稳健增长"},
    {"id": "legal",      "name": "法律",   "icon": "⚖️", "color": "#7c3aed", "desc": "风险与合规的守门人"},
    {"id": "healthcare", "name": "健康",   "icon": "🏥", "color": "#dc2626", "desc": "身心可持续的顾问"},
    {"id": "media",      "name": "媒体",   "icon": "🎬", "color": "#db2777", "desc": "内容与传播的创作者"},
    {"id": "music",      "name": "音乐",   "icon": "🎵", "color": "#9333ea", "desc": "声音的工程师"},
    {"id": "writing",    "name": "写作",   "icon": "✒️", "color": "#ea580c", "desc": "专业文字创作者"},
    {"id": "data",       "name": "数据",   "icon": "📊", "color": "#0d9488", "desc": "数据驱动决策"},
    {"id": "devops",     "name": "DevOps", "icon": "🔧", "color": "#4f46e5", "desc": "让系统稳定运行"},
    {"id": "business",   "name": "商业",   "icon": "💼", "color": "#b45309", "desc": "商业运营与咨询"},
    # 新增分类（academic + extended）
    {"id": "academic",   "name": "学术",   "icon": "🎓", "color": "#8B5CF6", "desc": "论文写作全流程"},
    {"id": "translation","name": "翻译",   "icon": "🌐", "color": "#0EA5E9", "desc": "跨语言沟通专家"},
    {"id": "ecommerce",  "name": "电商",   "icon": "🛒", "color": "#F43F5E", "desc": "电商运营与选品"},
    {"id": "game",       "name": "游戏",   "icon": "🎮", "color": "#8B5CF6", "desc": "游戏设计与开发"},
    {"id": "travel",     "name": "旅游",   "icon": "✈️", "color": "#06B6D4", "desc": "旅行规划与文案"},
    {"id": "food",       "name": "美食",   "icon": "🍳", "color": "#F59E0B", "desc": "菜谱与美食评论"},
    {"id": "sports",     "name": "体育",   "icon": "⚽", "color": "#10B981", "desc": "运动与体育分析"},
    {"id": "agriculture","name": "农业",   "icon": "🌾", "color": "#84CC16", "desc": "智慧农业与园艺"},
    {"id": "energy",     "name": "能源",   "icon": "⚡", "color": "#FBBF24", "desc": "新能源与电力系统"},
    {"id": "aerospace",  "name": "航空",   "icon": "🚀", "color": "#6366F1", "desc": "航空航天与无人机"},
    {"id": "environment","name": "环保",   "icon": "🌱", "color": "#22C55E", "desc": "环境工程与碳中和"},
    {"id": "social",     "name": "社交",   "icon": "💬", "color": "#EC4899", "desc": "社媒与社群运营"},
    {"id": "psychology", "name": "心理",   "icon": "🧠", "color": "#A855F7", "desc": "职业规划与心理"},
]


# ============================================================
# Crew 字典
# ============================================================

CREW_MAP: dict[str, Crew] = {c.id: c for c in CREWS}
