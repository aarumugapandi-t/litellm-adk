"""Conversation memory management for multi-turn dialogues."""

from typing import Any, Dict, List, Optional

from .base import BaseMemory
from .in_memory import InMemoryMemory


class ConversationMemory:
    """Manages multi-turn conversation messages across user, assistant, and tool turns."""

    def __init__(self, backend: Optional[BaseMemory] = None):
        self.backend: BaseMemory = backend or InMemoryMemory()

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all messages for a session."""
        return await self.backend.get_messages(session_id)

    async def add_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """Add a single message."""
        await self.backend.add_message(session_id, message)

    async def add_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Add multiple messages."""
        await self.backend.add_messages(session_id, messages)

    async def add_user_message(self, session_id: str, content: str) -> None:
        """Add a user message."""
        await self.add_message(session_id, {"role": "user", "content": content})

    async def add_assistant_message(
        self,
        session_id: str,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add an assistant message with optional tool calls."""
        msg: Dict[str, Any] = {"role": "assistant"}
        if content is not None:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        await self.add_message(session_id, msg)

    async def add_tool_message(self, session_id: str, tool_call_id: str, name: str, content: str) -> None:
        """Add a tool return message."""
        await self.add_message(
            session_id,
            {"role": "tool", "tool_call_id": tool_call_id, "name": name, "content": content},
        )

    async def clear(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        await self.backend.clear(session_id)

    async def close(self) -> None:
        """Close backend connection."""
        await self.backend.close()
