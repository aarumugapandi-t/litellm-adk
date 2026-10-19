"""Long-term memory surviving across sessions."""

from typing import Any, Dict, List, Optional
from .base import MemoryStore


from ..vector.base import VectorStore


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
        import re

        query_words = set(re.findall(r"\w+", query.lower()))
        results = []

        for key, item in self._store.items():
            text = f"{key} {str(item['value'])}".lower()
            text_words = set(re.findall(r"\w+", text))
            match_score = sum(1 for w in query_words if w in text_words)
            if match_score > 0:
                results.append({"key": key, "value": item["value"], "score": match_score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


class LongTermMemory:
    """Manages multi-tier long-term cognitive memory:
    
    1. Core User Profile Memory: Deterministic key-value attributes (name, role, constraints, formatting rules)
       partitioned strictly by user_id and unconditionally loaded into context.
    2. Episodic Memory: Vector-embedded historical discussions, decisions, and unstructured notes.
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        episodic_store: Optional[VectorStore] = None,
    ):
        self.store: MemoryStore = store or InMemoryStore()
        self.episodic_store: Optional[VectorStore] = episodic_store
        # Partitioned User Profile Storage: user_id -> {key: value}
        self._profiles: Dict[str, Dict[str, Any]] = {}

    # -----------------------------------------------------------------------
    # Tier 1: Deterministic Core User Profile (Per user_id)
    # -----------------------------------------------------------------------
    async def add_profile_attribute(
        self,
        user_id: Optional[str],
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Stores a persistent user profile attribute, constraint, or formatting rule."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        if uid not in self._profiles:
            self._profiles[uid] = {}
        self._profiles[uid][key] = value
        await self.store.add(f"{uid}:{key}", value, metadata)

    async def get_profile(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns all persistent profile attributes for the given user_id."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        profile = dict(self._profiles.get("__global__", {}))
        if uid != "__global__" and uid in self._profiles:
            profile.update(self._profiles[uid])
        return profile

    async def delete_profile_attribute(self, user_id: Optional[str], key: str) -> None:
        """Deletes a user profile attribute."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        if uid in self._profiles:
            self._profiles[uid].pop(key, None)
        await self.store.delete(f"{uid}:{key}")

    # -----------------------------------------------------------------------
    # Tier 4: Episodic Semantic Memory (Vector Store / Embeddings)
    # -----------------------------------------------------------------------
    async def add_episodic_memory(
        self,
        user_id: Optional[str],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Stores an episodic memory chunk into the vector store, tagged with user_id."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        if self.episodic_store:
            meta = dict(metadata or {})
            meta["user_id"] = uid
            await self.episodic_store.add_documents([content], metadatas=[meta])
        else:
            await self.store.add(f"{uid}:episodic:{id(content)}", content, metadata)

    async def search_episodic_memory(
        self,
        user_id: Optional[str],
        query: str,
        limit: int = 5,
    ) -> List[str]:
        """Searches episodic memory via semantic vector search for the specific user."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        if self.episodic_store:
            if hasattr(self.episodic_store, "embed"):
                query_emb = await self.episodic_store.embed(query)
            else:
                from ..vector.embeddings import SimpleEmbedder
                query_emb = await SimpleEmbedder().embed(query)

            results = await self.episodic_store.search(
                query_embedding=query_emb,
                top_k=limit,
                filter={"user_id": uid},
            )
            return [r.item.content for r in results]
        return []

    # -----------------------------------------------------------------------
    # Unified Retrieval & Backward Compatibility
    # -----------------------------------------------------------------------
    async def add_fact(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Stores a persistent fact or preference (profile attribute)."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        await self.add_profile_attribute(uid, key, value, metadata)
        await self.store.add(f"{uid}:{key}", value, metadata)

    async def get_fact(self, key: str, user_id: Optional[str] = None) -> Optional[Any]:
        """Retrieves a persistent fact by key."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        if uid in self._profiles and key in self._profiles[uid]:
            return self._profiles[uid][key]
        val = await self.store.get(f"{uid}:{key}")
        if val is not None:
            return val
        return await self.store.get(key)

    async def delete_fact(self, key: str, user_id: Optional[str] = None) -> None:
        """Deletes a persistent fact."""
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        if uid in self._profiles:
            self._profiles[uid].pop(key, None)
        await self.store.delete(f"{uid}:{key}")
        await self.store.delete(key)

    async def retrieve_relevant_facts(
        self,
        query: str,
        limit: int = 5,
        user_id: Optional[str] = None,
    ) -> List[str]:
        """Retrieves facts relevant to a given query string, scoped by user_id if provided."""
        results = await self.store.search(query, limit=limit)
        from ..session.session import current_user_id
        uid = str(user_id or current_user_id.get() or "__global__")
        filtered = []
        for r in results:
            k = r["key"]
            if k.startswith(f"{uid}:") or k.startswith("__global__:") or (":" not in k and uid == "__global__"):
                clean_k = k.split(":", 1)[1] if ":" in k else k
                filtered.append(f"{clean_k}: {r['value']}")
        return filtered

    async def retrieve_user_context(
        self,
        user_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 5,
    ) -> List[str]:
        """Assembles deterministic profile attributes plus query-relevant episodic memories."""
        entries: List[str] = []

        # 1. Deterministic profile attributes (unconditionally loaded for this user)
        profile = await self.get_profile(user_id)
        for k, v in profile.items():
            entries.append(f"{k}: {v}")

        # 2. Episodic semantic memories if query provided and vector store active
        if query and user_id and self.episodic_store:
            try:
                episodic = await self.search_episodic_memory(user_id, query, limit=limit)
                for ep in episodic:
                    entries.append(f"Past Context: {ep}")
            except Exception:
                pass

        # 3. Fallback to keyword search on underlying store if profile is empty
        if not entries and query:
            entries = await self.retrieve_relevant_facts(query, limit=limit, user_id=user_id)

        return entries
