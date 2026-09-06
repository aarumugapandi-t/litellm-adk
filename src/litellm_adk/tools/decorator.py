"""Tool decorator for convenient tool definition."""

from typing import Any, Callable, Dict, Optional, Set, Union, overload

from .base import Tool
from .permissions import ToolPermission


@overload
def tool(func: Callable) -> Tool:
    ...


@overload
def tool(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    permissions: Optional[Set[ToolPermission]] = None,
    requires_approval: Union[bool, Callable[[Dict[str, Any]], bool]] = False,
    timeout: Optional[float] = None,
    retry_policy: Optional[Any] = None,
    error_policy: Optional[str] = None,
) -> Callable[[Callable], Tool]:
    ...


def tool(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    permissions: Optional[Set[ToolPermission]] = None,
    requires_approval: Union[bool, Callable[[Dict[str, Any]], bool]] = False,
    timeout: Optional[float] = None,
    retry_policy: Optional[Any] = None,
    error_policy: Optional[str] = None,
) -> Union[Tool, Callable[[Callable], Tool]]:
    """Decorator to define a Tool with safety metadata and automatic schema inference."""

    def decorator(target_func: Callable) -> Tool:
        tool_instance = Tool(
            func=target_func,
            name=name,
            description=description,
            parameters=parameters,
            permissions=permissions,
            requires_approval=requires_approval,
            timeout=timeout,
            retry_policy=retry_policy,
            error_policy=error_policy,
        )
        # Import lazily to avoid circular imports
        from .registry import tool_registry

        tool_registry.register_tool(tool_instance)
        return tool_instance

    if func is not None and callable(func):
        return decorator(func)

    return decorator
