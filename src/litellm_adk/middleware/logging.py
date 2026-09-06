"""Logging middleware recording execution start, completion, and error states."""

import time
from typing import Any, Dict

from ..observability.logger import adk_logger
from .base import Middleware


class LoggingMiddleware(Middleware):
    """Logs life-cycle checkpoints of agent runs."""

    def __init__(self, prefix: str = "AgentRun"):
        self.prefix = prefix

    async def before_run(self, context: Dict[str, Any]) -> None:
        agent_name = context.get("agent_name", "Agent")
        prompt = context.get("prompt", "")
        context["_start_time"] = time.time()
        adk_logger.info(f"[{self.prefix}] {agent_name} started execution: '{prompt[:100]}...'")

    async def after_run(self, context: Dict[str, Any], result: Any) -> None:
        elapsed = time.time() - context.get("_start_time", time.time())
        agent_name = context.get("agent_name", "Agent")
        adk_logger.info(f"[{self.prefix}] {agent_name} finished in {elapsed:.3f}s")

    async def on_error(self, context: Dict[str, Any], error: Exception) -> None:
        agent_name = context.get("agent_name", "Agent")
        adk_logger.error(f"[{self.prefix}] {agent_name} encountered error: {error}")
