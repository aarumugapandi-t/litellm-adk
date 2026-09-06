"""ToolExecutor governing safe tool dispatch, permissions, approvals, and error containment."""

import asyncio
import inspect
import json
import time
from typing import Any, Callable, Dict, List, Optional, Set

from ..exceptions import ToolError, ToolPermissionError, ToolTimeoutError
from ..observability.logger import adk_logger
from .base import Tool
from .permissions import ToolPermission
from .registry import ToolRegistry


class ToolExecutor:
    """Executes tools adhering to permissions, approval requirements, timeouts, and error policies."""

    def __init__(
        self,
        registry: ToolRegistry,
        allowed_permissions: Optional[Set[ToolPermission]] = None,
        default_timeout: float = 30.0,
        default_error_policy: str = "return_to_llm",
    ):
        self.registry = registry
        self.allowed_permissions = allowed_permissions or {
            ToolPermission.READ,
            ToolPermission.WRITE,
            ToolPermission.EXTERNAL,
            ToolPermission.DANGEROUS,
        }
        self.default_timeout = default_timeout
        self.default_error_policy = default_error_policy

    def parse_arguments(self, raw_args: Any) -> Dict[str, Any]:
        """Parses tool call arguments from JSON string or dict."""
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            clean_str = raw_args.strip()
            if not clean_str:
                return {}
            try:
                return json.loads(clean_str)
            except json.JSONDecodeError as e:
                adk_logger.warning(f"Failed to parse tool call arguments '{raw_args}': {e}")
                return {"raw_arg": raw_args}
        return {}

    async def execute_tool_call(
        self,
        tool_name: str,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_approval_check: Optional[Callable[[str, str, Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        """Executes a single tool call through the safe execution pipeline.

        Returns a dictionary formatted as an OpenAI tool response message:
        {"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": ...}
        """
        start_time = time.time()
        tool = self.registry.get_tool(tool_name)

        if not tool:
            err_msg = f"Tool '{tool_name}' not found."
            adk_logger.error(err_msg)
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": f"Error: {err_msg}",
            }

        # 1. Permission check
        for perm in tool.permissions:
            if perm not in self.allowed_permissions:
                err_msg = f"Permission denied for tool '{tool_name}'. Requires permission '{perm.value}'."
                adk_logger.error(err_msg)
                raise ToolPermissionError(err_msg, tool_name=tool_name, permission=perm.value)

        # 2. Human approval check
        if on_approval_check and tool.check_approval_required(arguments):
            # Await approval or trigger approval requirement
            arguments = await on_approval_check(tool_name, tool_call_id, arguments) or arguments

        # 3. Execution with timeout
        timeout = tool.timeout or self.default_timeout
        error_policy = tool.error_policy or self.default_error_policy

        try:
            func = tool.func
            if tool.is_async:
                result = await asyncio.wait_for(func(**arguments), timeout=timeout)
            else:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(**arguments)),
                    timeout=timeout,
                )

            # Format result string
            if isinstance(result, (dict, list)):
                content_str = json.dumps(result)
            else:
                content_str = str(result)

            duration = time.time() - start_time
            adk_logger.info(f"Tool '{tool_name}' completed in {duration:.3f}s")

            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": content_str,
            }

        except asyncio.TimeoutError as e:
            duration = time.time() - start_time
            err_msg = f"Tool '{tool_name}' timed out after {timeout} seconds."
            adk_logger.error(err_msg)
            if error_policy == "return_to_llm":
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": f"Error: {err_msg}",
                }
            raise ToolTimeoutError(err_msg, tool_name=tool_name, timeout=timeout) from e

        except Exception as e:
            duration = time.time() - start_time
            err_msg = f"Error executing tool '{tool_name}': {str(e)}"
            adk_logger.error(err_msg)
            if error_policy == "return_to_llm":
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": err_msg,
                }
            raise ToolError(err_msg, tool_name=tool_name, tool_call_id=tool_call_id) from e
