"""预设 Crew 定义（8 个）。

从 app/orchestration/agent_team.py 提取。

为避免与 loader.py 的循环导入，本模块自行汇总所有 agent 列表并构建
本地 _AGENT_MAP，供 _crew() 使用。
"""

from .base import AgentDef, Crew, ProcessType
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


# 汇总所有 agent，构建本地 map（避免与 loader 循环导入）
_ALL_AGENTS = (
    CREATIVE_AGENTS + DESIGN_AGENTS + TECH_AGENTS + RESEARCH_AGENTS
    + STRATEGY_AGENTS + QA_AGENTS + INDUSTRY_AGENTS + EXTRA_AGENTS
    + ACADEMIC_AGENTS + EXTENDED_AGENTS
)
_AGENT_MAP: dict[str, AgentDef] = {a.id: a for a in _ALL_AGENTS}


def _process_to_mode(p: ProcessType) -> str:
    """把 process 映射到前端的 mode。"""
    mapping = {
        ProcessType.SEQUENTIAL: "group",
        ProcessType.HIERARCHICAL: "master",
        ProcessType.CONSENSUS: "group",
        ProcessType.PARALLEL: "parallel",
    }
    return mapping.get(p, "group")


def _crew(
    cid: str, name: str, description: str, icon: str, color: str,
    process: ProcessType, members: list[str], tags: list[str],
    manager_id: str | None = None, mode: str = "",
) -> Crew:
    return Crew(
        id=cid, name=name, description=description, icon=icon, color=color,
        agents=[_AGENT_MAP[mid] for mid in members if mid in _AGENT_MAP],
        process=process, manager_agent_id=manager_id, tags=tags,
        mode=mode or _process_to_mode(process), session_id=cid,
    )


CREWS: list[Crew] = [
    _crew("marketing_squad", "营销突击队", "从洞察到文案到投放，一站式营销全链路", "🚀", "#ec4899",
          ProcessType.SEQUENTIAL, ["analyst", "copywriter", "visual_designer", "growth"],
          ["营销", "品牌", "增长"]),

    _crew("content_factory", "内容工厂", "采集→撰写→校对→整合，流水线生产高质量内容", "🏭", "#10b981",
          ProcessType.SEQUENTIAL,  # pipeline 复用 sequential
          ["analyst", "editor", "reviewer", "editor"],
          ["内容", "流水线", "生产"], mode="pipeline"),

    _crew("dev_squad", "研发小队", "前后端+测试，快速交付可运行的代码", "⚙", "#3b82f6",
          ProcessType.SEQUENTIAL, ["fullstack", "frontend", "backend", "tester"],
          ["开发", "全栈", "交付"]),

    _crew("research_lab", "研究院", "行研+数据+学术，产出有深度的研究报告", "🔬", "#f59e0b",
          ProcessType.SEQUENTIAL, ["analyst", "data_scientist", "professor", "reviewer"],
          ["研究", "报告", "学术"]),

    _crew("startup_partners", "创业合伙人", "战略+产品+增长+财务，像真合伙人一样讨论", "🤝", "#6366f1",
          ProcessType.CONSENSUS, ["strategist", "product_manager", "growth", "finance"],
          ["创业", "战略", "商业"]),

    _crew("brand_studio", "品牌工作室", "文案+视觉+插画+公关，打造完整品牌形象", "🎨", "#8b5cf6",
          ProcessType.SEQUENTIAL, ["copywriter", "visual_designer", "illustrator", "pr"],
          ["品牌", "设计", "公关"]),

    # hierarchical: product_manager 作为主管
    _crew("product_dev", "产品开发组", "产品经理主管协调，工程师并行实现", "📱", "#10b981",
          ProcessType.HIERARCHICAL, ["product_manager", "frontend", "backend", "tester"],
          ["产品", "开发", "敏捷"], manager_id="product_manager"),

    # parallel: 3 个 worker 并行实现不同模块
    _crew("parallel_eng", "并行工程组", "借鉴 Anthropic：主管委派任务，工程师并行完成", "🔀", "#3b82f6",
          ProcessType.PARALLEL, ["fullstack", "frontend", "backend", "reviewer"],
          ["并行", "工程", "Anthropic"], manager_id="fullstack"),

    # 论文写作团队（流水线模式）
    _crew("paper_writing_team", "论文写作团队", "文献→方法→分析→写作→润色→审查，全流程学术论文写作", "🎓", "#8B5CF6",
          ProcessType.SEQUENTIAL,
          ["literature_review_agent", "methodology_design_agent", "data_analysis_agent",
           "paper_writing_agent", "editing_polishing_agent", "paper_review_agent"],
          ["学术", "论文", "写作"], mode="pipeline"),
]
