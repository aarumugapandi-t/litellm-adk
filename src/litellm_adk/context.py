"""Backward compatibility re-export for ContextManager."""

from .context import ContextItem, ContextManager, ContextPolicy, ContextStrategy, ContextWindow

__all__ = [
    "ContextManager",
    "ContextPolicy",
    "ContextStrategy",
    "ContextItem",
    "ContextWindow",
]
