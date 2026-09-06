"""Base protocols and abstract classes for memory backends."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class BaseMemory(ABC):
    """Abstract Base Class for asynchronous memory persistence."""

    @abstractmethod
    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all messages for a given session."""
        pass

    @abstractmethod
    async def add_message(self, session_id: str, message: Dict[str, Any]):
        """Add a single message to a session."""
        pass

    @abstractmethod
    async def add_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        """Add multiple messages to a session."""
        pass

    @abstractmethod
    async def clear(self, session_id: str):
        """Clear history for a session."""
        pass

    @abstractmethod
    async def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """Retrieve metadata/state for a given session."""
        pass

    @abstractmethod
    async def save_session_metadata(self, session_id: str, metadata: Dict[str, Any]):
        """Save/Update metadata/state for a given session."""
        pass

    async def close(self):
        """Optional cleanup for database connections."""
        pass


@runtime_checkable
class MemoryStore(Protocol):
    """Protocol for pluggable generic key/value and semantic memory storage."""

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve an item by key."""
        ...

    async def add(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store an item."""
        ...

    async def update(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update an existing item."""
        ...

    async def delete(self, key: str) -> None:
        """Delete an item by key."""
        ...

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memory entries relevant to query."""
        ...
