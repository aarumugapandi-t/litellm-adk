"""AgentTeam coordination of specialized agents."""

from typing import Dict, List, Optional, Any
from ..agent.agent import Agent
from .agent_tool import agent_as_tool


class AgentTeam:
    """Manages a roster of specialized agents operating collectively."""

    def __init__(self, agents: Optional[List[Agent]] = None):
        self._agents: Dict[str, Agent] = {}
        if agents:
            for ag in agents:
                self.add_agent(ag)

    def add_agent(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def get_agent(self, name: str) -> Optional[Agent]:
        return self._agents.get(name)

    def get_tools(self) -> List[Any]:
        """Returns each team member wrapped as a Tool."""
        return [agent_as_tool(ag) for ag in self._agents.values()]
