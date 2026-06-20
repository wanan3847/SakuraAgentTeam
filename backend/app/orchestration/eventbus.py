"""EventBus for publishing and subscribing to workflow events.

Simple async event bus using a queue pattern with callback support.
Used to drive real-time frontend updates via Server-Sent Events.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """Types of events that can be published."""

    # Session lifecycle
    SESSION_STARTED = "session.started"
    SESSION_COMPLETED = "session.completed"
    SESSION_FAILED = "session.failed"

    # Agent lifecycle
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_LOG = "agent.log"

    # Artifact / output
    ARTIFACT_CREATED = "artifact.created"
    FILE_UPDATED = "file.updated"

    # Experience
    EXPERIENCE_RECORDED = "experience.recorded"


@dataclass
class Event:
    """A single event in the bus."""

    event_type: str
    session_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transmission."""
        return {
            "event_id": self.event_id,
            "type": self.event_type,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


EventCallback = Callable[[Event], Awaitable[None]]


class EventBus:
    """Async event bus with pub/sub pattern.

    Supports:
    - Per-session subscriptions
    - Wildcard subscriptions (e.g., "agent.*")
    - Event history (ring buffer per session)
    - SSE streaming for frontend
    """

    def __init__(self, max_history: int = 100):
        """Initialize event bus.

        Args:
            max_history: Max events to keep in history per session
        """
        self._callbacks: Dict[str, List[EventCallback]] = {}
        self._wildcard_callbacks: List[EventCallback] = []
        self._session_history: Dict[str, List[Event]] = {}
        self._max_history = max_history
        self._queues: Dict[str, asyncio.Queue] = {}  # For SSE streaming
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, callback: EventCallback) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        """Subscribe to all events (wildcard)."""
        self._wildcard_callbacks.append(callback)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        async with self._lock:
            # Store in history
            sid = event.session_id
            if sid not in self._session_history:
                self._session_history[sid] = []
            self._session_history[sid].append(event)
            if len(self._session_history[sid]) > self._max_history:
                self._session_history[sid] = self._session_history[sid][-self._max_history:]

            # Push to SSE queue if exists
            if sid in self._queues:
                self._queues[sid].put_nowait(event)

        # Fire callbacks (outside lock)
        callbacks = list(self._callbacks.get(event.event_type, []))
        callbacks.extend(self._wildcard_callbacks)

        for cb in callbacks:
            try:
                await cb(event)
            except Exception as e:
                logger.error("event_callback_error", error=str(e), callback=str(cb))

        logger.debug(
            "event_published",
            event_type=event.event_type,
            session_id=event.session_id,
        )

    async def publish_log(
        self,
        session_id: str,
        agent_role: str,
        message: str,
        level: str = "info",
    ) -> None:
        """Shortcut to publish an AGENT_LOG event."""
        await self.publish(Event(
            event_type=EventType.AGENT_LOG.value,
            session_id=session_id,
            payload={
                "agent_role": agent_role,
                "message": message,
                "level": level,
            },
        ))

    def get_history(self, session_id: str) -> List[Event]:
        """Get event history for a session."""
        return list(self._session_history.get(session_id, []))

    def create_stream_queue(self, session_id: str) -> asyncio.Queue:
        """Create/retrieve a queue for SSE streaming."""
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]

    def close_stream(self, session_id: str) -> None:
        """Close and cleanup a stream queue."""
        if session_id in self._queues:
            del self._queues[session_id]


# Global event bus instance
event_bus = EventBus()
