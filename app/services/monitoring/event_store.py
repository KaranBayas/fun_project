from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.models.monitoring_schemas import SecurityEventRequest


class BaseEventStore(ABC):
    """Abstract interface for storing security events.

    This abstraction allows replacing the storage backend in the future with
    PostgreSQL, OpenSearch, Qdrant, or another data store.
    """

    @abstractmethod
    async def save_event(self, event: SecurityEventRequest) -> SecurityEventRequest:
        """Save a security event into the store."""
        pass

    @abstractmethod
    async def get_event(self, event_id: str) -> Optional[SecurityEventRequest]:
        """Retrieve a security event by event_id."""
        pass

    @abstractmethod
    async def list_events(self, limit: int = 100) -> List[SecurityEventRequest]:
        """List recently recorded events."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored events."""
        pass


class InMemoryEventStore(BaseEventStore):
    """In-memory prototype event store implementation."""

    def __init__(self) -> None:
        self._events: Dict[str, SecurityEventRequest] = {}

    async def save_event(self, event: SecurityEventRequest) -> SecurityEventRequest:
        if event.event_id:
            self._events[event.event_id] = event
        return event

    async def get_event(self, event_id: str) -> Optional[SecurityEventRequest]:
        return self._events.get(event_id)

    async def list_events(self, limit: int = 100) -> List[SecurityEventRequest]:
        return list(self._events.values())[:limit]

    async def clear(self) -> None:
        self._events.clear()
