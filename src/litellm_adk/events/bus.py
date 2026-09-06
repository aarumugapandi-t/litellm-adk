"""Asynchronous pub/sub EventBus for agent runtime events."""

import asyncio
import inspect
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from fnmatch import fnmatch

from ..observability.logger import adk_logger
from .types import Event


class EventBus:
    """Pub/sub dispatcher managing listeners and real-time streaming queues."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable[[Event], Any]]] = {}
        self._queues: List[asyncio.Queue[Optional[Event]]] = []

    def subscribe(self, pattern: str, handler: Callable[[Event], Any]) -> None:
        """Subscribes a callback to events matching pattern (supports wildcards, e.g. 'tool.*')."""
        if pattern not in self._handlers:
            self._handlers[pattern] = []
        self._handlers[pattern].append(handler)

    def unsubscribe(self, pattern: str, handler: Callable[[Event], Any]) -> None:
        """Unsubscribes a callback from pattern."""
        if pattern in self._handlers:
            self._handlers[pattern] = [h for h in self._handlers[pattern] if h != handler]

    async def publish(self, event: Event) -> None:
        """Publishes an event to all matching subscribers and active streaming queues."""
        # 1. Dispatch to matching handlers
        for pattern, handlers in self._handlers.items():
            if fnmatch(event.type, pattern) or pattern == "*":
                for handler in handlers:
                    try:
                        if inspect.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        adk_logger.warning(f"Error in event handler for {event.type}: {e}")

        # 2. Push to streaming queues
        for q in self._queues:
            await q.put(event)

    def create_stream_queue(self) -> asyncio.Queue[Optional[Event]]:
        """Creates a new queue that will receive all published events."""
        q: asyncio.Queue[Optional[Event]] = asyncio.Queue()
        self._queues.append(q)
        return q

    def remove_stream_queue(self, q: asyncio.Queue[Optional[Event]]) -> None:
        """Removes a previously registered streaming queue."""
        if q in self._queues:
            self._queues.remove(q)
