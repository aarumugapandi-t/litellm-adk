"""Unit tests for autonomous tool retrieval, conditional transformers, multi-query RRF, and routing."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from litellm_adk.agent.agent import Agent
from litellm_adk.agent.config import AgentConfig
from litellm_adk.vector.base import VectorItem, VectorSearchResult
from litellm_adk.vector.retriever import RetrievalConfig, Retriever
from litellm_adk.vector.stores.in_memory import InMemoryVectorStore
from litellm_adk.vector.strategy import (
    MultiQueryConfig,
    QueryTransformationConfig,
    QueryTransformationResult,
    RetrievalMode,
    RetrievalStrategy,
)
from litellm_adk.vector.tool import RetrieverTool
from litellm_adk.vector.transformers import (
    ConditionalQueryTransformer,
    MultiQueryDecomposer,
    ReciprocalRankFusion,
    RetrievalRouter,
)


@pytest.mark.asyncio
async def test_retriever_tool_execution():
    """Verifies RetrieverTool executes search and formats results properly."""
    store = InMemoryVectorStore()
    await store.add_documents([
        "The standard refund window is 30 calendar days from purchase.",
        "VIP members receive an extended 60-day return policy.",
    ])
    retriever = Retriever(vector_store=store, top_k=2)
    tool = retriever.to_tool()

    assert isinstance(tool, RetrieverTool)
    assert tool.name == "search_knowledge_base"
    assert "query" in tool.definition["function"]["parameters"]["properties"]

    # Execute search
    res = await tool(query="refund window")
    assert "[1]" in res
    assert "30 calendar days" in res


@pytest.mark.asyncio
async def test_agent_auto_mounts_retriever_tool():
    """Verifies that an agent automatically mounts RetrieverTool into tool_registry by default."""
    store = InMemoryVectorStore()
    retriever = Retriever(vector_store=store)

    agent = Agent(
        model="gpt-4o",
        api_key="sk-test",
        retriever=retriever,
        retrieval_mode="tool",
    )

    assert agent.tool_registry.get_tool("search_knowledge_base") is not None
    tool_names = [t["function"]["name"] for t in agent.tools]
    assert "search_knowledge_base" in tool_names


@pytest.mark.asyncio
async def test_agent_autonomous_tool_calling():
    """Verifies the LLM autonomously chooses when to call search_knowledge_base."""
    store = InMemoryVectorStore()
    await store.add_documents(["Server error code 502 indicates a bad gateway upstream."])
    retriever = Retriever(vector_store=store, top_k=1)

    agent = Agent(
        model="gpt-4o",
        api_key="sk-test",
        retriever=retriever,
        retrieval_mode="tool",
    )

    # 1. Simulating turn where LLM decides to call the search tool
    tool_call_obj = MagicMock()
    tool_call_obj.id = "call_search_1"
    tool_call_obj.function = MagicMock()
    tool_call_obj.function.name = "search_knowledge_base"
    tool_call_obj.function.arguments = json.dumps({"query": "server error code 502"})

    step1_choice = MagicMock()
    step1_choice.message = MagicMock()
    step1_choice.message.content = ""
    step1_choice.message.tool_calls = [tool_call_obj]

    step1_resp = MagicMock()
    step1_resp.choices = [step1_choice]
    step1_resp.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)

    # Step 2: Final response after receiving tool results
    step2_choice = MagicMock()
    step2_choice.message = MagicMock()
    step2_choice.message.content = "Error 502 represents an upstream bad gateway error."
    step2_choice.message.tool_calls = None

    step2_resp = MagicMock()
    step2_resp.choices = [step2_choice]
    step2_resp.usage = MagicMock(prompt_tokens=30, completion_tokens=10, total_tokens=40)

    with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=[step1_resp, step2_resp]) as mock_acomp:
        res = await agent.run("What does error 502 mean?", session_id="test_tool_session")
        assert res.content == "Error 502 represents an upstream bad gateway error."
        assert mock_acomp.call_count == 2


@pytest.mark.asyncio
async def test_agent_chitchat_makes_zero_tool_calls():
    """Verifies that for a greeting, the agent answers directly without executing search."""
    store = InMemoryVectorStore()
    await store.add_documents(["Irrelevant documentation chunk."])
    retriever = Retriever(vector_store=store)

    agent = Agent(
        model="gpt-4o",
        api_key="sk-test",
        retriever=retriever,
        retrieval_mode="tool",
    )

    # LLM responds directly with 0 tool calls
    direct_choice = MagicMock()
    direct_choice.message = MagicMock()
    direct_choice.message.content = "Hello! How can I assist you today?"
    direct_choice.message.tool_calls = None

    direct_resp = MagicMock()
    direct_resp.choices = [direct_choice]
    direct_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=8, total_tokens=18)

    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=direct_resp) as mock_acomp:
        res = await agent.run("Hi there!", session_id="test_chitchat_session")
        assert res.content == "Hello! How can I assist you today?"
        assert mock_acomp.call_count == 1

        # Confirm no tool message in history
        history = await agent.conversation_memory.get_messages("test_chitchat_session")
        roles = [m["role"] for m in history]
        assert "tool" not in roles


@pytest.mark.asyncio
async def test_conditional_query_transformer_heuristics_and_llm():
    """Verifies ConditionalQueryTransformer skips greetings dynamically and rewrites ambiguous queries."""
    # 1. Configurable chitchat phrases / intent evaluator
    cfg = QueryTransformationConfig(custom_chitchat_phrases=["hello", "thanks a lot"])
    transformer = ConditionalQueryTransformer(config=cfg)

    res_hi = await transformer.transform("Hello!")
    assert not res_hi.needs_search

    res_thanks = await transformer.transform("Thanks a lot")
    assert not res_thanks.needs_search

    # 2. Dynamic model-driven classification (language and typo tolerant)
    mock_model = MagicMock()
    def _mock_generate(prompt):
        resp = MagicMock()
        if "hwllo" in prompt:
            resp.content = json.dumps({
                "needs_search": False,
                "reasoning": "Greeting with typo",
                "search_query": None,
            })
        else:
            resp.content = json.dumps({
                "needs_search": True,
                "reasoning": "User asks about pricing",
                "search_query": "Enterprise cloud pricing tiers and SLAs",
            })
        return resp

    mock_model.generate = AsyncMock(side_effect=_mock_generate)
    transformer_with_model = ConditionalQueryTransformer(model=mock_model)

    res_typo = await transformer_with_model.transform("hwllo there!")
    assert not res_typo.needs_search

    res_pricing = await transformer_with_model.transform(
        "What are their pricing tiers?",
        history=[{"role": "user", "content": "Tell me about enterprise cloud."}],
    )
    assert res_pricing.needs_search
    assert res_pricing.search_query == "Enterprise cloud pricing tiers and SLAs"


@pytest.mark.asyncio
async def test_retriever_conditional_transform_strategy():
    """Verifies Retriever with CONDITIONAL_TRANSFORM strategy avoids search when needs_search is False."""
    store = InMemoryVectorStore()
    await store.add_documents(["Database migration guide."])

    mock_model = MagicMock()
    def _mock_gen(prompt):
        resp = MagicMock()
        if "Hey" in prompt:
            resp.content = json.dumps({"needs_search": False, "search_query": None})
        else:
            resp.content = json.dumps({"needs_search": True, "search_query": "Database migration guide"})
        return resp
    mock_model.generate = AsyncMock(side_effect=_mock_gen)

    retriever = Retriever(
        vector_store=store,
        strategy=RetrievalStrategy.CONDITIONAL_TRANSFORM,
        transformer_model=mock_model,
    )

    # Greeting should yield empty docs without search
    docs_greeting = await retriever.retrieve_context("Hey!")
    assert docs_greeting == []

    # Factual query should retrieve
    docs_factual = await retriever.retrieve_context("Database migration guide")
    assert len(docs_factual) > 0


@pytest.mark.asyncio
async def test_reciprocal_rank_fusion():
    """Verifies RRF formula fuses, ranks, and deduplicates multiple result lists."""
    list1 = [
        VectorSearchResult(item=VectorItem(id="docA", text="Doc A text"), score=0.9),
        VectorSearchResult(item=VectorItem(id="docB", text="Doc B text"), score=0.8),
    ]
    list2 = [
        VectorSearchResult(item=VectorItem(id="docB", text="Doc B text"), score=0.85),
        VectorSearchResult(item=VectorItem(id="docC", text="Doc C text"), score=0.75),
    ]

    # Doc B appears in both lists (rank 1 in list1, rank 0 in list2) -> should have highest fused score
    fused = ReciprocalRankFusion.fuse([list1, list2], k=60)
    assert len(fused) == 3
    assert fused[0].item.id == "docB"
    assert fused[0].score > fused[1].score


@pytest.mark.asyncio
async def test_retrieval_router_dynamic_and_typo_tolerance():
    """Verifies RetrievalRouter directs queries accurately even with spelling mistakes."""
    router = RetrievalRouter()

    # Standard routing
    assert router.route_fuzzy("Compare AWS Lambda vs Google Cloud Functions") == RetrievalStrategy.MULTI_QUERY
    assert router.route_fuzzy("What was its previous release date?") == RetrievalStrategy.CONDITIONAL_TRANSFORM
    assert router.route_fuzzy("PostgreSQL connection pooling configuration") == RetrievalStrategy.DIRECT

    # Typo tolerance in comparative keywords (e.g. "copmare" -> "compare", "differnce" -> "difference")
    assert router.route_fuzzy("copmare AWS Lambda and GCP") == RetrievalStrategy.MULTI_QUERY
    assert router.route_fuzzy("What is the differnce between TCP and UDP?") == RetrievalStrategy.MULTI_QUERY

    # Typo tolerance in contextual pronouns (e.g. "theri" -> "their", "taht" -> "that")
    assert router.route_fuzzy("What was theri pricing?") == RetrievalStrategy.CONDITIONAL_TRANSFORM
    assert router.route_fuzzy("How does taht scale?") == RetrievalStrategy.CONDITIONAL_TRANSFORM

    # Model-based async routing
    mock_model = MagicMock()
    mock_model.generate = AsyncMock(return_value=MagicMock(content="multi_query"))
    model_router = RetrievalRouter(model=mock_model)
    assert await model_router.route("Any comparative query") == RetrievalStrategy.MULTI_QUERY


@pytest.mark.asyncio
async def test_retrieval_mode_configuration():
    """Verifies pipeline mode does not mount tool, while tool mode mounts tool without pre-retrieval."""
    store = InMemoryVectorStore()
    retriever = Retriever(vector_store=store)

    # Pipeline mode: tool should NOT be mounted
    agent_pipeline = Agent(
        model="gpt-4o",
        api_key="sk-test",
        retriever=retriever,
        retrieval_mode="pipeline",
    )
    assert agent_pipeline.tool_registry.get_tool("search_knowledge_base") is None

    # Both mode: tool IS mounted and pre-retrieval also active
    agent_both = Agent(
        model="gpt-4o",
        api_key="sk-test",
        retriever=retriever,
        retrieval_mode="both",
    )
    assert agent_both.tool_registry.get_tool("search_knowledge_base") is not None


@pytest.mark.asyncio
async def test_mixed_greeting_and_factual_intent_triggers_search():
    """Verifies that queries mixing courtesy words, typos, and factual requests still trigger search."""
    query = "Thanks, once more think I want to know about company's some policy"

    mock_model = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = json.dumps({
        "needs_search": True,
        "reasoning": "User asks for company policy after a thank-you pleasantry and typo.",
        "search_query": "company policy",
    })
    mock_model.generate = AsyncMock(return_value=mock_resp)

    transformer = ConditionalQueryTransformer(model=mock_model)
    result = await transformer.transform(query)

    assert result.needs_search is True
    assert result.search_query == "company policy"

