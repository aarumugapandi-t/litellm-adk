"""Dynamic Tool Synthesis, AST Security Validation, and Safe Sandbox Execution."""

from __future__ import annotations

import ast
import asyncio
import datetime
import json
import math
import re
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from ..exceptions import ToolError, ToolPermissionError
from ..observability.logger import adk_logger
from .base import Tool
from .permissions import ToolPermission


class DynamicToolParameter(BaseModel):
    """Parameter definition for a dynamic tool."""
    name: str
    type: str = "string"  # string, number, integer, boolean, object, array
    description: str = ""
    required: bool = True
    default: Optional[Any] = None


class DynamicToolSpec(BaseModel):
    """Specification for a dynamically generated tool."""
    id: str = Field(default_factory=lambda: f"tool_{int(time.time()*1000)}")
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    code: str
    version: int = 1
    permissions: List[str] = Field(default_factory=lambda: ["READ", "EXTERNAL"])
    timeout_seconds: float = 10.0
    approval_required: bool = False
    credential_requirements: List[str] = Field(default_factory=list)


class ToolExecutionResult(BaseModel):
    """Result of a dynamic tool test or runtime execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    stdout: Optional[str] = None


class ASTSecurityValidator:
    """Validates Python source code for malicious constructs and unsafe imports."""

    BLOCKED_MODULES = {
        "os", "sys", "subprocess", "shutil", "socket", "pty", "commands",
        "multiprocessing", "threading", "signal", "ctypes", "pickle", "shelve",
        "posix", "nt", "_thread", "posixpath", "ntpath", "pwd", "grp",
    }

    BLOCKED_CALLS = {
        "eval", "exec", "__import__", "compile", "breakpoint", "getattr",
        "setattr", "delattr", "memoryview", "globals", "locals", "vars",
    }

    ALLOWED_MODULES = {
        "json", "math", "re", "datetime", "random", "urllib.parse", "typing",
        "itertools", "functools", "collections", "string", "hashlib",
    }

    @classmethod
    def validate(cls, code_str: str) -> None:
        """Parses and inspects code AST. Raises ToolPermissionError if unsafe."""
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            raise ToolError(f"Syntax error in dynamic tool code: {e.msg} (line {e.lineno})") from e

        for node in ast.walk(tree):
            # Check import statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in cls.BLOCKED_MODULES:
                        raise ToolPermissionError(f"Blocked import of restricted module '{alias.name}' in dynamic tool.")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    if root_mod in cls.BLOCKED_MODULES:
                        raise ToolPermissionError(f"Blocked import of restricted module '{node.module}' in dynamic tool.")

            # Check for blocked function calls
            elif isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name and func_name in cls.BLOCKED_CALLS:
                    raise ToolPermissionError(f"Blocked call to restricted function '{func_name}()' in dynamic tool.")

            # Block dunder attribute access like __class__, __subclasses__, __globals__
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    raise ToolPermissionError(f"Blocked access to protected dunder attribute '{node.attr}' in dynamic tool.")


class SafeCodeSandbox:
    """Executes validated dynamic Python code within a restricted runtime scope."""

    SAFE_BUILTINS = {
        "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin,
        "bool": bool, "bytes": bytes, "bytearray": bytearray, "callable": callable,
        "chr": chr, "complex": complex, "dict": dict, "dir": dir, "divmod": divmod,
        "enumerate": enumerate, "filter": filter, "float": float, "format": format,
        "frozenset": frozenset, "hasattr": hasattr, "hash": hash, "hex": hex,
        "id": id, "int": int, "isinstance": isinstance, "issubclass": issubclass,
        "iter": iter, "len": len, "list": list, "map": map, "max": max,
        "min": min, "next": next, "oct": oct, "ord": ord, "pow": pow,
        "print": print, "range": range, "repr": repr, "reversed": reversed,
        "round": round, "set": set, "slice": slice, "sorted": sorted,
        "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
        "Exception": Exception, "ValueError": ValueError, "KeyError": KeyError,
        "TypeError": TypeError, "IndexError": IndexError, "RuntimeError": RuntimeError,
    }

    @classmethod
    async def execute(
        cls,
        code: str,
        entrypoint: str = "run",
        arguments: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 10.0,
    ) -> ToolExecutionResult:
        """Validates and executes dynamic tool code."""
        start_time = time.time()
        arguments = arguments or {}

        # 1. Security AST Analysis
        try:
            ASTSecurityValidator.validate(code)
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                error=f"Security check failed: {str(e)}",
                duration_seconds=round(time.time() - start_time, 4),
            )

        # 2. Build restricted execution namespace
        exec_namespace: Dict[str, Any] = {
            "__builtins__": cls.SAFE_BUILTINS,
            "json": json,
            "math": math,
            "re": re,
            "datetime": datetime,
            "time": time,
        }

        # 3. Compile and execute definitions
        try:
            compiled = compile(code, "<dynamic_tool>", "exec")
            exec(compiled, exec_namespace)
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                error=f"Compilation error: {str(e)}",
                duration_seconds=round(time.time() - start_time, 4),
            )

        # 4. Resolve entrypoint function
        target_fn = exec_namespace.get(entrypoint)
        if not target_fn or not callable(target_fn):
            # Fallback to first callable defined in namespace that is not built-in
            candidates = [
                v for k, v in exec_namespace.items()
                if callable(v) and k not in cls.SAFE_BUILTINS and k not in {"json", "math", "re", "datetime", "time"}
            ]
            if candidates:
                target_fn = candidates[0]
            else:
                return ToolExecutionResult(
                    success=False,
                    error=f"No callable entrypoint '{entrypoint}' found in tool source.",
                    duration_seconds=round(time.time() - start_time, 4),
                )

        # 5. Invoke target function with timeout
        try:
            loop = asyncio.get_event_loop()
            if asyncio.iscoroutinefunction(target_fn):
                result = await asyncio.wait_for(target_fn(**arguments), timeout=timeout_seconds)
            else:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: target_fn(**arguments)),
                    timeout=timeout_seconds,
                )

            return ToolExecutionResult(
                success=True,
                output=result,
                duration_seconds=round(time.time() - start_time, 4),
            )
        except asyncio.TimeoutError:
            return ToolExecutionResult(
                success=False,
                error=f"Tool execution timed out after {timeout_seconds} seconds.",
                duration_seconds=round(time.time() - start_time, 4),
            )
        except Exception as e:
            adk_logger.warning(f"Error executing dynamic tool '{entrypoint}': {e}")
            return ToolExecutionResult(
                success=False,
                error=f"Runtime error: {str(e)}",
                duration_seconds=round(time.time() - start_time, 4),
            )


def create_dynamic_tool_instance(spec: DynamicToolSpec) -> Tool:
    """Transforms a DynamicToolSpec into a callable ADK Tool object."""
    # Convert permissions strings to ToolPermission enum
    perms = set()
    for p in spec.permissions:
        try:
            perms.add(ToolPermission[p.upper()])
        except KeyError:
            perms.add(ToolPermission.EXTERNAL)

    # Normalize parameters to OpenAPI standard
    params = spec.parameters or {}
    if "type" not in params:
        properties = {}
        required = []
        for k, v in params.items():
            if isinstance(v, dict):
                properties[k] = v
                if v.get("required"):
                    required.append(k)
            else:
                properties[k] = {"type": "string", "description": str(v)}
        params = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    async def _dynamic_runner(**kwargs: Any) -> Any:
        res = await SafeCodeSandbox.execute(
            code=spec.code,
            arguments=kwargs,
            timeout_seconds=spec.timeout_seconds,
        )
        if not res.success:
            raise ToolError(f"Dynamic tool '{spec.name}' failed: {res.error}")
        return res.output

    return Tool(
        name=spec.name,
        description=spec.description,
        parameters=params,
        func=_dynamic_runner,
        permissions=perms,
        requires_approval=spec.approval_required,
        timeout=spec.timeout_seconds,
    )
