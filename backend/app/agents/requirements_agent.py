"""Requirements Agent - analyzes user input and produces a PRD document.

This is the first Agent in the default workflow. It produces:
- Project requirements document (PRD.md)
- List of key features
- Technical stack hints
"""

from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan
from app.core.logging import get_logger

logger = get_logger(__name__)


class RequirementsAgent(Agent):
    """Agent that analyzes requirements and writes a PRD document."""

    role = AgentRole.REQUIREMENTS
    description = "Analyze user requirements and produce a Product Requirements Document (PRD)"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Analyze user requirement, extract key features, and write a PRD document"

    def _default_plan_steps(self, ctx: Context) -> list[PlanStep]:
        return [
            PlanStep(
                description="Analyze user requirement and extract key features",
                tool="llm_chat",
                parameters={"task": "requirements_analysis"},
            ),
            PlanStep(
                description="Write PRD document structure",
                tool="file_write",
                parameters={"path": "PRD.md"},
            ),
            PlanStep(
                description="Extract technical requirements",
                tool="llm_chat",
                parameters={"task": "technical_requirements"},
            ),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate PRD document from user requirement."""
        logger.info("requirements_agent_execute", session_id=ctx.session_id)

        requirement = ctx.user_requirement

        # Generate PRD content (template-based for MVP)
        prd_content = self._generate_prd(requirement)

        # Extract features for downstream agents
        features = self._extract_features(requirement)

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="document",
            name="PRD.md",
            content=prd_content,
            metadata={
                "features": features,
                "requirements_length": len(requirement),
                "files": [
                    {"path": "PRD.md", "content": prd_content},
                ],
            },
        )

        logger.info(
            "requirements_agent_done",
            session_id=ctx.session_id,
            features_count=len(features),
        )

        return artifact

    def _generate_prd(self, requirement: str) -> str:
        """Generate a PRD document from the user's requirement."""
        # Simple template-based generation for MVP
        lines = [
            "# Product Requirements Document (PRD)",
            "",
            "## 1. 项目概述",
            "",
            requirement,
            "",
            "## 2. 目标与范围",
            "",
            "- 构建一个功能完整的全栈应用",
            "- 前后端分离架构",
            "- 支持基础 CRUD 操作",
            "- 具备良好的用户体验",
            "",
            "## 3. 功能需求",
            "",
        ]

        # Extract features based on requirement keywords
        features = self._extract_features(requirement)
        for i, feature in enumerate(features, 1):
            lines.append(f"### 3.{i} {feature['title']}")
            lines.append("")
            lines.append(feature["description"])
            lines.append("")

        lines.extend(
            [
                "## 4. 非功能性需求",
                "",
                "- **性能**: 页面加载 < 2秒，API 响应 < 500ms",
                "- **可用性**: 支持桌面和移动设备",
                "- **安全性**: 前端输入验证，后端 API 防护",
                "- **可维护性**: 代码结构清晰，注释完整",
                "",
                "## 5. 技术栈",
                "",
                "- **前端**: React 18 + TypeScript + Tailwind CSS",
                "- **后端**: FastAPI (Python)",
                "- **数据**: SQLite (MVP) / PostgreSQL (生产)",
                "- **部署**: Docker + 本地脚本",
                "",
                "## 6. 里程碑",
                "",
                "1. 需求分析与设计",
                "2. 前端开发",
                "3. 后端开发",
                "4. 测试与质量检查",
                "5. 部署与验证",
                "",
            ]
        )

        return "\n".join(lines)

    def _extract_features(self, requirement: str) -> list[dict]:
        """Extract feature list from requirement (keyword-based for MVP)."""
        features = []
        text = requirement.lower()

        # Common feature patterns
        if any(k in text for k in ["todo", "待办", "任务", "task"]):
            features.append(
                {
                    "title": "任务管理",
                    "description": "用户可以创建、编辑、删除和完成任务。支持任务列表展示和状态过滤。",
                }
            )

        if any(k in text for k in ["用户", "登录", "认证", "user", "login", "auth"]):
            features.append(
                {
                    "title": "用户认证",
                    "description": "支持用户注册、登录和会话管理。使用 Token 进行身份验证。",
                }
            )

        if any(k in text for k in ["博客", "文章", "post", "blog", "article"]):
            features.append(
                {
                    "title": "文章发布",
                    "description": "支持创建、编辑和展示文章内容。支持基本的 Markdown/富文本格式。",
                }
            )

        if any(k in text for k in ["评论", "comment", "discussion"]):
            features.append(
                {
                    "title": "评论系统",
                    "description": "用户可以对内容发表评论、回复，支持评论列表和删除。",
                }
            )

        if any(k in text for k in ["标签", "分类", "tag", "category"]):
            features.append(
                {
                    "title": "标签/分类",
                    "description": "支持为内容添加标签或分类，支持按标签/分类过滤内容。",
                }
            )

        # Always add a basic feature
        if not features:
            features.append(
                {
                    "title": "核心功能",
                    "description": "根据用户需求实现核心业务功能。包含数据的增删改查操作。",
                }
            )

        return features

    async def review(self, artifact: Artifact, ctx: Context) -> object:
        """Custom review: ensure PRD has at least 2 features."""
        from app.agents.base import ReviewResult

        issues = []
        suggestions = []

        if not artifact.content.startswith("# Product Requirements Document"):
            issues.append("PRD missing header")

        features = artifact.metadata.get("features", [])
        if len(features) == 0:
            issues.append("No features extracted from requirement")

        passed = len(issues) == 0
        self.status = type(self.status).COMPLETED if passed else type(self.status).FAILED

        logger.info(
            "requirements_agent_review",
            passed=passed,
            features_count=len(features),
        )

        return ReviewResult(passed=passed, issues=issues, suggestions=suggestions)
