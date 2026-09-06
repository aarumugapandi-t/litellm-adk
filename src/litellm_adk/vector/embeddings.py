"""Embedding abstractions and implementations."""

import hashlib
import math
from typing import List, Optional, Protocol, runtime_checkable
import litellm

from ..exceptions import VectorStoreError
from ..observability.logger import adk_logger


@runtime_checkable
class Embedder(Protocol):
    """Protocol for generating vector embeddings."""

    async def embed(self, text: str) -> List[float]:
        """Generate embedding vector for a single text."""
        ...

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of texts."""
        ...


class LiteLLMEmbedder:
    """Embedder using LiteLLM's embedding gateway."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key

    async def embed(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            kwargs = {"model": self.model, "input": texts}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            response = await litellm.aembedding(**kwargs)
            return [data["embedding"] for data in response.data]
        except Exception as e:
            adk_logger.error(f"Embedding generation failed: {e}")
            raise VectorStoreError(f"Embedding error: {str(e)}", operation="embed_batch") from e


class SimpleEmbedder:
    """Deterministic, zero-dependency lightweight embedder for tests and local development."""

    def __init__(self, dimensions: int = 64):
        self.dimensions = dimensions

    async def embed(self, text: str) -> List[float]:
        words = text.lower().split()
        vector = [0.0] * self.dimensions

        for word in words:
            clean_word = "".join(c for c in word if c.isalnum())
            if not clean_word:
                continue
            h = int(hashlib.md5(clean_word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimensions
            sign = 1.0 if (h >> 16) & 1 else -1.0
            vector[idx] += sign

        # Normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed(t) for t in texts]
