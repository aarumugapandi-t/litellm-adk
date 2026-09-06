"""Base protocols and data structures for vector storage and retrieval."""

import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
import uuid
from pydantic import BaseModel, Field


class VectorItem(BaseModel):
    """An individual text item indexed with its vector embedding."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    namespace: str = "default"
    created_at: float = Field(default_factory=time.time)


class VectorSearchResult(BaseModel):
    """Result from a similarity search query against a vector store."""

    item: VectorItem
    score: float

    @property
    def text(self) -> str:
        return self.item.text

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.item.metadata


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector storage engines."""

    async def add(self, items: List[VectorItem]) -> List[str]:
        """Adds vector items to the store and returns their IDs."""
        ...

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        similarity_threshold: Optional[float] = None,
        namespace: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Searches for items matching query_embedding."""
        ...

    async def delete(self, ids: List[str], namespace: Optional[str] = None) -> None:
        """Deletes items by ID."""
        ...

    async def get(self, id: str) -> Optional[VectorItem]:
        """Retrieves an item by ID."""
        ...
