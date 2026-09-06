"""Long-term memory surviving across sessions."""

from typing import Any, Dict, List, Optional
from .base import MemoryStore


class InMemoryStore:
    """Default in-memory implementation of MemoryStore protocol."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        return entry["value"] if entry else None

    async def add(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._store[key] = {"value": value, "metadata": metadata or {}}

    async def update(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        if key in self._store:
            self._store[key]["value"] = value
            if metadata:
                self._store[key]["metadata"].update(metadata)
        else:
            await self.add(key, value, metadata)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_words = set(query.lower().split())
        results = []

        for key, item in self._store.items():
            text = f"{key} {str(item['value'])}".lower()
            match_score = sum(1 for w in query_words if w in text)
            if match_score > 0:
                results.append({"key": key, "value": item["value"], "score": match_score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


class LongTermMemory:
    """Manages cross-session user preferences, learned facts, and persistent decisions."""

    def __init__(self, store: Optional[MemoryStore] = None):
        self.store: MemoryStore = store or InMemoryStore()

    async def add_fact(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Stores a persistent fact or preference."""
        await self.store.add(key, value, metadata)

    async def get_fact(self, key: str) -> Optional[Any]:
        """Retrieves a persistent fact by key."""
        return await self.store.get(key)

    async def delete_fact(self, key: str) -> None:
        """Deletes a persistent fact."""
        await self.store.delete(key)

    async def retrieve_relevant_facts(self, query: str, limit: int = 5) -> List[str]:
        """Retrieves facts relevant to a given query string."""
        results = await self.store.search(query, limit=limit)
        return [f"{r['key']}: {r['value']}" for r in results]
