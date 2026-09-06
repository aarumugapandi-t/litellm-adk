"""Persistence protocols for sessions and agent runs."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from ..session.session import Session
from ..agent.result import AgentResult


@runtime_checkable
class SessionStore(Protocol):
    """Protocol for persisting conversational session state."""

    async def get(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by its ID."""
        ...

    async def save(self, session: Session) -> None:
        """Persist or update a session."""
        ...

    async def delete(self, session_id: str) -> None:
        """Remove a session."""
        ...

    async def list_sessions(self, user_id: Optional[str] = None) -> List[Session]:
        """List active sessions, optionally filtered by user ID."""
        ...


@runtime_checkable
class RunStore(Protocol):
    """Protocol for logging and persisting agent execution results."""

    async def save_run(self, result: AgentResult) -> None:
        """Persist an agent execution result."""
        ...

    async def get_run(self, run_id: str) -> Optional[AgentResult]:
        """Retrieve an execution result by run ID."""
        ...
