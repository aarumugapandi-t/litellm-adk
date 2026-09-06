"""Security middleware performing PII sanitization and safety checks."""

from typing import Any, Dict

from ..security import PIIScrubber
from .base import Middleware


class PIIScrubbingMiddleware(Middleware):
    """Sanitizes sensitive Personally Identifiable Information (PII) before model dispatch."""

    async def before_run(self, context: Dict[str, Any]) -> None:
        if "prompt" in context and isinstance(context["prompt"], str):
            context["prompt"] = PIIScrubber.scrub_text(context["prompt"])

        if "messages" in context and isinstance(context["messages"], list):
            context["messages"] = PIIScrubber.scrub_messages(context["messages"])

    async def after_run(self, context: Dict[str, Any], result: Any) -> None:
        pass

    async def on_error(self, context: Dict[str, Any], error: Exception) -> None:
        pass
