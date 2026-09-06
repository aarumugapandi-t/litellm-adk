"""Production ToolRegistry managing Tool definitions and lookups."""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Set, Union

from ..config.settings import settings
from ..observability.logger import adk_logger
from .base import Tool
from .permissions import ToolPermission


class ToolRegistry:
    """Registry for managing and discovering agent tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> Tool:
        """Directly registers a Tool instance."""
        self._tools[tool.name] = tool
        adk_logger.debug(f"Registered Tool instance: {tool.name}")
        return tool

    def register(
        self,
        name_or_func: Any = None,
        requires_approval: Union[bool, Callable[[Dict[str, Any]], bool]] = False,
        timeout: Optional[float] = None,
        error_policy: Optional[str] = None,
        permissions: Optional[Set[ToolPermission]] = None,
    ):
        """Decorator or function method to register a function as a Tool."""
        if callable(name_or_func):
            t = Tool(
                func=name_or_func,
                requires_approval=requires_approval,
                timeout=timeout,
                error_policy=error_policy,
                permissions=permissions,
            )
            self.register_tool(t)
            return name_or_func

        def decorator(func: Callable):
            tool_name = name_or_func if isinstance(name_or_func, str) else None
            t = Tool(
                func=func,
                name=tool_name,
                requires_approval=requires_approval,
                timeout=timeout,
                error_policy=error_policy,
                permissions=permissions,
            )
            self.register_tool(t)
            return func

        return decorator

    def get_tool(self, name: str) -> Optional[Tool]:
        """Retrieves a registered Tool instance by name."""
        return self._tools.get(name)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns OpenAPI schema definitions for all registered tools."""
        return [t.definition for t in self._tools.values()]

    def get_tool_definition(self, name: str) -> Optional[Dict[str, Any]]:
        """Returns OpenAPI schema definition for a specific tool by name."""
        t = self._tools.get(name)
        return t.definition if t else None

    def execute(self, name: str, **kwargs: Any) -> Any:
        """Synchronously executes a registered tool."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found in registry.")

        tool = self._tools[name]
        func = tool.func
        policy = tool.error_policy or settings.tool_error_policy

        try:
            if inspect.iscoroutinefunction(func):
                return asyncio.run(func(**kwargs))
            return func(**kwargs)
        except Exception as e:
            if policy == "return_to_llm":
                adk_logger.warning(f"Tool '{name}' failed (soft): {e}")
                return f"Error executing {name}: {str(e)}"
            raise e

    async def aexecute(self, name: str, **kwargs: Any) -> Any:
        """Asynchronously executes a registered tool with timeout and thread-offloading for sync functions."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found in registry.")

        tool = self._tools[name]
        func = tool.func
        timeout = tool.timeout or settings.tool_timeout
        policy = tool.error_policy or settings.tool_error_policy

        adk_logger.info(f"Executing tool (async): {name} [timeout={timeout}s]")

        try:
            if inspect.iscoroutinefunction(func):
                return await asyncio.wait_for(func(**kwargs), timeout=timeout)
            else:
                loop = asyncio.get_running_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(**kwargs)),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            err_msg = f"Tool '{name}' timed out after {timeout} seconds."
            adk_logger.error(err_msg)
            if policy == "return_to_llm":
                return err_msg
            raise TimeoutError(err_msg)
        except Exception as e:
            if policy == "return_to_llm":
                adk_logger.warning(f"Tool '{name}' failed (soft): {e}")
                return f"Error executing {name}: {str(e)}"
            raise e


# Global tool registry
tool_registry = ToolRegistry()
