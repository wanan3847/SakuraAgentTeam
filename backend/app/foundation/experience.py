"""Experience Store - stores and retrieves error patterns using ChromaDB.

The experience store allows agents to:
1. Record successful solutions to errors that occurred
2. Query past experiences by error message
3. Use accumulated knowledge to avoid repeating mistakes

Storage: ChromaDB vector database for semantic similarity search
Fallback: SQLite keyword search if ChromaDB unavailable

Reference: Neat-Freak pattern - sessions accumulate experience,
useful knowledge is graduated to persistent storage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string with timezone info."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Experience:
    """A single experience / error pattern."""

    id: str
    error_type: str           # e.g., "ImportError", "ConnectionError"
    error_message: str        # Full error message
    context: Dict[str, str]   # Context: agent_role, task_type, project_type
    attempted_fixes: List[str] = field(default_factory=list)
    final_solution: str = ""
    success: bool = True
    user_rating: int = 3
    occurrence_count: int = 1
    status: str = "active"
    created_at: str = field(default_factory=_utcnow_iso)
    graduated_at: Optional[str] = None


class ExperienceStore:
    """Vector-based experience store.

    Uses ChromaDB for semantic similarity search so that similar errors
    (even with different wording or variable names) can be matched.

    If ChromaDB is not installed, falls back to keyword-based SQLite search.
    """

    def __init__(self, persist_directory: str = "./data/experience_db"):
        """Initialize the experience store.

        Args:
            persist_directory: Path to ChromaDB persistence directory
        """
        self.persist_directory = persist_directory
        self._experiences: List[Experience] = []
        self._client = None
        self._collection = None

        self._initialize()

    def _initialize(self) -> None:
        """Initialize ChromaDB or fall back to keyword search."""
        try:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(path=self.persist_directory)
            self._collection = self._client.get_or_create_collection("sakura_experiences")
            logger.info("experience_store_chroma_initialized", path=self.persist_directory)
        except ImportError:
            logger.warning("chromadb_not_available_fallback_keyword")
        except Exception as e:
            logger.warning("chromadb_init_failed", error=str(e))

        # Always load in-memory list for fallback
        self._load_from_memory()

    def _load_from_memory(self) -> None:
        """Load experiences from a JSON file if available."""
        import json
        from pathlib import Path

        data_path = Path(self.persist_directory) / "experiences.json"
        if data_path.exists():
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    self._experiences.append(Experience(**item))
                logger.info(
                    "experiences_loaded_from_json",
                    count=len(self._experiences),
                )
            except Exception as e:
                logger.warning("experience_load_failed", error=str(e))

    def _save_to_memory(self) -> None:
        """Save experiences to JSON file."""
        import json
        from pathlib import Path

        data_path = Path(self.persist_directory) / "experiences.json"
        data_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [exp.__dict__ for exp in self._experiences]
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("experience_save_failed", error=str(e))

    def add_experience(
        self,
        error_message: str,
        error_type: str,
        context: Dict[str, str],
        final_solution: str,
        success: bool = True,
    ) -> str:
        """Record a new experience.

        Args:
            error_message: The error that occurred
            error_type: Classification of the error
            context: Where/How the error occurred
            final_solution: How it was fixed
            success: Whether the fix worked

        Returns:
            experience ID
        """
        from uuid import uuid4

        exp_id = uuid4().hex[:12]

        exp = Experience(
            id=exp_id,
            error_type=error_type,
            error_message=error_message,
            context=context,
            final_solution=final_solution,
            success=success,
        )

        self._experiences.append(exp)
        self._save_to_memory()

        # Add to ChromaDB for vector search
        if self._collection is not None:
            try:
                doc = f"{error_type}: {error_message}\nContext: {context}\nSolution: {final_solution}"
                self._collection.add(
                    documents=[doc],
                    metadatas=[{
                        "error_type": error_type,
                        "agent_role": context.get("agent_role", ""),
                        "success": str(success),
                    }],
                    ids=[exp_id],
                )
            except Exception as e:
                logger.warning("chroma_add_failed", error=str(e))

        logger.info(
            "experience_recorded",
            exp_id=exp_id,
            error_type=error_type,
        )

        return exp_id

    def search_similar(
        self,
        error_message: str,
        context: Optional[Dict[str, str]] = None,
        top_k: int = 5,
    ) -> List[Experience]:
        """Search for similar past experiences.

        Args:
            error_message: Current error message
            context: Optional context to filter by
            top_k: Max results to return

        Returns:
            List of matching experiences (most similar first)
        """
        if not self._experiences:
            return []

        # Try vector search first
        if self._collection is not None:
            try:
                results = self._collection.query(
                    query_texts=[error_message],
                    n_results=min(top_k, len(self._experiences)),
                )

                ids = results.get("ids", [[]])[0]
                matches = []
                for exp_id in ids:
                    match = next((e for e in self._experiences if e.id == exp_id), None)
                    if match and match.status == "active":
                        matches.append(match)
                return matches[:top_k]

            except Exception as e:
                logger.debug("chroma_search_failed_fallback_keyword", error=str(e))

        # Fallback: keyword-based matching
        return self._keyword_search(error_message, context, top_k)

    def _keyword_search(
        self,
        error_message: str,
        context: Optional[Dict[str, str]],
        top_k: int,
    ) -> List[Experience]:
        """Simple keyword-based fallback search."""
        import re

        # Extract keywords from error message (words of 4+ chars)
        keywords = set(re.findall(r'\b\w{4,}\b', error_message.lower()))
        if not keywords:
            return self._experiences[:top_k]

        scored = []
        for exp in self._experiences:
            if exp.status != "active":
                continue

            error_lower = exp.error_message.lower()
            score = sum(1 for kw in keywords if kw in error_lower)

            # Context matching bonus
            if context:
                for key, value in context.items():
                    if exp.context.get(key) == value:
                        score += 2

            if score > 0:
                scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:top_k]]

    def mark_rating(self, experience_id: str, rating: int) -> bool:
        """Update user rating for an experience.

        Args:
            experience_id: Experience to update
            rating: 1-5 rating

        Returns:
            True if updated
        """
        exp = next((e for e in self._experiences if e.id == experience_id), None)
        if not exp:
            return False

        exp.user_rating = max(1, min(5, rating))
        self._save_to_memory()

        # Check if it should graduate (rating 5 and appeared 3+ times)
        if exp.user_rating == 5 and exp.occurrence_count >= 3:
            exp.status = "graduated"
            exp.graduated_at = _utcnow_iso()
            self._save_to_memory()
            logger.info("experience_graduated", exp_id=experience_id)

        return True

    def increment_occurrence(self, experience_id: str) -> None:
        """Increment occurrence counter when an experience is referenced."""
        exp = next((e for e in self._experiences if e.id == experience_id), None)
        if exp:
            exp.occurrence_count += 1
            self._save_to_memory()

    def graduate(self, experience_id: str) -> bool:
        """Manually graduate an experience to persistent knowledge."""
        exp = next((e for e in self._experiences if e.id == experience_id), None)
        if not exp:
            return False

        exp.status = "graduated"
        exp.graduated_at = _utcnow_iso()
        self._save_to_memory()
        return True

    def get_graduated(self) -> List[Experience]:
        """Get all graduated (persistent) experiences."""
        return [e for e in self._experiences if e.status == "graduated"]

    def count(self) -> Dict[str, int]:
        """Get count statistics."""
        return {
            "total": len(self._experiences),
            "active": sum(1 for e in self._experiences if e.status == "active"),
            "graduated": sum(1 for e in self._experiences if e.status == "graduated"),
        }


# Global experience store instance
experience_store = ExperienceStore()
