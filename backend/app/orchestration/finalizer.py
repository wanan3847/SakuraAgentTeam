"""
Finalizer — 借鉴 Anthropic Orchestrator-Workers 的汇总阶段 + MetaGPT 最终交付。

消费所有 artifact,生成一个 final_report artifact。
格式必须适合用户直接使用,不是过程复述。
"""

from __future__ import annotations

import logging

from app.foundation.llm.base import Message, MessageRole
from app.foundation.llm.meter import MeteredLLMProvider

from .collaboration_state import Artifact, CollaborationState, new_artifact_id
from .output_contracts import build_finalizer_prompt

logger = logging.getLogger(__name__)


def _format_artifacts_for_prompt(state: CollaborationState) -> str:
    """把所有 artifact 格式化成 finalizer prompt 能用的文本。"""
    lines: list[str] = []
    for a in state.artifacts:
        lines.append(f"### 【{a.agent_name}】{a.title}")
        lines.append(f"类型:{a.type}")
        if a.summary:
            lines.append(f"摘要:{a.summary}")
        lines.append("内容:")
        # 截断过长的内容,避免 prompt 超长
        content = a.content[:2000]
        if len(a.content) > 2000:
            content += "\n...(内容已截断)"
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


async def synthesize_final_artifact(
    state: CollaborationState,
    llm: MeteredLLMProvider | None = None,
    finalizer_agent_name: str = "最终整合者",
) -> Artifact:
    """生成最终交付 artifact。

    Args:
        state: 协作状态(包含所有上游 artifact)
        llm: LLM provider
        finalizer_agent_name: 最终整合者的名字(展示用)

    Returns:
        final_report 类型的 Artifact
    """
    if not state.artifacts:
        # 没有 artifact,直接用用户需求生成一个简单回复
        content = f"# 最终成果\n\n## 结论\n\n根据需求「{state.user_request}」,由于协作过程中未产生有效产物,暂无最终成果。\n\n## 风险与后续动作\n\n建议重新发起协作,或检查 agent 配置。"
    else:
        artifacts_text = _format_artifacts_for_prompt(state)
        prompt = build_finalizer_prompt(state.user_request, artifacts_text)

        if llm is not None:
            try:
                messages = [Message(role=MessageRole.USER, content=prompt)]
                if isinstance(llm, MeteredLLMProvider):
                    resp = await llm.achat(messages, session_id="agent-team", agent_role="finalizer")
                else:
                    resp = await llm.achat(messages)
                content = resp.content or ""
                if not content.strip():
                    content = _fallback_final(state)
            except Exception as e:
                logger.warning(f"finalizer LLM 调用失败: {e},用拼接兜底")
                content = _fallback_final(state)
        else:
            content = _fallback_final(state)

    artifact = Artifact(
        id=new_artifact_id(),
        task_id="final",
        agent_id="finalizer",
        agent_name=finalizer_agent_name,
        type="final_report",
        title="最终成果",
        content=content,
        summary=content[:200] if content else "",
    )
    state.set_final_artifact(artifact)
    return artifact


def _fallback_final(state: CollaborationState) -> str:
    """LLM 不可用时,拼接所有 artifact 作为最终成果。"""
    lines = ["# 最终成果", "", "## 结论", "", f"本次协作共完成 {len(state.tasks)} 个任务,产出 {len(state.artifacts)} 个成果。", "", "## 关键产物", ""]
    for a in state.artifacts:
        lines.append(f"### 【{a.agent_name}】{a.title}")
        if a.summary:
            lines.append(a.summary)
        else:
            lines.append(a.content[:300])
        lines.append("")
    lines.append("## 执行过程摘要")
    for t in state.tasks:
        status = "✓" if t.state == "done" else "✗" if t.state == "failed" else "○"
        lines.append(f"- {status} {t.name}(@{t.agent_name})")
    lines.append("")
    lines.append("## 风险与后续动作")
    lines.append("(本次为规则兜底生成,建议配置 LLM 以获得更好的整合效果)")
    return "\n".join(lines)
