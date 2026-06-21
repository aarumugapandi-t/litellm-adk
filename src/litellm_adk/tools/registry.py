import inspect
import json
import asyncio
from typing import Any, Callable, Dict, List, Optional, Type, Union
from pydantic import BaseModel, create_model
from ..observability.logger import adk_logger
from ..config.settings import settings

class ToolRegistry:
    """
    Production-grade Registry for managing and safely executing tools.
    Supports timeouts, error policies, and async/parallel execution.
    """
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, 
                 name_or_func: Any = None, 
                 requires_approval: Union[bool, Callable[[Dict[str, Any]], bool]] = False,
                 timeout: Optional[float] = None,
                 error_policy: Optional[str] = None):
        """
        Decorator to register a function as a tool.
        """
        if callable(name_or_func):
            self._register_function(name_or_func, requires_approval=requires_approval, timeout=timeout, error_policy=error_policy)
            return name_or_func

        def decorator(func: Callable):
            self._register_function(func, name_or_func, requires_approval=requires_approval, timeout=timeout, error_policy=error_policy)
            return func
        return decorator

    def _register_function(self, 
                           func: Callable, 
                           name: Optional[str] = None, 
                           description: Optional[str] = None, 
                           requires_approval: Union[bool, Callable[[Dict[str, Any]], bool]] = False,
                           timeout: Optional[float] = None,
                           error_policy: Optional[str] = None) -> Dict[str, Any]:
        """Internal helper to register a function and return its definition."""
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Tool: {tool_name}"
        
        # Simple schema generation
        sig = inspect.signature(func)
        parameters = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self": continue
            param_type = "string"
            if param.annotation == int: param_type = "integer"
            elif param.annotation == float: param_type = "number"
            elif param.annotation == bool: param_type = "boolean"
            
            parameters[param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}"
            }

        definition = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description.strip(),
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": [p.name for p in sig.parameters.values() if p.default == inspect.Parameter.empty and p.name != "self"]
                }
            }
        }
        
        self._tools[tool_name] = {
            "name": tool_name,
            "func": func,
            "definition": definition,
            "requires_approval": requires_approval,
            "timeout": timeout,
            "error_policy": error_policy
        }
        adk_logger.debug(f"Registered tool: {tool_name}")
        return definition

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [t["definition"] for t in self._tools.values()]

    def get_tool_definition(self, name: str) -> Optional[Dict[str, Any]]:
        if name in self._tools:
            return self._tools[name]["definition"]
        return None

    def execute(self, name: str, **kwargs) -> Any:
        """
        Synchronous execution of a tool. 
        Note: Limited timeout support for blocking synchronous functions.
        """
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found.")
            
        tool_meta = self._tools[name]
        func = tool_meta["func"]
        
        try:
            if inspect.iscoroutinefunction(func):
                return asyncio.run(func(**kwargs))
            return func(**kwargs)
        except Exception as e:
            policy = tool_meta.get("error_policy") or settings.tool_error_policy
            if policy == "return_to_llm":
                adk_logger.warning(f"Tool '{name}' failed (soft): {e}")
                return f"Error executing {name}: {str(e)}"
            raise e

    async def aexecute(self, name: str, **kwargs) -> Any:
        """
        Asynchronous tool execution with robust timeout and error handling.
        """
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found.")
            
        tool_meta = self._tools[name]
        func = tool_meta["func"]
        timeout = tool_meta.get("timeout") or settings.tool_timeout
        policy = tool_meta.get("error_policy") or settings.tool_error_policy
        
        adk_logger.info(f"Executing tool (async): {name} [timeout={timeout}s]")
        
        try:
            if inspect.iscoroutinefunction(func):
                # Use asyncio.wait_for for robust timeout
                return await asyncio.wait_for(func(**kwargs), timeout=timeout)
            else:
                # Offload blocking sync tools to a thread pool
                loop = asyncio.get_running_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(**kwargs)),
                    timeout=timeout
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
tool = tool_registry.register
