"""Retriever and RAG pipeline components supporting direct, conditional, and multi-query strategies."""

import asyncio
from typing import Any, Dict, List, Optional, Sequence
from pydantic import BaseModel, Field

from .base import VectorItem, VectorSearchResult, VectorStore
from .embeddings import Embedder, SimpleEmbedder
from .stores.in_memory import InMemoryVectorStore
from .strategy import (
    MultiQueryConfig,
    QueryTransformationConfig,
    RetrievalMode,
    RetrievalRouterConfig,
    RetrievalStrategy,
)
from .transformers import (
    ConditionalQueryTransformer,
    MultiQueryDecomposer,
    ReciprocalRankFusion,
    RetrievalRouter,
)


class RetrievalConfig(BaseModel):
    """Configuration for retrieval augmentation."""

    top_k: int = Field(default=4, ge=1, description="Number of documents to retrieve.")
    similarity_threshold: Optional[float] = Field(default=None, description="Minimum similarity threshold.")
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters to apply.")
    namespace: Optional[str] = Field(default=None, description="Vector store namespace.")
    max_context_tokens: Optional[int] = Field(default=None, description="Token cap on retrieved context.")

    # Strategy & Execution Mode
    mode: RetrievalMode = Field(default=RetrievalMode.TOOL, description="'tool', 'pipeline', or 'both'")
    strategy: RetrievalStrategy = Field(default=RetrievalStrategy.DIRECT, description="Retrieval strategy algorithm.")
    transformation_config: Optional[QueryTransformationConfig] = None
    multi_query_config: Optional[MultiQueryConfig] = None
    router_config: Optional[RetrievalRouterConfig] = None


class Retriever:
    """Retrieval pipeline for vector-based semantic search, context extraction, and agent tools."""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedder: Optional[Embedder] = None,
        config: Optional[RetrievalConfig] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        min_score: Optional[float] = None,
        namespace: Optional[str] = None,
        strategy: Optional[RetrievalStrategy] = None,
        mode: Optional[RetrievalMode] = None,
        transformer_model: Optional[Any] = None,
    ):
        self.vector_store: VectorStore = vector_store or InMemoryVectorStore()
        if embedder is None and hasattr(self.vector_store, "embed") and hasattr(self.vector_store, "embed_batch"):
            self.embedder: Embedder = self.vector_store  # type: ignore
        else:
            self.embedder: Embedder = embedder or SimpleEmbedder()

        r_config = config or RetrievalConfig()
        if top_k is not None:
            r_config.top_k = top_k
        sim_thresh = similarity_threshold if similarity_threshold is not None else min_score
        if sim_thresh is not None:
            r_config.similarity_threshold = sim_thresh
        if namespace is not None:
            r_config.namespace = namespace
        if strategy is not None:
            r_config.strategy = strategy
        if mode is not None:
            r_config.mode = mode

        self.config: RetrievalConfig = r_config
        self.transformer_model = transformer_model

        # Helper components
        self._transformer = ConditionalQueryTransformer(
            model=self.transformer_model,
            config=self.config.transformation_config,
        )
        self._decomposer = MultiQueryDecomposer(
            model=self.transformer_model,
            config=self.config.multi_query_config,
        )
        self._router = RetrievalRouter(
            model=self.transformer_model,
            config=self.config.router_config,
        )

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

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[VectorSearchResult]:
        """Embeds query and performs direct vector similarity search."""
        k = top_k or self.config.top_k
        query_embedding = await self.embedder.embed(query)

        return await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=k,
            similarity_threshold=self.config.similarity_threshold,
            namespace=self.config.namespace,
            filter=self.config.metadata_filter,
        )

    async def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        strategy: Optional[RetrievalStrategy] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Retrieves raw text contents applying the configured retrieval strategy."""
        active_strategy = strategy or self.config.strategy
        k = top_k or self.config.top_k

        # 1. DIRECT STRATEGY
        if active_strategy == RetrievalStrategy.DIRECT:
            results = await self.retrieve(query, top_k=k)
            return [res.text for res in results]

        # 2. CONDITIONAL TRANSFORM STRATEGY
        if active_strategy == RetrievalStrategy.CONDITIONAL_TRANSFORM:
            decision = await self._transformer.transform(query, history=history)
            if not decision.needs_search:
                return []
            target_query = decision.search_query or query
            results = await self.retrieve(target_query, top_k=k)
            return [res.text for res in results]

        # 3. MULTI-QUERY STRATEGY
        if active_strategy == RetrievalStrategy.MULTI_QUERY:
            sub_queries = await self._decomposer.decompose(query)
            if len(sub_queries) <= 1:
                results = await self.retrieve(query, top_k=k)
                return [res.text for res in results]

            search_tasks = [self.retrieve(sq, top_k=k) for sq in sub_queries]
            result_lists = await asyncio.gather(*search_tasks)

            rrf_k = self.config.multi_query_config.rrf_k if self.config.multi_query_config else 60
            fused_results = ReciprocalRankFusion.fuse(result_lists, k=rrf_k, top_k=k)
            return [res.text for res in fused_results]

        # 4. ADAPTIVE ROUTER STRATEGY
        if active_strategy == RetrievalStrategy.ADAPTIVE_ROUTER:
            routed_strategy = await self._router.route(query, history=history)
            return await self.retrieve_context(
                query=query,
                top_k=k,
                history=history,
                strategy=routed_strategy,
                **kwargs,
            )

        # Fallback to direct
        results = await self.retrieve(query, top_k=k)
        return [res.text for res in results]

    def to_tool(
        self,
        name: str = "search_knowledge_base",
        description: Optional[str] = None,
        top_k: Optional[int] = None,
        working_memory: Optional[Any] = None,
    ) -> Any:
        """Constructs an autonomous RetrieverTool wrapping this retriever for an Agent."""
        from .tool import RetrieverTool
        return RetrieverTool(
            retriever=self,
            name=name,
            description=description,
            top_k=top_k or self.config.top_k,
            working_memory=working_memory,
        )
