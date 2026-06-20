"""Project repository management using Git.

Wraps GitPython to provide atomic, structured version control
for project artifacts produced by agents. Every meaningful state
change (PRD committed, design finalized, code generated, tests
passed) is recorded as a separate commit so the user can
inspect and roll back to any point in time.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


# Lazy import: GitPython may not be installed in dev environments
try:
    from git import Actor, Repo

    _GITPYTHON_AVAILABLE = True
except Exception:  # pragma: no cover - optional dep
    _GITPYTHON_AVAILABLE = False


class GitRepoError(Exception):
    """Raised when a git operation fails."""


class ProjectRepo:
    """Wrapper around a Git repository for a single project.

    The repository is a self-contained directory under
    ``<projects_root>/<project_id>`` containing all artifacts
    produced by the agents.
    """

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path).resolve()
        self._repo: Repo | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def init(self, user_name: str = "Sakura Agent", user_email: str = "agent@sakura.local") -> None:
        """Initialize a new git repository if one doesn't exist.

        Also performs an initial commit on a fresh repo so subsequent
        ``commit()`` calls have a valid ``HEAD`` to diff against.
        """
        if not _GITPYTHON_AVAILABLE:
            logger.warning("gitpython_unavailable_skip_init", path=str(self.path))
            return
        self.path.mkdir(parents=True, exist_ok=True)
        if (self.path / ".git").exists():
            self._repo = Repo(self.path)
        else:
            self._repo = Repo.init(self.path)
        self._set_identity(user_name, user_email)
        self._ensure_gitignore()

        # Ensure there is at least one commit so HEAD exists
        try:
            has_head = bool(self._repo.heads)
        except Exception:
            has_head = False
        if not has_head:
            self._initial_commit()
        logger.info("project_repo_initialized", path=str(self.path))

    def _initial_commit(self) -> None:
        """Create the first empty commit so HEAD points somewhere."""
        if not self._repo:
            return
        try:
            actor = Actor("Sakura Agent", "agent@sakura.local")
            self._repo.index.commit(
                "Initial commit — Sakura Agent scaffold",
                author=actor,
                committer=actor,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("git_initial_commit_failed", error=str(exc))

    def _set_identity(self, name: str, email: str) -> None:
        if self._repo is None:
            return
        try:
            with self._repo.config_writer() as cfg:
                cfg.set_value("user", "name", name)
                cfg.set_value("user", "email", email)
        except Exception as exc:  # pragma: no cover - non-fatal
            logger.warning("git_set_identity_failed", error=str(exc))

    def _ensure_gitignore(self) -> None:
        gitignore = self.path / ".gitignore"
        if gitignore.exists():
            return
        gitignore.write_text(
            "\n".join(
                [
                    "# Python",
                    "__pycache__/",
                    "*.pyc",
                    ".pytest_cache/",
                    ".venv/",
                    "node_modules/",
                    "dist/",
                    "build/",
                    ".next/",
                    "# Env",
                    ".env",
                    ".env.local",
                    "# IDE",
                    ".vscode/",
                    ".idea/",
                    "# OS",
                    ".DS_Store",
                    "",
                ]
            )
        )

    @property
    def repo(self) -> Repo | None:
        return self._repo

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    def history(self, max_count: int = 50) -> list[dict]:
        """Return list of recent commits, newest first."""
        if not self._repo:
            return []
        commits: list[dict] = []
        try:
            for c in self._repo.iter_commits(max_count=max_count):
                commits.append(
                    {
                        "sha": c.hexsha,
                        "short_sha": c.hexsha[:7],
                        "message": c.message.strip(),
                        "author": str(c.author),
                        "timestamp": c.committed_datetime.isoformat(),
                    }
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("git_history_failed", error=str(exc))
        return commits

    def status(self) -> dict:
        """Return the working tree status."""
        if not self._repo:
            return {"untracked": [], "modified": [], "staged": []}
        try:
            return {
                "untracked": [item.path for item in self._repo.untracked_files],
                "modified": [item.a_path for item in self._repo.index.diff(None)],
                "staged": [item.a_path for item in self._repo.index.diff("HEAD")],
            }
        except Exception as exc:  # pragma: no cover
            return {"untracked": [], "modified": [], "staged": [], "error": str(exc)}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    def commit(
        self,
        message: str,
        paths: list[str] | None = None,
        author_name: str = "Sakura Agent",
        author_email: str = "agent@sakura.local",
    ) -> str | None:
        """Stage and commit changes. Returns commit SHA on success."""
        if not self._repo:
            logger.warning("git_commit_skipped_no_repo")
            return None
        try:
            # Stage paths (or all changes)
            if paths:
                self._repo.index.add(paths)
            else:
                self._repo.git.add(A=True)

            # Skip if nothing to commit AND we have a HEAD (compare to HEAD)
            if self._repo.heads:
                if not self._repo.index.diff("HEAD") and not self._repo.untracked_files:
                    logger.debug("git_commit_skipped_no_changes", message=message)
                    return None

            author = Actor(author_name, author_email)
            commit = self._repo.index.commit(message, author=author, committer=author)
            sha = commit.hexsha
            logger.info("git_commit_created", sha=sha[:7], message=message)
            return sha
        except Exception as exc:
            logger.error("git_commit_failed", error=str(exc))
            return None

    def rollback(self, target_sha: str) -> bool:
        """Hard reset the working tree to a previous commit."""
        if not self._repo:
            return False
        try:
            self._repo.git.reset("--hard", target_sha)
            logger.info("git_rollback", target=target_sha[:7])
            return True
        except Exception as exc:
            logger.error("git_rollback_failed", error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Async wrappers (call from inside asyncio code)
    # ------------------------------------------------------------------
    async def ainit(self, **kwargs) -> None:
        await asyncio.to_thread(self.init, **kwargs)

    async def acommit(self, message: str, **kwargs) -> str | None:
        return await asyncio.to_thread(self.commit, message, **kwargs)

    async def ahistory(self, max_count: int = 50) -> list[dict]:
        return await asyncio.to_thread(self.history, max_count)


def open_or_create(projects_root: str, project_id: str) -> ProjectRepo:
    """Convenience factory: open or create the repo for a project."""
    repo = ProjectRepo(Path(projects_root) / project_id)
    repo.init()
    return repo
