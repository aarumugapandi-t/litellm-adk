from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseMemory(ABC):
    """
    Abstract Base Class for asynchronous memory persistence.
    """
    
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
