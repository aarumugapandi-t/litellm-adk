"""Custom Vector Store Example.

Demonstrates implementing the VectorStore protocol to integrate a custom storage engine
without modifying any framework internals.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional
from litellm_adk import (
    Agent,
    Retriever,
    SimpleEmbedder,
    VectorItem,
    VectorSearchResult,
    VectorStore,
)


class SimpleDictionaryVectorStore(VectorStore):
    """Custom dictionary-backed vector store implementing the VectorStore protocol."""

    def __init__(self):
        self._database: Dict[str, VectorItem] = {}

    async def add(self, items: List[VectorItem]) -> List[str]:
        ids = []
        for item in items:
            self._database[item.id] = item
            ids.append(item.id)
        print(f"[CustomVectorStore] Successfully indexed {len(items)} items.")
        return ids

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        similarity_threshold: Optional[float] = None,
        namespace: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        # Keyword & embedding matching
        results = []
        for item in self._database.values():
            if namespace and item.namespace != namespace:
                continue
            # Simple dot product as score
            score = 1.0
            if item.embedding and query_embedding:
                score = sum(a * b for a, b in zip(item.embedding, query_embedding))

            results.append(VectorSearchResult(item=item, score=score))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> None:
        for item_id in ids:
            self._database.pop(item_id, None)

    async def get(self, id: str) -> Optional[VectorItem]:
        return self._database.get(id)


async def main():
    # 1. Instantiate the custom store and embedder
    my_store = SimpleDictionaryVectorStore()
    retriever = Retriever(vector_store=my_store, embedder=SimpleEmbedder(dimensions=32))

    # 2. Add domain documents
    await retriever.add_documents([
        "Authentication uses OAuth2 Bearer tokens signed via RSA256.",
        "Rate limiting is set to 100 requests per minute per IP address.",
    ])

    # 3. Create Agent powered by the custom vector store
    agent = Agent(
        name="custom_store_assistant",
        model=os.getenv("LITELLM_MODEL", "openai/gpt-4o"),
        system_prompt="You are a security architect. Answer questions based on the retrieved documentation.",
        retriever=retriever,
    )

    query = "What is the token signing method and rate limit?"
    print(f"Query: {query}\n")

    result = await agent.run(query)
    print(f"Response:\n{result.text}")


if __name__ == "__main__":
    asyncio.run(main())
