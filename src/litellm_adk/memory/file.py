import json
import os
import asyncio
from typing import List, Dict, Any, Optional
from .base import BaseMemory

class FileMemory(BaseMemory):
    """
    JSON file-based persistence for conversation history and session metadata.
    Note: In production environments, SQLAlchemyMemory (Postgres/SQLite) is recommended
    over FileMemory for better concurrency handling.
    """
    def __init__(self, file_path: str = "conversations.json"):
        self.file_path = file_path
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._load_sync()

    def _load_sync(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for k, v in data.items():
                        if isinstance(v, list):
                            self._cache[k] = {"messages": v, "metadata": {}}
                        else:
                            self._cache[k] = v
                except json.JSONDecodeError:
                    self._cache = {}
        else:
            self._cache = {}

    async def _save(self):
        # Offload file I/O to a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._save_sync)

    def _save_sync(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, ensure_ascii=False)

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        async with self._lock:
            return self._cache.get(session_id, {}).get("messages", []).copy()

    async def add_message(self, session_id: str, message: Dict[str, Any]):
        async with self._lock:
            if session_id not in self._cache:
                self._cache[session_id] = {"messages": [], "metadata": {}}
            self._cache[session_id]["messages"].append(message)
            await self._save()

    async def add_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        async with self._lock:
            if session_id not in self._cache:
                self._cache[session_id] = {"messages": [], "metadata": {}}
            self._cache[session_id]["messages"].extend(messages)
            await self._save()

    async def clear(self, session_id: str):
        async with self._lock:
            if session_id in self._cache:
                self._cache[session_id] = {"messages": [], "metadata": {}}
                await self._save()

    async def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        async with self._lock:
            return self._cache.get(session_id, {}).get("metadata", {}).copy()

    async def save_session_metadata(self, session_id: str, metadata: Dict[str, Any]):
        async with self._lock:
            if session_id not in self._cache:
                self._cache[session_id] = {"messages": [], "metadata": {}}
            self._cache[session_id]["metadata"] = metadata
            await self._save()
