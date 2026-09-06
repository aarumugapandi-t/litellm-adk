"""Tool wrapper enabling an Agent to be invoked as a tool by another Agent."""

from typing import Any, Dict, Optional

from ..agent.agent import Agent
from ..tools.base import Tool
from ..tools.permissions import ToolPermission


def agent_as_tool(
    agent: Agent,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Tool:
    """Wraps an Agent instance into an executable Tool."""
    tool_name = name or agent.name.lower().replace(" ", "_")
    tool_desc = description or (f"{agent.name}: {agent.description}" if agent.description else f"Delegate tasks to {agent.name}")

    async def _delegate(query: str) -> str:
        result = await agent.run(query)
        return result.text

    return Tool(
        func=_delegate,
        name=tool_name,
        description=tool_desc,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": f"The specific task or prompt to delegate to {agent.name}.",
                }
            },
            "required": ["query"],
        },
        permissions={ToolPermission.EXTERNAL},
    )


class AgentTool(Tool):
    """Class wrapper representing an Agent exposed as a Tool."""

    def __init__(self, agent: Agent, name: Optional[str] = None, description: Optional[str] = None):
        wrapped = agent_as_tool(agent, name=name, description=description)
        super().__init__(
            func=wrapped.func,
            name=wrapped.name,
            description=wrapped.description,
            parameters=wrapped.definition["function"]["parameters"],
            permissions=wrapped.permissions,
        )
        self.agent = agent
