import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import ValidationError

from litellm_adk.vector.base import VectorItem, VectorSearchResult, VectorStore
from litellm_adk.vector.retriever import Retriever, RetrievalConfig
from litellm_adk.memory.backends.postgres import PostgresVectorStore, PostgresVectorStoreConfig
from litellm_adk.agent.agent import LiteLLMAgent


def test_vector_item_content_alias():
    item = VectorItem(text="Hello world")
    assert item.text == "Hello world"
    assert item.content == "Hello world"


def test_vector_search_result_dict_and_attr_access():
    item = VectorItem(id="test-123", text="Sample document", metadata={"source": "test"})
    result = VectorSearchResult(item=item, score=0.92)

    # Attribute access
    assert result.text == "Sample document"
    assert result.score == 0.92
    assert result.metadata == {"source": "test"}
    assert result.item.id == "test-123"

    # Dictionary-style access for backwards compatibility
    assert result["text"] == "Sample document"
    assert result["score"] == 0.92
    assert result["metadata"] == {"source": "test"}
    assert result["id"] == "test-123"
    assert result.get("score") == 0.92
    assert result.get("nonexistent", "fallback") == "fallback"


def test_postgres_vector_store_config_strict_fields():
    # Valid config
    config = PostgresVectorStoreConfig(
        connection_string="postgresql://user:pass@localhost:5432/db",
        embedding_model="gemini/gemini-embedding-001",
        vector_dim=768,
    )
    assert config.embedding_model == "gemini/gemini-embedding-001"
    assert config.vector_dim == 768

    # Misspelled field must raise ValidationError (ConfigDict extra="forbid")
    with pytest.raises(ValidationError):
        PostgresVectorStoreConfig(
            connection_string="postgresql://user:pass@localhost:5432/db",
            embeding_model="gemini/gemini-embedding-001",  # Typo!
        )


def test_postgres_vector_store_dimension_inference():
    # Gemini defaults to 768
    store_gemini = PostgresVectorStore.__new__(PostgresVectorStore)
    store_gemini.__init__(
        connection_string="postgresql://dummy:5432/db",
        embedding_model="gemini/gemini-embedding-001"
    )
    assert store_gemini.vector_dim == 768
    assert store_gemini.embedding_model == "gemini/gemini-embedding-001"

    # OpenAI defaults to 1536
    store_openai = PostgresVectorStore.__new__(PostgresVectorStore)
    store_openai.__init__(
        connection_string="postgresql://dummy:5432/db",
        embedding_model="text-embedding-3-small"
    )
    assert store_openai.vector_dim == 1536

    # Explicit override
    store_override = PostgresVectorStore.__new__(PostgresVectorStore)
    store_override.__init__(
        connection_string="postgresql://dummy:5432/db",
        embedding_model="gemini/gemini-embedding-001",
        vector_dim=512
    )
    assert store_override.vector_dim == 512


def test_postgres_vector_store_no_fallback_without_config():
    # When sentence-transformers is missing and no embedding model is given, raise ValueError
    with patch.dict("sys.modules", {"sentence_transformers": None}):
        store = PostgresVectorStore.__new__(PostgresVectorStore)
        with pytest.raises(ValueError, match="No embedding configuration provided"):
            store.__init__(connection_string="postgresql://dummy:5432/db")


@pytest.mark.asyncio
async def test_postgres_vector_store_search_protocol():
    store = PostgresVectorStore.__new__(PostgresVectorStore)
    store.table_name = "test_vectors"
    store.vector_dim = 768
    store.pool = MagicMock()

    # Mock pool acquire context manager
    mock_conn = AsyncMock()
    store.pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock fetch return row
    mock_conn.fetch.return_value = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "text": "Retrieved context fact",
            "metadata": '{"source": "demo", "_namespace": "default"}',
            "score": 0.85
        }
    ]

    dummy_embedding = [0.1] * 768

    # Test search with query_embedding (as called by Retriever)
    results = await store.search(query_embedding=dummy_embedding, top_k=3)

    assert len(results) == 1
    assert isinstance(results[0], VectorSearchResult)
    assert results[0].text == "Retrieved context fact"
    assert results[0].score == 0.85
    assert results[0]["text"] == "Retrieved context fact"
    assert results[0].metadata == {"source": "demo"}


@pytest.mark.asyncio
async def test_retriever_with_custom_embedder_store():
    store = PostgresVectorStore.__new__(PostgresVectorStore)
    store.vector_dim = 768
    store.embed = AsyncMock(return_value=[0.5] * 768)
    store.search = AsyncMock(return_value=[
        VectorSearchResult(
            item=VectorItem(text="Fact: emerald green", metadata={}),
            score=0.9
        )
    ])

    retriever = Retriever(vector_store=store, embedder=store)
    context = await retriever.retrieve_context("What is my favorite color?")

    store.embed.assert_awaited_once_with("What is my favorite color?")
    store.search.assert_awaited_once()
    assert context == ["Fact: emerald green"]


def test_agent_explicit_retrieval_and_typo_warning():
    store = PostgresVectorStore.__new__(PostgresVectorStore)
    store.vector_dim = 768
    store.embed = AsyncMock(return_value=[0.1] * 768)
    store.embed_batch = AsyncMock(return_value=[[0.1] * 768])
    store.search = AsyncMock(return_value=[])

    with patch("litellm_adk.agent.agent.adk_logger.warning") as mock_warn:
        agent = LiteLLMAgent(
            model="command-a-03-2025",
            api_key="sk-test",
            vector_store=store,
            vector_search_threshold=0.6,
            parallel_tool_calls=True,
            mispeled_argument=123,  # Should trigger warning
        )
        assert agent.retriever is not None
        assert agent.retriever.config.similarity_threshold == 0.6
        assert agent.execution_config.parallel_tool_calls is True
        mock_warn.assert_called_once()
        assert "mispeled_argument" in str(mock_warn.call_args)
