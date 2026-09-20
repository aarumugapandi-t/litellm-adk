import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from litellm_adk.context import (
    ContextManager,
    ContextPlacement,
    ContextPolicy,
    ContextStrategy,
)
from litellm_adk.memory.working import WorkingMemory
from litellm_adk.memory.long_term import LongTermMemory
from litellm_adk.memory.conversation import ConversationMemory
from litellm_adk.vector import InMemoryVectorStore, Retriever
from litellm_adk.agent import Agent


def test_context_policy_and_strategies():
    """Verifies that ContextStrategy and ContextPolicy support the documented options."""
    policy = ContextPolicy(
        max_tokens=4096,
        strategy=ContextStrategy.SLIDING_WINDOW,
        preserve_system_prompt=True,
        preserve_last_n_messages=4,
        context_placement=ContextPlacement.USER_TURN,
    )
    assert policy.max_tokens == 4096
    assert policy.strategy == ContextStrategy.SLIDING_WINDOW
    assert policy.preserve_system_prompt is True
    assert policy.preserve_last_n_messages == 4
    assert policy.context_placement == "user_turn"

    # Also test backward compatibility aliases
    assert ContextStrategy.TRUNCATE == ContextStrategy.SLIDING_WINDOW
    assert ContextStrategy.SUMMARIZE == ContextStrategy.SUMMARIZATION
    assert ContextStrategy.SEMANTIC_TRUNCATION == "semantic_truncation"


def test_sliding_window_compaction_preserves_system_and_last_n():
    """Verifies sliding window preserves system prompt and the specified recent message window."""
    mgr = ContextManager(
        policy=ContextPolicy(
            max_tokens=50,
            strategy=ContextStrategy.SLIDING_WINDOW,
            preserve_system_prompt=True,
            preserve_last_n_messages=2,
            reserve_tokens=0,
        )
    )

    messages = [
        {"role": "system", "content": "System directive"},
        {"role": "user", "content": "Old message 1"},
        {"role": "assistant", "content": "Old answer 1"},
        {"role": "user", "content": "Recent question"},
        {"role": "assistant", "content": "Recent answer"},
    ]

    compacted = mgr.apply_compaction(messages, model="gpt-4")
    roles = [m["role"] for m in compacted]

    # System prompt must be preserved
    assert roles[0] == "system"
    assert compacted[0]["content"] == "System directive"

    # The last 2 messages (recent window) must be preserved
    assert compacted[-2]["content"] == "Recent question"
    assert compacted[-1]["content"] == "Recent answer"


def test_semantic_truncation_strips_older_tool_calls():
    """Verifies semantic truncation removes intermediate tool execution from older turns."""
    mgr = ContextManager(
        policy=ContextPolicy(
            max_tokens=60,
            strategy=ContextStrategy.SEMANTIC_TRUNCATION,
            preserve_system_prompt=True,
            preserve_last_n_messages=2,
            reserve_tokens=0,
        )
    )

    messages = [
        {"role": "system", "content": "System prompt"},
        # Older turn with tool calls
        {"role": "user", "content": "What is the weather?"},
        {
            "role": "assistant",
            "content": "Looking up...",
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "Sunny and 22C with very verbose detailed meteorological observations from satellite XYZ"},
        {"role": "assistant", "content": "The weather in Paris is sunny and 22C."},
        # Recent turn (preserved)
        {"role": "user", "content": "Great, and what about dinner?"},
        {"role": "assistant", "content": "I recommend a bistro nearby."},
    ]

    compacted = mgr.apply_compaction(messages, model="gpt-4")
    compacted_roles = [m["role"] for m in compacted]

    # Raw tool message from older turn should be pruned
    assert "tool" not in compacted_roles

    # Recent turns must be retained
    assert compacted[-2]["content"] == "Great, and what about dinner?"
    assert compacted[-1]["content"] == "I recommend a bistro nearby."


def test_summarization_compaction():
    """Verifies summarization condenses older turns outside preserve_last_n_messages."""
    mgr = ContextManager(
        policy=ContextPolicy(
            max_tokens=95,
            strategy=ContextStrategy.SUMMARIZATION,
            preserve_system_prompt=True,
            preserve_last_n_messages=2,
            reserve_tokens=0,
        )
    )

    messages = [
        {"role": "system", "content": "Assistant instructions"},
        {
            "role": "user",
            "content": "My name is Alice and I am a senior software engineer living in Berlin working on distributed systems with high concurrency and microservices architectures.",
        },
        {
            "role": "assistant",
            "content": "Nice to meet you Alice! Distributed systems in Berlin sounds like an exciting domain to work on with modern distributed frameworks.",
        },
        {
            "role": "user",
            "content": "I primarily write Python for backend data services and Rust for high-throughput network proxies and low-latency packet processing.",
        },
        {
            "role": "assistant",
            "content": "Both are excellent choices. Python provides great developer velocity for APIs, while Rust ensures zero-cost abstractions and memory safety without garbage collection pauses.",
        },
        # Recent turns
        {"role": "user", "content": "What project should I build?"},
        {"role": "assistant", "content": "You could build a fast CLI tool in Rust."},
    ]

    compacted = mgr.apply_compaction(messages, model="gpt-4")

    # Should contain system summary block
    summary_msgs = [m for m in compacted if "Previous Conversation Summary" in m.get("content", "")]
    assert len(summary_msgs) == 1
    assert "- User:" in summary_msgs[0]["content"]

    # Recent window preserved
    assert compacted[-2]["content"] == "What project should I build?"
    assert compacted[-1]["content"] == "You could build a fast CLI tool in Rust."


def test_ephemeral_rag_context_placement_in_user_turn():
    """Verifies that retrieved documents are placed ephemerally in the user turn by default."""
    mgr = ContextManager(
        policy=ContextPolicy(context_placement=ContextPlacement.USER_TURN)
    )

    messages = mgr.assemble_messages(
        system_prompt="You are a helpful assistant.",
        conversation_history=[],
        current_prompt="What is my favorite color?",
        long_term_memories=["Favorite color: Emerald Green"],
        retrieved_documents=["Fact: Emerald Green is a vibrant shade of green."],
    )

    # 1. System prompt should contain long-term persistent memories, but NOT retrieved docs
    system_content = messages[0]["content"]
    assert "### Long-Term Memory / Known Facts:" in system_content
    assert "Favorite color: Emerald Green" in system_content
    assert "### Retrieved Reference Context:" not in system_content

    # 2. User turn should contain the ephemeral <context> block wrapped around the question
    user_msg = messages[-1]
    assert user_msg["role"] == "user"
    assert "<context>" in user_msg["content"]
    assert "Fact: Emerald Green is a vibrant shade of green." in user_msg["content"]
    assert "</context>\n\nWhat is my favorite color?" in user_msg["content"]


def test_system_prompt_placement_fallback():
    """Verifies backward compatibility when context_placement='system_prompt'."""
    mgr = ContextManager(
        policy=ContextPolicy(context_placement=ContextPlacement.SYSTEM_PROMPT)
    )

    messages = mgr.assemble_messages(
        system_prompt="You are a helpful assistant.",
        conversation_history=[],
        current_prompt="What is my favorite color?",
        retrieved_documents=["Fact: Emerald Green is a vibrant shade of green."],
    )

    system_content = messages[0]["content"]
    assert "### Retrieved Reference Context:" in system_content
    assert "Fact: Emerald Green is a vibrant shade of green." in system_content

    user_msg = messages[-1]
    assert user_msg["content"] == "What is my favorite color?"


@pytest.mark.asyncio
async def test_working_memory_lifecycle_and_pruning_in_agent():
    """Verifies working memory holds retrieved documents during execution and prunes them upon completion."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Your favorite color is Emerald Green.", role="assistant", tool_calls=None))]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    vector_store = InMemoryVectorStore()
    await vector_store.add_documents(["Emerald Green is the user's favorite color."])
    retriever = Retriever(vector_store=vector_store, top_k=1)

    working_memory = WorkingMemory()
    long_term_memory = LongTermMemory()
    await long_term_memory.add_fact("location", "New York")

    agent = Agent(
        model="gpt-4o",
        api_key="sk-test",
        retriever=retriever,
        working_memory=working_memory,
        long_term_memory=long_term_memory,
    )

    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
        res = await agent.run("What is my favorite color?", session_id="session_test")
        assert res.content == "Your favorite color is Emerald Green."

        # Working memory should be cleared after the turn completes
        assert len(working_memory.retrieved_documents) == 0
        assert working_memory.current_task is None

        # Conversation memory should contain ONLY clean user query and assistant answer (no raw chunk bloat)
        history = await agent.conversation_memory.get_messages("session_test")
        assert len(history) == 2
        assert history[0]["content"] == "What is my favorite color?"
        assert "<context>" not in history[0]["content"]
        assert history[1]["content"] == "Your favorite color is Emerald Green."


@pytest.mark.asyncio
async def test_documentation_snippet_compatibility():
    """Executes the exact snippets from docs/08-memory-context-management.md to guarantee 100% compliance."""
    # Snippet 1: Section 3 ContextManager with ContextPolicy
    context_mgr = ContextManager(
        policy=ContextPolicy(
            max_tokens=4096,
            strategy=ContextStrategy.SLIDING_WINDOW,
            preserve_system_prompt=True,
            preserve_last_n_messages=4,
        )
    )
    assert context_mgr.policy.max_tokens == 4096
    assert context_mgr.policy.strategy == ContextStrategy.SLIDING_WINDOW

    # Snippet 2: Section 4 Vector Store & RAG Retrieval
    vector_store = InMemoryVectorStore()
    await vector_store.add_documents([
        "Company refund policy: Returns are accepted within 30 days with receipt.",
        "Shipping policy: Free ground shipping applies to orders over $50.",
    ])

    retriever = Retriever(vector_store=vector_store, top_k=2)
    assert retriever.config.top_k == 2

    agent = Agent(
        model="gpt-4o",
        api_key="sk-fake",
        retriever=retriever,
        system_prompt="Answer customer policy questions accurately using retrieved knowledge.",
        context_manager=context_mgr,
    )
    assert agent.retriever is not None
    assert agent.context_manager == context_mgr
