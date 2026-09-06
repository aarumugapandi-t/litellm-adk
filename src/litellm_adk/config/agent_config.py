"""Backward compatibility redirect for AgentConfig."""

from ..agent.config import AgentConfig, ExecutionConfig

__all__ = ["AgentConfig", "ExecutionConfig"]
