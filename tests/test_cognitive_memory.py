"""Tests for the Enterprise Cognitive Memory Architecture in LiteLLM ADK."""

import pytest
import asyncio
from typing import Dict, Any

from litellm_adk.memory.long_term import LongTermMemory, InMemoryStore
from litellm_adk.memory.working import WorkingMemory
from litellm_adk.session import Session, current_user_id, current_session_id
from litellm_adk.vector import InMemoryVectorStore, Retriever
from litellm_adk.vector.tool import RetrieverTool


@pytest.mark.asyncio
async def test_user_profile_store_tenant_isolation():
    """Verify deterministic profile attributes are strictly partitioned by user_id."""
    ltm = LongTermMemory()

    # Add attributes for Alice
    await ltm.add_profile_attribute(
        user_id="alice_sec_ops",
        key="tone",
        value="concise bullet points",
    )
    await ltm.add_profile_attribute(
        user_id="alice_sec_ops",
        key="role",
        value="Lead Infrastructure Architect",
    )

    # Add attributes for Bob
    await ltm.add_profile_attribute(
        user_id="bob_dev",
        key="tone",
        value="verbose explanations with code blocks",
    )

    # Check Alice's profile
    alice_profile = await ltm.get_profile("alice_sec_ops")
    assert alice_profile["tone"] == "concise bullet points"
    assert alice_profile["role"] == "Lead Infrastructure Architect"

    # Check Bob's profile
    bob_profile = await ltm.get_profile("bob_dev")
    assert bob_profile["tone"] == "verbose explanations with code blocks"
    assert "role" not in bob_profile

    # Check unknown user profile is empty
    charlie_profile = await ltm.get_profile("charlie_guest")
    assert charlie_profile == {}


@pytest.mark.asyncio
async def test_deterministic_profile_retrieval_unconditional():
    """Verify profile attributes load unconditionally without requiring keyword matches in prompt."""
    ltm = LongTermMemory()
    await ltm.add_profile_attribute(
        user_id="alice",
        key="formatting",
        value="concise bullet points",
    )

    # Query with zero keyword overlap with "formatting" or "bullet"
    context = await ltm.retrieve_user_context(
        user_id="alice",
        query="What is the weather in Tokyo?",
    )
    assert any("formatting: concise bullet points" in entry for entry in context)

    # Unknown user gets no profile context
    bob_context = await ltm.retrieve_user_context(
        user_id="bob",
        query="What is the weather in Tokyo?",
    )
    assert not any("concise bullet points" in entry for entry in bob_context)


@pytest.mark.asyncio
async def test_contextvars_scoping_in_long_term_memory():
    """Verify active request contextvar automatically scopes memory operations when user_id is omitted."""
    ltm = LongTermMemory()

    # Set contextvar to Alice
    token = current_user_id.set("alice_auto")
    try:
        # add_fact without passing user_id
        await ltm.add_fact("security_clearance", "Level 4")

        # Must be in Alice's profile
        alice_profile = await ltm.get_profile("alice_auto")
        assert alice_profile.get("security_clearance") == "Level 4"

        # Must NOT be in Bob's profile
        bob_profile = await ltm.get_profile("bob_auto")
        assert "security_clearance" not in bob_profile

        # retrieve_user_context without user_id defaults to active contextvar
        context = await ltm.retrieve_user_context(query="unrelated query")
        assert any("security_clearance: Level 4" in entry for entry in context)
    finally:
        current_user_id.reset(token)


@pytest.mark.asyncio
async def test_episodic_semantic_memory_isolation():
    """Verify episodic memory vector searches isolate chunks by user_id."""
    vstore = InMemoryVectorStore()
    ltm = LongTermMemory(episodic_store=vstore)

    await ltm.add_episodic_memory(
        user_id="alice",
        content="Alice decided to deploy the service in us-east-1 on AWS.",
    )
    await ltm.add_episodic_memory(
        user_id="bob",
        content="Bob decided to deploy the service in eu-central-1 on GCP.",
    )

    # Alice searches for deployment region
    alice_results = await ltm.search_episodic_memory(
        user_id="alice",
        query="deployment region cloud",
    )
    assert any("us-east-1" in r for r in alice_results)
    assert not any("eu-central-1" in r for r in alice_results)

    # Bob searches for deployment region
    bob_results = await ltm.search_episodic_memory(
        user_id="bob",
        query="deployment region cloud",
    )
    assert any("eu-central-1" in r for r in bob_results)
    assert not any("us-east-1" in r for r in bob_results)


@pytest.mark.asyncio
async def test_retriever_tool_chunk_deduplication():
    """Verify RetrieverTool deduplicates chunks across parallel tool calls in the same turn."""
    vstore = InMemoryVectorStore()
    await vstore.add_documents([
        "Policy A: Travel flights over 6 hours are business class.",
        "Policy B: Travel meals are reimbursed up to $75/day.",
    ])
    retriever = Retriever(vector_store=vstore, top_k=2)
    tool = RetrieverTool(retriever=retriever)

    # First call retrieves Policy A & Policy B
    res1 = await tool.execute(query="travel flight policy")
    assert "Policy A" in res1

    # Second concurrent/parallel call for similar query should suppress duplicate chunks
    res2 = await tool.execute(query="flight policy business class")
    assert "already retrieved in this turn" in res2 or "Policy A" not in res2

    # Reset cache for new turn
    tool.reset_cache()
    res3 = await tool.execute(query="travel flight policy")
    assert "Policy A" in res3


@pytest.mark.asyncio
async def test_working_memory_observation_tracking():
    """Verify WorkingMemory captures observations and scratchpad state."""
    wm = WorkingMemory()
    wm.set_task("Investigate alert 404")

    wm.record_tool_result("search_kb", {"query": "alert 404"}, "Found root cause: DNS failure")
    notes = wm.get_summary_notes()
    assert any("Found root cause: DNS failure" in n for n in notes)

    wm.clear()
    assert wm.get_summary_notes() == []
    assert wm.current_task is None


@pytest.mark.asyncio
async def test_agent_user_id_memory_injection():
    """Verify agent.run with user_id parameter dynamically injects profile attributes."""
    from unittest.mock import AsyncMock, patch
    from litellm_adk.agent import Agent
    from litellm_adk.models.base import ModelResponse

    ltm = LongTermMemory()
    await ltm.add_profile_attribute("alice", "coding_preference", "typed Python")

    agent = Agent(model="gpt-4o", api_key="sk-test", long_term_memory=ltm)
    mock_resp = ModelResponse(role="assistant", content="Understood.")

    with patch.object(agent.model, "generate", new_callable=AsyncMock, return_value=mock_resp) as mock_gen:
        res = await agent.run("Please write a function.", user_id="alice")
        assert res.content == "Understood."
        messages = mock_gen.call_args[1]["messages"]
        system_content = messages[0]["content"]
        assert "coding_preference: typed Python" in system_content


@pytest.mark.asyncio
async def test_agent_memory_placement_user_turn():
    """Verify ContextPolicy(memory_placement='user_turn') injects memories directly into the user message."""
    from unittest.mock import AsyncMock, patch
    from litellm_adk.agent import Agent
    from litellm_adk.context import ContextManager, ContextPolicy
    from litellm_adk.models.base import ModelResponse

    ltm = LongTermMemory()
    await ltm.add_profile_attribute("alice", "tone", "concise")

    ctx_mgr = ContextManager(policy=ContextPolicy(memory_placement="user_turn"))
    agent = Agent(model="gpt-4o", api_key="sk-test", long_term_memory=ltm, context_manager=ctx_mgr)
    mock_resp = ModelResponse(role="assistant", content="Hello!")

    with patch.object(agent.model, "generate", new_callable=AsyncMock, return_value=mock_resp) as mock_gen:
        await agent.run("Hello there!", user_id="alice")
        messages = mock_gen.call_args[1]["messages"]
        user_msg = messages[-1]
        assert user_msg["role"] == "user"
        assert "<user_memory>" in user_msg["content"]
        assert "tone: concise" in user_msg["content"]
        assert "Hello there!" in user_msg["content"]
        # System message should not have the memory block
        assert "### Long-Term Memory" not in messages[0]["content"]


@pytest.mark.asyncio
async def test_agent_stream_persists_conversation_memory():
    from unittest.mock import patch
    from litellm_adk.agent import Agent
    from litellm_adk.memory import InMemoryMemory
    from litellm_adk.models.base import ModelStreamChunk

    async def mock_stream(*args, **kwargs):
        yield ModelStreamChunk(content_delta="Streaming response.")

    mem = InMemoryMemory()
    agent = Agent(model="gpt-4o", api_key="sk-test", memory=mem)

    with patch.object(agent.model, "stream", side_effect=mock_stream):
        chunks = []
        async for delta in agent.astream("Tell me a fact.", session_id="stream_sess"):
            chunks.append(delta)

        assert "".join(chunks) == "Streaming response."

        # Verify conversation history was synced to backend
        history = await mem.get_messages("stream_sess")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Tell me a fact."
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Streaming response."

