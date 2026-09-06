"""Pure Python in-memory vector store with cosine similarity."""

import math
from typing import Any, Dict, List, Optional

from ..base import VectorItem, VectorSearchResult, VectorStore


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class InMemoryVectorStore:
    """In-memory vector store requiring zero external database dependencies."""

    def __init__(self):
        self._items: Dict[str, VectorItem] = {}

    async def add(self, items: List[VectorItem]) -> List[str]:
        """Stores vector items in memory."""
        ids = []
        for item in items:
            self._items[item.id] = item
            ids.append(item.id)
        return ids

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        similarity_threshold: Optional[float] = None,
        namespace: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Performs cosine similarity search across indexed vectors."""
        results: List[VectorSearchResult] = []

        for item in self._items.values():
            if namespace and item.namespace != namespace:
                continue

            if filter:
                match = all(item.metadata.get(k) == v for k, v in filter.items())
                if not match:
                    continue

            if not item.embedding:
                continue

            score = _cosine_similarity(query_embedding, item.embedding)

            if similarity_threshold is not None and score < similarity_threshold:
                continue

            results.append(VectorSearchResult(item=item, score=score))

        # Sort descending by similarity score
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> None:
        """Deletes items by ID."""
        for item_id in ids:
            if item_id in self._items:
                if namespace and self._items[item_id].namespace != namespace:
                    continue
                del self._items[item_id]

    async def get(self, id: str) -> Optional[VectorItem]:
        """Retrieves a single vector item by ID."""
        return self._items.get(id)

    async def add_texts(
        self,
        texts: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        namespace: str = "default",
    ) -> List[str]:
        """Convenience method to index raw texts with embeddings."""
        items = []
        for i, text in enumerate(texts):
            emb = embeddings[i] if embeddings and i < len(embeddings) else None
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            item_id = ids[i] if ids and i < len(ids) else None

            if item_id:
                item = VectorItem(id=item_id, text=text, embedding=emb, metadata=meta, namespace=namespace)
            else:
                item = VectorItem(text=text, embedding=emb, metadata=meta, namespace=namespace)
            items.append(item)

        return await self.add(items)
