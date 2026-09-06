"""Retriever and RAG pipeline components."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .base import VectorItem, VectorSearchResult, VectorStore
from .embeddings import Embedder, SimpleEmbedder
from .stores.in_memory import InMemoryVectorStore


class RetrievalConfig(BaseModel):
    """Configuration for retrieval augmentation."""

    top_k: int = Field(default=4, ge=1, description="Number of documents to retrieve.")
    similarity_threshold: Optional[float] = Field(default=None, description="Minimum similarity threshold.")
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters to apply.")
    namespace: Optional[str] = Field(default=None, description="Vector store namespace.")
    max_context_tokens: Optional[int] = Field(default=None, description="Token cap on retrieved context.")


class Retriever:
    """Retrieval pipeline for vector-based semantic search and context extraction."""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedder: Optional[Embedder] = None,
        config: Optional[RetrievalConfig] = None,
    ):
        self.vector_store: VectorStore = vector_store or InMemoryVectorStore()
        self.embedder: Embedder = embedder or SimpleEmbedder()
        self.config: RetrievalConfig = config or RetrievalConfig()

    async def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        namespace: Optional[str] = None,
    ) -> List[str]:
        """Embeds and indexes documents into the vector store."""
        embeddings = await self.embedder.embed_batch(texts)
        ns = namespace or self.config.namespace or "default"

        items = []
        for i, text in enumerate(texts):
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            items.append(VectorItem(text=text, embedding=embeddings[i], metadata=meta, namespace=ns))

        return await self.vector_store.add(items)

    async def retrieve(self, query: str, top_k: Optional[int] = None) -> List[VectorSearchResult]:
        """Embeds query and performs vector similarity search."""
        k = top_k or self.config.top_k
        query_embedding = await self.embedder.embed(query)

        return await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=k,
            similarity_threshold=self.config.similarity_threshold,
            namespace=self.config.namespace,
            filter=self.config.metadata_filter,
        )

    async def retrieve_context(self, query: str, top_k: Optional[int] = None) -> List[str]:
        """Convenience method returning raw text contents of matched documents."""
        results = await self.retrieve(query, top_k=top_k)
        return [res.text for res in results]
