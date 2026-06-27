"""
强制输出协议 — 借鉴 CrewAI.Task.expected_output + MetaGPT SOP。

每个 agent 根据其 category / role 匹配一个输出契约:
- artifact_type:产出什么类型的 artifact
- required_sections:必须包含哪些章节

agent prompt 必须包含当前任务、期望输出、上游 artifact、必须章节。
缺少必要章节时,后端自动发起一次修正 prompt。
"""

from __future__ import annotations

from typing import Any

from app.agents.registry.base import AgentDef


# ===== 输出契约定义 =====
# key 优先按 agent.category 匹配,其次按 agent.id 匹配

OUTPUT_CONTRACTS: dict[str, dict[str, Any]] = {
    # ===== 按 category 匹配 =====
    "创意": {
        "artifact_type": "creative",
        "required_sections": ["核心创意", "目标人群", "表达策略", "风险与备选"],
    },
    "设计": {
        "artifact_type": "design_spec",
        "required_sections": ["设计目标", "关键界面/视觉要素", "交互流程", "约束与规范"],
    },
    "技术": {
        "artifact_type": "implementation_plan",
        "required_sections": ["文件变更", "实现方案", "关键逻辑", "风险与测试要点"],
    },
    "研究": {
        "artifact_type": "research",
        "required_sections": ["研究目标", "方法与数据", "关键发现", "结论与建议"],
    },
    "策略": {
        "artifact_type": "strategy",
        "required_sections": ["现状分析", "核心策略", "执行路径", "预期效果与风险"],
    },
    "审核": {
        "artifact_type": "review_report",
        "required_sections": ["审核范围", "发现问题", "严重级别", "建议修复", "是否通过"],
    },
    "学术": {
        "artifact_type": "research",
        "required_sections": ["研究问题", "方法论", "关键发现", "结论与局限"],
    },
    # ===== 按 agent.id 匹配(更精确) =====
    "product_manager": {
        "artifact_type": "requirements",
        "required_sections": ["目标", "用户故事", "范围", "约束", "验收标准"],
    },
    "strategist": {
        "artifact_type": "strategy",
        "required_sections": ["市场现状", "核心策略", "执行路径", "预期效果与风险"],
    },
    "fullstack": {
        "artifact_type": "implementation_plan",
        "required_sections": ["文件变更", "组件设计", "状态管理", "风险"],
    },
    "frontend": {
        "artifact_type": "implementation_plan",
        "required_sections": ["文件变更", "组件设计", "交互逻辑", "风险"],
    },
    "backend": {
        "artifact_type": "implementation_plan",
        "required_sections": ["接口变更", "数据模型", "核心逻辑", "风险"],
    },
    "tester": {
        "artifact_type": "test_report",
        "required_sections": ["测试范围", "测试用例", "结果", "遗留风险"],
    },
    "reviewer": {
        "artifact_type": "review_report",
        "required_sections": ["发现问题", "严重级别", "建议修复", "是否通过"],
    },
    "ux_designer": {
        "artifact_type": "design_spec",
        "required_sections": ["信息架构", "关键界面", "交互流程", "视觉约束"],
    },
    "visual_designer": {
        "artifact_type": "design_spec",
        "required_sections": ["视觉目标", "关键视觉要素", "配色与字体", "风险"],
    },
    "data_scientist": {
        "artifact_type": "research",
        "required_sections": ["分析目标", "数据与方法", "关键发现", "结论与建议"],
    },
    "analyst": {
        "artifact_type": "research",
        "required_sections": ["分析目标", "数据来源", "关键发现", "结论与建议"],
    },
    "copywriter": {
        "artifact_type": "creative",
        "required_sections": ["核心文案", "调性说明", "适用场景", "备选方案"],
    },
    "growth": {
        "artifact_type": "strategy",
        "required_sections": ["增长目标", "渠道策略", "执行节奏", "KPI 与风险"],
    },
}


def get_contract(agent: AgentDef) -> dict[str, Any]:
    """获取 agent 的输出契约。

    优先按 agent.id 匹配,其次按 agent.category,最后用通用兜底。
    """
    if agent.id in OUTPUT_CONTRACTS:
        return OUTPUT_CONTRACTS[agent.id]
    if agent.category in OUTPUT_CONTRACTS:
        return OUTPUT_CONTRACTS[agent.category]
    # 兜底
    return {
        "artifact_type": "text",
        "required_sections": ["核心内容", "关键要点", "结论"],
    }


def build_worker_prompt(
    agent: AgentDef,
    user_request: str,
    task_name: str,
    task_description: str,
    expected_output: str,
    dependency_artifacts_text: str,
) -> str:
    """组装 worker agent 的 prompt — 借鉴 CrewAI.Task + MetaGPT SOP。

    强制 agent:
    1. 只完成当前任务,不重复其他 agent 职责
    2. 消费上游 artifact
    3. 按指定章节输出
    4. 输出具体、可执行、能被下游 agent 直接使用
    """
    contract = get_contract(agent)
    required_sections = contract["required_sections"]
    artifact_type = contract["artifact_type"]

    sections_text = "\n".join(f"- {s}" for s in required_sections)

    upstream = ""
    if dependency_artifacts_text:
        upstream = f"""
## 上游产物(你必须参考这些内容,不要重复已经完成的工作)

{dependency_artifacts_text}
"""
    else:
        upstream = """
## 上游产物
(这是第一个任务,没有上游产物)
"""

    return f"""你是团队中的【{agent.name}】。

## 你的角色
{agent.role}

## 你的目标
{agent.goal}

## 你的背景
{agent.backstory}

## 用户原始需求
{user_request}

## 当前任务
{task_name}

## 任务说明
{task_description}

## 期望输出
{expected_output or f'按照以下章节结构输出 {artifact_type} 类型的产物'}
{upstream}
## 输出要求

1. **只完成当前任务**,不要重复其他 agent 的职责,不要试图一次性解决整个需求
2. 必须输出以下章节(如果某个章节不适用,写明原因):
{sections_text}
3. 输出要**具体、可执行、能被下游 agent 直接使用**,不要发表泛泛建议
4. 用 Markdown 格式输出,章节用 `##` 标题

现在开始执行当前任务:
"""


def build_finalizer_prompt(
    user_request: str,
    artifacts_text: str,
) -> str:
    """组装 finalizer 的 prompt — 借鉴 Anthropic Orchestrator-Workers 的汇总阶段。

    强制 finalizer:
    1. 不要简单复述过程
    2. 合并重复内容
    3. 明确结论和下一步
    4. 保留关键细节
    5. 如果有风险,单独列出
    """
    return f"""你是最终整合者。

## 用户原始需求
{user_request}

## 以下是所有 agent 产物
{artifacts_text}

## 你的任务

生成用户可以直接使用的最终成果。

要求:
1. **不要简单复述过程**,用户不关心 agent 之间怎么协作的
2. 合并重复内容,消除冗余
3. 明确结论和下一步行动
4. 保留关键细节(代码、方案、数据等)
5. 如果有风险,单独列出

## 输出格式(必须包含以下章节)

```markdown
# 最终成果

## 结论
(一句话总结最终交付了什么)

## 关键产物
(列出核心成果,每个产物 2-3 句话说明)

## 具体方案 / 内容
(用户可以直接使用的完整内容:方案、代码、文案等)

## 执行过程摘要
(简述经过哪些步骤得出结论,每步 1 句话)

## 风险与后续动作
(如果有风险或需要后续跟进的事项,列在这里)
```

现在生成最终成果:
"""


def validate_output(content: str, agent: AgentDef) -> tuple[bool, list[str]]:
    """检查 agent 输出是否包含所有必要章节。

    返回 (is_valid, missing_sections)。
    """
    contract = get_contract(agent)
    required = contract["required_sections"]
    missing = []
    for section in required:
        # 宽松匹配:章节名或相近变体出现在内容里即可
        if section not in content:
            missing.append(section)
    return len(missing) == 0, missing


def build_fix_prompt(agent: AgentDef, original_output: str, missing_sections: list[str]) -> str:
    """当 agent 输出缺少章节时,生成修正 prompt。"""
    sections_text = "\n".join(f"- {s}" for s in missing_sections)
    return f"""你之前的输出缺少以下必要章节:

{sections_text}

请补充这些章节。原输出:

{original_output[:3000]}

请输出**完整的、包含所有章节**的版本(不要只输出补充部分):
"""
