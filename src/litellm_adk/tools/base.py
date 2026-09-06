"""First-class Tool abstraction with automatic schema inference."""

import inspect
from typing import Any, Callable, Dict, List, Optional, Set, Union
from pydantic import BaseModel

from .permissions import ToolPermission


def _python_type_to_json_type(annotation: Any) -> str:
    """Maps Python types to OpenAPI/JSON schema types."""
    if annotation == int:
        return "integer"
    if annotation == float:
        return "number"
    if annotation == bool:
        return "boolean"
    if annotation in (list, List) or getattr(annotation, "__origin__", None) in (list, List):
        return "array"
    if annotation in (dict, Dict) or getattr(annotation, "__origin__", None) in (dict, Dict):
        return "object"
    return "string"


def generate_tool_schema(func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """Generates an LLM-compatible OpenAPI function calling schema from a callable."""
    tool_name = name or func.__name__
    tool_description = description or func.__doc__ or f"Tool: {tool_name}"

    sig = inspect.signature(func)
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        param_type = _python_type_to_json_type(param.annotation)
        prop: Dict[str, Any] = {
            "type": param_type,
            "description": f"Parameter {param_name}",
        }

        # If annotation is a Pydantic model
        if inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel):
            prop = param.annotation.model_json_schema()

        properties[param_name] = prop

        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description.strip(),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


class Tool:
    """First-class Tool abstraction encapsulating metadata, safety policies, and execution."""

    def __init__(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        permissions: Optional[Set[ToolPermission]] = None,
        requires_approval: Union[bool, Callable[[Dict[str, Any]], bool]] = False,
        timeout: Optional[float] = None,
        retry_policy: Optional[Any] = None,
        error_policy: Optional[str] = None,
    ):
        self.func = func
        self.name = name or func.__name__
        self.description = (description or func.__doc__ or f"Tool: {self.name}").strip()
        self.permissions = permissions or {ToolPermission.READ}
        self.requires_approval = requires_approval
        self.timeout = timeout
        self.retry_policy = retry_policy
        self.error_policy = error_policy

        if parameters is not None:
            self._definition = {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": parameters,
                },
            }
        else:
            self._definition = generate_tool_schema(func, name=self.name, description=self.description)

    @property
    def definition(self) -> Dict[str, Any]:
        """Returns the OpenAI/LiteLLM tool specification dictionary."""
        return self._definition

    @property
    def is_async(self) -> bool:
        """Returns True if the underlying function is a coroutine function."""
        return inspect.iscoroutinefunction(self.func)

    def check_approval_required(self, arguments: Dict[str, Any]) -> bool:
        """Evaluates whether this tool execution requires human approval."""
        if isinstance(self.requires_approval, bool):
            return self.requires_approval
        if callable(self.requires_approval):
            return self.requires_approval(arguments)
        return False

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"Tool(name='{self.name}', async={self.is_async}, permissions={[p.value for p in self.permissions]})"
