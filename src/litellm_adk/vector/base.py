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

    @property
    def content(self) -> str:
        """Alias for text to support content-centric workflows."""
        return self.text


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

    def __getitem__(self, key: str) -> Any:
        if key == "text":
            return self.text
        elif key == "metadata":
            return self.metadata
        elif key == "score":
            return self.score
        elif key == "id":
            return self.item.id
        elif key == "item":
            return self.item
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


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
