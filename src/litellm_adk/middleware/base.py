"""Middleware protocol and pipeline execution engine."""

import inspect
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from ..observability.logger import adk_logger


@runtime_checkable
class Middleware(Protocol):
    """Protocol for intercepting agent runs and error lifecycles."""

    async def before_run(self, context: Dict[str, Any]) -> None:
        """Invoked before the agent loop begins execution."""
        ...

    async def after_run(self, context: Dict[str, Any], result: Any) -> None:
        """Invoked after the agent loop completes successfully."""
        ...

    async def on_error(self, context: Dict[str, Any], error: Exception) -> None:
        """Invoked if an unhandled exception occurs during execution."""
        ...


class MiddlewarePipeline:
    """Manages an ordered chain of middleware handlers."""

    def __init__(self, middlewares: Optional[List[Middleware]] = None):
        self.middlewares: List[Middleware] = middlewares or []

    def add(self, middleware: Middleware) -> None:
        self.middlewares.append(middleware)

    async def run_before(self, context: Dict[str, Any]) -> None:
        """Executes before_run across all middleware in registration order."""
        for mw in self.middlewares:
            if hasattr(mw, "before_run"):
                try:
                    if inspect.iscoroutinefunction(mw.before_run):
                        await mw.before_run(context)
                    else:
                        mw.before_run(context)
                except Exception as e:
                    adk_logger.warning(f"Error in {mw.__class__.__name__}.before_run: {e}")

    async def run_after(self, context: Dict[str, Any], result: Any) -> None:
        """Executes after_run across all middleware in reverse order."""
        for mw in reversed(self.middlewares):
            if hasattr(mw, "after_run"):
                try:
                    if inspect.iscoroutinefunction(mw.after_run):
                        await mw.after_run(context, result)
                    else:
                        mw.after_run(context, result)
                except Exception as e:
                    adk_logger.warning(f"Error in {mw.__class__.__name__}.after_run: {e}")

    async def run_on_error(self, context: Dict[str, Any], error: Exception) -> None:
        """Executes on_error across all middleware."""
        for mw in self.middlewares:
            if hasattr(mw, "on_error"):
                try:
                    if inspect.iscoroutinefunction(mw.on_error):
                        await mw.on_error(context, error)
                    else:
                        mw.on_error(context, error)
                except Exception as e:
                    adk_logger.warning(f"Error in {mw.__class__.__name__}.on_error: {e}")
