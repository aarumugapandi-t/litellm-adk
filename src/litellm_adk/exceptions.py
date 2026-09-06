"""Explicit framework exceptions hierarchy for LiteLLM ADK."""

from typing import Any, Dict, Optional


class AgentError(Exception):
    """Base exception for all agent framework errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ModelError(AgentError):
    """Raised when an LLM provider call fails."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if model:
            details["model"] = model
        if provider:
            details["provider"] = provider
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details)
        self.model = model
        self.provider = provider
        self.status_code = status_code


class ToolError(AgentError):
    """Raised when a tool execution encounters an error."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if tool_name:
            details["tool_name"] = tool_name
        if tool_call_id:
            details["tool_call_id"] = tool_call_id
        super().__init__(message, details)
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id


class ToolTimeoutError(ToolError):
    """Raised when a tool execution exceeds its configured timeout."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        timeout: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if timeout is not None:
            details["timeout"] = timeout
        super().__init__(message, tool_name=tool_name, details=details)
        self.timeout = timeout


class ToolPermissionError(ToolError):
    """Raised when a tool call fails permission checks."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if permission:
            details["required_permission"] = permission
        super().__init__(message, tool_name=tool_name, details=details)
        self.permission = permission


class MemoryError(AgentError):
    """Raised when a memory store operation fails."""

    def __init__(
        self,
        message: str,
        layer: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if layer:
            details["memory_layer"] = layer
        super().__init__(message, details)
        self.layer = layer


class VectorStoreError(AgentError):
    """Raised when a vector store or embedding operation fails."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if operation:
            details["operation"] = operation
        super().__init__(message, details)
        self.operation = operation


class HumanInterventionError(AgentError):
    """Raised when human intervention rejects, cancels, or errors an operation."""

    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if request_id:
            details["request_id"] = request_id
        if reason:
            details["reason"] = reason
        super().__init__(message, details)
        self.request_id = request_id
        self.reason = reason


class ContextLimitError(AgentError):
    """Raised when prompt or context exceeds configured window/limits."""

    def __init__(
        self,
        message: str,
        current_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if current_tokens is not None:
            details["current_tokens"] = current_tokens
        if max_tokens is not None:
            details["max_tokens"] = max_tokens
        super().__init__(message, details)
        self.current_tokens = current_tokens
        self.max_tokens = max_tokens


class OutputValidationError(AgentError):
    """Raised when structured LLM output fails schema validation and cannot be repaired."""

    def __init__(
        self,
        message: str,
        raw_output: Optional[str] = None,
        validation_errors: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if raw_output:
            details["raw_output"] = raw_output
        if validation_errors:
            details["validation_errors"] = str(validation_errors)
        super().__init__(message, details)
        self.raw_output = raw_output
        self.validation_errors = validation_errors


class MaxIterationsError(AgentError):
    """Raised when the agent loop exceeds the configured maximum iterations."""

    def __init__(
        self,
        message: str,
        iterations: Optional[int] = None,
        max_iterations: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if iterations is not None:
            details["iterations"] = iterations
        if max_iterations is not None:
            details["max_iterations"] = max_iterations
        super().__init__(message, details)
        self.iterations = iterations
        self.max_iterations = max_iterations


class ExecutionTimeoutError(AgentError):
    """Raised when agent execution exceeds the configured max execution time."""

    def __init__(
        self,
        message: str,
        timeout: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if timeout is not None:
            details["timeout"] = timeout
        super().__init__(message, details)
        self.timeout = timeout
