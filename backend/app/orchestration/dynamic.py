"""Dynamic Workflow Selector - chooses the right workflow based on project state.

Analyses the requirement and existing project to choose between:
- FULL_GREENFIELD: Project from scratch
- BROWNFIELD: Existing project with code files
- INCREMENTAL: Small change to an existing project

Inspired by the idea of "context-aware agent selection" from modern
multi-agent systems.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.core.logging import get_logger
from app.orchestration.workflows import (
    BROWNFIELD,
    FULL_GREENFIELD,
    INCREMENTAL,
    Workflow,
)

logger = get_logger(__name__)


class ProjectState(StrEnum):
    """Classification of the current project state."""

    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    INCREMENTAL = "incremental"
    UNKNOWN = "unknown"


@dataclass
class ProjectAnalysis:
    """Result of project analysis."""

    state: ProjectState
    has_code: bool
    has_git: bool
    has_database: bool
    file_count: int
    confidence: float
    recommendation: str


class ProjectAnalyzer:
    """Analyzes the project state to choose the right workflow."""

    def __init__(self, project_root: str = "./data/projects"):
        """Initialize analyzer with project root directory."""
        self.project_root = project_root

    def analyze(self, project_id: str | None = None, requirement: str = "") -> ProjectAnalysis:
        """Analyze project state.

        Args:
            project_id: Optional project directory to analyze
            requirement: User's natural language requirement

        Returns:
            Project analysis
        """
        from pathlib import Path

        has_code = False
        has_git = False
        has_database = False
        file_count = 0

        # Check project directory if exists
        if project_id:
            project_path = Path(self.project_root) / project_id
            if project_path.exists():
                # Count files
                all_files = list(project_path.rglob("*"))
                code_files = [
                    f
                    for f in all_files
                    if f.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json"}
                ]
                file_count = len(code_files)

                # Check for code files
                has_code = file_count > 0

                # Check for git
                has_git = (project_path / ".git").exists()

                # Check for database
                has_database = any(f.suffix in {".db", ".sqlite", ".sqlite3"} for f in all_files)

        # Determine state
        if not has_code:
            state = ProjectState.GREENFIELD
            confidence = 0.9
            recommendation = "Starting fresh project. Using full greenfield workflow."
        elif not has_git and has_code:
            state = ProjectState.BROWNFIELD
            confidence = 0.75
            recommendation = "Found code but no version control. Using brownfield workflow."
        elif has_code and has_git:
            state = ProjectState.INCREMENTAL
            confidence = 0.8
            recommendation = "Existing project found. Using incremental workflow."
        else:
            state = ProjectState.UNKNOWN
            confidence = 0.5
            recommendation = "Unable to determine state. Defaulting to full greenfield."

        # Nudge from requirement: if user says "new project", "from scratch", greenfield
        if requirement:
            req_lower = requirement.lower()
            if any(
                kw in req_lower
                for kw in ["新建", "从零", "from scratch", "新的项目", "new project"]
            ):
                state = ProjectState.GREENFIELD
                confidence = max(confidence, 0.85)
                recommendation = "User requested new project. Using full greenfield workflow."
            elif any(kw in req_lower for kw in ["添加", "加上", "增加", "add", "update", "修改"]):
                if has_code:
                    state = ProjectState.INCREMENTAL
                    confidence = 0.9
                    recommendation = "User requested a change to existing project."

        logger.info(
            "project_analysis_complete",
            state=state.value,
            has_code=has_code,
            has_git=has_git,
            file_count=file_count,
            confidence=confidence,
        )

        return ProjectAnalysis(
            state=state,
            has_code=has_code,
            has_git=has_git,
            has_database=has_database,
            file_count=file_count,
            confidence=confidence,
            recommendation=recommendation,
        )


class WorkflowSelector:
    """Selects the appropriate workflow based on project state."""

    def __init__(self, analyzer: ProjectAnalyzer | None = None):
        """Initialize with a project analyzer."""
        self.analyzer = analyzer or ProjectAnalyzer()

    def select(
        self,
        project_id: str | None = None,
        requirement: str = "",
    ) -> Workflow:
        """Select a workflow.

        Args:
            project_id: Optional project directory
            requirement: User's natural language requirement

        Returns:
            Selected Workflow
        """
        analysis = self.analyzer.analyze(project_id, requirement)

        if analysis.state == ProjectState.GREENFIELD:
            return FULL_GREENFIELD
        elif analysis.state == ProjectState.BROWNFIELD:
            return BROWNFIELD
        elif analysis.state == ProjectState.INCREMENTAL:
            return INCREMENTAL
        else:
            # Default to full greenfield for unknown
            return FULL_GREENFIELD

    def select_by_state(self, state: ProjectState) -> Workflow:
        """Select workflow by explicit state."""
        mapping = {
            ProjectState.GREENFIELD: FULL_GREENFIELD,
            ProjectState.BROWNFIELD: BROWNFIELD,
            ProjectState.INCREMENTAL: INCREMENTAL,
            ProjectState.UNKNOWN: FULL_GREENFIELD,
        }
        return mapping.get(state, FULL_GREENFIELD)


# Global instances
project_analyzer = ProjectAnalyzer()
workflow_selector = WorkflowSelector(project_analyzer)
