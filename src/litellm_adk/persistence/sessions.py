"""SessionStore implementations."""

from typing import Dict, List, Optional
from ..session.session import Session
from .base import SessionStore


class InMemorySessionStore(SessionStore):
    """In-memory session store."""

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    async def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    async def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def list_sessions(self, user_id: Optional[str] = None) -> List[Session]:
        if user_id:
            return [s for s in self._sessions.values() if s.user_id == user_id]
        return list(self._sessions.values())
