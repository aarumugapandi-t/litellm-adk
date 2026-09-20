import asyncio
import json
import logging
import os
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

import litellm

from pydantic import BaseModel, ConfigDict, Field
from ...observability.logger import adk_logger
from ...vector.base import VectorItem, VectorSearchResult, VectorStore
from ..vector_store import VectorStore as LegacyVectorStore


class PostgresVectorStoreConfig(BaseModel):
    """Configuration model for PostgreSQL pgvector storage."""

    model_config = ConfigDict(extra="forbid")

    connection_string: str = Field(description="PostgreSQL connection URI.")
    table_name: str = Field(default="adk_vectors", description="Target PostgreSQL table name.")
    embedding_model: Optional[str] = Field(default=None, description="Embedding model identifier.")
    vector_dim: Optional[int] = Field(default=None, description="Vector dimension size matching the embedding model.")
    api_key: Optional[str] = Field(default=None, description="API key for the embedding provider.")
    base_url: Optional[str] = Field(default=None, description="Base URL or proxy endpoint for the embedding provider.")
    custom_llm_provider: Optional[str] = Field(
        default=None,
        description="Custom LLM provider protocol (e.g. 'openai' for LiteLLM proxy or OpenAI-compatible gateways).",
    )


class PostgresVectorStore(VectorStore, LegacyVectorStore):
    """
    PostgreSQL-based vector store implementation using pgvector.
    Adheres to both ADK VectorStore and Embedder protocols.
    
    Requires:
    - PostgreSQL database with pgvector extension (`CREATE EXTENSION IF NOT EXISTS vector;`)
    - `asyncpg` and `pgvector` Python packages
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        table_name: str = "adk_vectors",
        embedding_model: Optional[str] = None,
        vector_dim: Optional[int] = None,
        embedding_function: Optional[Callable[[List[str]], Awaitable[List[List[float]]]]] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        custom_llm_provider: Optional[str] = None,
        config: Optional[PostgresVectorStoreConfig] = None,
    ):
        try:
            import asyncpg  # type: ignore
            from pgvector.asyncpg import register_vector  # type: ignore
        except ImportError:
            raise ImportError("asyncpg/pgvector not installed. Please run `pip install asyncpg pgvector`.")

        if config:
            connection_string = config.connection_string or connection_string
            table_name = config.table_name or table_name
            embedding_model = config.embedding_model or embedding_model
            vector_dim = config.vector_dim or vector_dim
            api_key = config.api_key or api_key
            base_url = config.base_url or base_url
            custom_llm_provider = config.custom_llm_provider or custom_llm_provider

        if not connection_string:
            raise ValueError("A valid 'connection_string' must be provided to PostgresVectorStore.")

        self.connection_string = connection_string
        self.table_name = table_name
        self.api_key = api_key or os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("LITELLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        self.custom_llm_provider = custom_llm_provider or ("openai" if self.base_url else None)
        self.pool = None
        self.embedding_function = embedding_function
        self.embedding_model = embedding_model

        # Configure embedding provider generically without hardcoded vendor fallbacks
        if not self.embedding_model and not self.embedding_function:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
                self.vector_dim = vector_dim or 384

                async def default_local_emb(texts: List[str]) -> List[List[float]]:
                    loop = asyncio.get_running_loop()
                    embeddings = await loop.run_in_executor(None, self._st_model.encode, texts)
                    return embeddings.tolist()

                self.embedding_function = default_local_emb
                self.embedding_model = "local-st"
            except ImportError:
                raise ValueError(
                    "No embedding configuration provided. Please specify 'embedding_model' (e.g. 'gemini/gemini-embedding-001', "
                    "'text-embedding-3-small') along with 'vector_dim', or provide an 'embedding_function', "
                    "or install 'sentence-transformers' for local embeddings."
                )
        else:
            if vector_dim is not None:
                self.vector_dim = vector_dim
            elif self.embedding_model:
                lower = self.embedding_model.lower()
                if "gemini" in lower or "embedding-001" in lower or "text-embedding-004" in lower:
                    self.vector_dim = 768
                elif "text-embedding-3-small" in lower or "ada-002" in lower:
                    self.vector_dim = 1536
                elif "text-embedding-3-large" in lower:
                    self.vector_dim = 3072
                elif "minilm" in lower or "bge-small" in lower:
                    self.vector_dim = 384
                elif "bge-base" in lower:
                    self.vector_dim = 768
                elif "bge-large" in lower:
                    self.vector_dim = 1024
                else:
                    raise ValueError(
                        f"Cannot infer vector dimension for model '{self.embedding_model}'. "
                        "Please specify 'vector_dim' explicitly (e.g., vector_dim=768)."
                    )
            else:
                raise ValueError("When providing a custom 'embedding_function', 'vector_dim' must be explicitly specified.")

    async def _ensure_pool(self) -> None:
        import asyncpg
        from pgvector.asyncpg import register_vector

        if not self.pool:
            self.pool = await asyncpg.create_pool(self.connection_string)
            async with self.pool.acquire() as conn:
                await register_vector(conn)
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        id UUID PRIMARY KEY,
                        text TEXT,
                        metadata JSONB,
                        embedding vector({self.vector_dim})
                    )
                """)

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using custom function or LiteLLM gateway/proxy."""
        if self.embedding_function:
            return await self.embedding_function(texts)

        kwargs: Dict[str, Any] = {
            "model": self.embedding_model,
            "input": texts,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url
            kwargs["base_url"] = self.base_url
        if self.custom_llm_provider:
            kwargs["custom_llm_provider"] = self.custom_llm_provider

        response = await litellm.aembedding(**kwargs)
        return [d["embedding"] for d in response["data"]]

    # -------------------------------------------------------------------------
    # Embedder Protocol Implementation
    # -------------------------------------------------------------------------

    async def embed(self, text: str) -> List[float]:
        """Generate embedding vector for a single text."""
        embeddings = await self._get_embeddings([text])
        return embeddings[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of texts."""
        return await self._get_embeddings(texts)

    # -------------------------------------------------------------------------
    # VectorStore Protocol Implementation
    # -------------------------------------------------------------------------

    async def add(self, items: List[VectorItem]) -> List[str]:
        """Adds vector items to the store and returns their IDs."""
        await self._ensure_pool()
        if not items:
            return []

        # Generate missing embeddings in batch
        missing_indices = [i for i, item in enumerate(items) if not item.embedding]
        if missing_indices:
            texts = [items[i].text for i in missing_indices]
            embeddings = await self.embed_batch(texts)
            for idx, emb in zip(missing_indices, embeddings):
                items[idx].embedding = emb

        records = []
        ids = []
        for item in items:
            item_id = str(item.id)
            try:
                pg_id = uuid.UUID(item_id)
            except ValueError:
                pg_id = uuid.uuid5(uuid.NAMESPACE_DNS, item_id)

            meta = dict(item.metadata)
            if item.namespace:
                meta["_namespace"] = item.namespace

            records.append((
                pg_id,
                item.text,
                json.dumps(meta),
                item.embedding,
            ))
            ids.append(item_id)

        async with self.pool.acquire() as conn:  # type: ignore
            await conn.executemany(f"""
                INSERT INTO {self.table_name} (id, text, metadata, embedding)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET
                    text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding
            """, records)

        return ids

    async def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        namespace: str = "default",
    ) -> List[str]:
        """Convenience method to index raw texts with optional metadata and ids."""
        if not texts:
            return []
        items = []
        for i, text in enumerate(texts):
            item_id = ids[i] if ids and i < len(ids) else str(uuid.uuid4())
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            items.append(VectorItem(id=item_id, text=text, metadata=meta, namespace=namespace))
        return await self.add(items)

    async def search(
        self,
        query_embedding: Optional[List[float]] = None,
        query: Optional[str] = None,
        top_k: int = 4,
        similarity_threshold: Optional[float] = None,
        namespace: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Searches for items matching query_embedding or text query.
        Returns a list of VectorSearchResult objects (also accessible as dicts).
        """
        await self._ensure_pool()

        # Resolve embedding vector
        target_embedding = query_embedding
        if target_embedding is None:
            if not query:
                raise ValueError("Either 'query_embedding' or 'query' must be provided to search.")
            target_embedding = await self.embed(query)
        elif query and len(target_embedding) != self.vector_dim:
            # Dimension mismatch safeguard: re-embed using this store's embedder
            target_embedding = await self.embed(query)

        # Build SQL query with optional filters
        params: List[Any] = [target_embedding, top_k]
        filter_clauses: List[str] = []

        if filter:
            params.append(json.dumps(filter))
            filter_clauses.append(f"metadata @> ${len(params)}")

        if namespace:
            params.append(json.dumps({"_namespace": namespace}))
            filter_clauses.append(f"metadata @> ${len(params)}")

        where_sql = ""
        if filter_clauses:
            where_sql = "WHERE " + " AND ".join(filter_clauses)

        async with self.pool.acquire() as conn:  # type: ignore
            rows = await conn.fetch(f"""
                SELECT id, text, metadata, 1 - (embedding <=> $1) as score
                FROM {self.table_name}
                {where_sql}
                ORDER BY embedding <=> $1
                LIMIT $2
            """, *params)

        results: List[VectorSearchResult] = []
        for row in rows:
            score = float(row["score"])
            if similarity_threshold is not None and score < similarity_threshold:
                continue

            raw_meta = row["metadata"]
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
            item_namespace = meta.pop("_namespace", "default")

            item = VectorItem(
                id=str(row["id"]),
                text=row["text"],
                metadata=meta,
                namespace=item_namespace,
            )
            results.append(VectorSearchResult(item=item, score=score))

        return results

    async def get(self, id: str) -> Optional[VectorItem]:
        """Retrieves an item by ID."""
        await self._ensure_pool()
        try:
            pg_id = uuid.UUID(id)
        except ValueError:
            pg_id = uuid.uuid5(uuid.NAMESPACE_DNS, id)

        async with self.pool.acquire() as conn:  # type: ignore
            row = await conn.fetchrow(f"""
                SELECT id, text, metadata
                FROM {self.table_name}
                WHERE id = $1
            """, pg_id)

        if not row:
            return None

        raw_meta = row["metadata"]
        meta = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
        item_namespace = meta.pop("_namespace", "default")

        return VectorItem(
            id=str(row["id"]),
            text=row["text"],
            metadata=meta,
            namespace=item_namespace,
        )

    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> None:
        """Deletes items by ID."""
        await self._ensure_pool()
        if not ids:
            return

        pg_ids = []
        for item_id in ids:
            try:
                pg_ids.append(uuid.UUID(item_id))
            except ValueError:
                pg_ids.append(uuid.uuid5(uuid.NAMESPACE_DNS, item_id))

        async with self.pool.acquire() as conn:  # type: ignore
            if namespace:
                await conn.execute(f"""
                    DELETE FROM {self.table_name}
                    WHERE id = ANY($1::uuid[]) AND metadata @> $2::jsonb
                """, pg_ids, json.dumps({"_namespace": namespace}))
            else:
                await conn.execute(f"""
                    DELETE FROM {self.table_name}
                    WHERE id = ANY($1::uuid[])
                """, pg_ids)

    async def close(self) -> None:
        """Closes the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None

