"""Multi-agent abstractions: AgentTool, AgentTeam, and Supervisor."""

from .agent_tool import AgentTool, agent_as_tool
from .supervisor import Supervisor
from .team import AgentTeam

__all__ = [
    "AgentTool",
    "agent_as_tool",
    "AgentTeam",
    "Supervisor",
]
