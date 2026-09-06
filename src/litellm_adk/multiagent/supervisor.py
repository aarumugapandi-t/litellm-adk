"""Supervisor pattern coordinating worker agents."""

from typing import Any, List, Optional
from ..agent.agent import Agent
from .agent_tool import agent_as_tool


class Supervisor(Agent):
    """Supervisor agent that orchestrates and delegates to a team of worker agents."""

    def __init__(
        self,
        agents: List[Agent],
        name: str = "Supervisor",
        system_prompt: str = "You are a supervisor coordinating worker agents. Delegate tasks to the appropriate worker.",
        **kwargs: Any,
    ):
        worker_tools = [agent_as_tool(ag) for ag in agents]
        tools = kwargs.pop("tools", []) or []
        tools.extend(worker_tools)

        super().__init__(
            name=name,
            system_prompt=system_prompt,
            tools=tools,
            **kwargs,
        )
        self.worker_agents = {ag.name: ag for ag in agents}
