"""Comprehensive test suite verifying adherence to architecture.md standards."""

import asyncio
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel
import pytest

from litellm_adk import (
    Agent,
    AgentConfig,
    AgentLifecycleState,
    AgentResult,
    AgentStarted,
    ApprovalDecision,
    CallbackHumanLoop,
    ConsoleHumanLoop,
    ContextManager,
    ConversationMemory,
    ExecutionConfig,
    ExecutionTimeoutError,
    HumanApprovalRequired,
    HumanInTheLoop,
    HumanInterventionError,
    InMemoryMemory,
    InMemoryRunStore,
    InMemorySessionStore,
    InMemoryVectorStore,
    LiteLLMAgent,
    LiteLLMModel,
    LoggingMiddleware,
    LongTermMemory,
    MaxIterationsError,
    MemoryPolicy,
    MiddlewarePipeline,
    ModelConfig,
    ModelResponse,
    ModelUsage,
    OutputParser,
    OutputValidationError,
    PIIScrubbingMiddleware,
    Retriever,
    SimpleEmbedder,
    Supervisor,
    Tool,
    ToolCallRecord,
    ToolExecutor,
    ToolPermission,
    ToolPermissionError,
    ToolRegistry,
    ToolTimeoutError,
    VectorItem,
    WorkingMemory,
    agent_as_tool,
    tool,
)


# ---------------------------------------------------------------------------
# 1. Models & Configuration Tests
# ---------------------------------------------------------------------------

def test_model_config_initialization():
    cfg = ModelConfig(
        model="groq/llama-3.3-70b",
        temperature=0.2,
        max_tokens=1000,
        timeout=30.0,
    )
    assert cfg.model == "groq/llama-3.3-70b"
    assert cfg.temperature == 0.2
    assert cfg.max_tokens == 1000
    assert cfg.timeout == 30.0


def test_agent_config_from_dict_and_yaml():
    data = {
        "name": "ResearchBot",
        "description": "Performs scientific research.",
        "model": "openai/gpt-4o",
        "system_prompt": "You are a research scientist.",
    }
    cfg = AgentConfig.from_dict(data)
    assert cfg.name == "ResearchBot"
    assert cfg.model == "openai/gpt-4o"

    yaml_str = """
name: YamlBot
model: anthropic/claude-3-5-sonnet
system_prompt: You are a YAML agent.
"""
    cfg_yaml = AgentConfig.from_yaml(yaml_str)
    assert cfg_yaml.name == "YamlBot"
    assert cfg_yaml.model == "anthropic/claude-3-5-sonnet"


# ---------------------------------------------------------------------------
# 2. Tool System Tests
# ---------------------------------------------------------------------------

def test_tool_schema_generation():
    @tool(name="calc_add", description="Add two integers", permissions={ToolPermission.READ})
    def add_numbers(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    assert isinstance(add_numbers, Tool)
    assert add_numbers.name == "calc_add"
    assert add_numbers.description == "Add two integers"
    assert ToolPermission.READ in add_numbers.permissions

    defn = add_numbers.definition
    assert defn["type"] == "function"
    assert defn["function"]["name"] == "calc_add"
    props = defn["function"]["parameters"]["properties"]
    assert props["x"]["type"] == "integer"
    assert props["y"]["type"] == "integer"
    assert defn["function"]["parameters"]["required"] == ["x", "y"]


def test_tool_executor_permissions():
    registry = ToolRegistry()

    @registry.register(permissions={ToolPermission.DANGEROUS})
    def wipe_database():
        return "wiped"

    # Executor allowing only READ permissions
    executor = ToolExecutor(registry=registry, allowed_permissions={ToolPermission.READ})

    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(ToolPermissionError) as exc_info:
            loop.run_until_complete(
                executor.execute_tool_call(
                    tool_name="wipe_database",
                    tool_call_id="call_1",
                    arguments={},
                )
            )
        assert "Permission denied" in str(exc_info.value)
    finally:
        loop.close()


def test_tool_executor_timeout():
    registry = ToolRegistry()

    @registry.register(timeout=0.05, error_policy="raise")
    def slow_tool():
        import time
        time.sleep(0.2)
        return "done"

    executor = ToolExecutor(registry=registry, default_error_policy="raise")

    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(ToolTimeoutError):
            loop.run_until_complete(
                executor.execute_tool_call(
                    tool_name="slow_tool",
                    tool_call_id="call_2",
                    arguments={},
                )
            )
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# 3. Multi-Layer Memory Tests
# ---------------------------------------------------------------------------

def test_working_memory():
    wm = WorkingMemory()
    wm.set_task("Summarize AI papers")
    wm.set_plan(["Search arXiv", "Extract key takeaways", "Format markdown"])
    wm.add_observation("Found 10 papers matching query.")

    notes = wm.get_summary_notes()
    assert any("Summarize AI papers" in n for n in notes)
    assert any("Search arXiv" in n for n in notes)
    assert any("Found 10 papers" in n for n in notes)

    wm.clear()
    assert wm.current_task is None
    assert len(wm.plan) == 0


def test_long_term_memory():
    ltm = LongTermMemory()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ltm.add_fact("user_style", "Prefers concise bullet points"))
        fact = loop.run_until_complete(ltm.get_fact("user_style"))
        assert fact == "Prefers concise bullet points"

        results = loop.run_until_complete(ltm.retrieve_relevant_facts("bullet points style"))
        assert len(results) > 0
        assert "user_style" in results[0]
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# 4. Vector Store & RAG Tests
# ---------------------------------------------------------------------------

def test_in_memory_vector_store_and_retriever():
    embedder = SimpleEmbedder(dimensions=32)
    vector_store = InMemoryVectorStore()
    retriever = Retriever(vector_store=vector_store, embedder=embedder)

    docs = [
        "Quantum computing uses qubits and superposition.",
        "Deep learning employs convolutional neural networks.",
        "LiteLLM provides unified model routing across providers.",
    ]

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(retriever.add_documents(docs))
        results = loop.run_until_complete(retriever.retrieve_context("Tell me about qubits"))
        assert len(results) > 0
        assert "Quantum computing" in results[0]
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# 5. Structured Output & Parser Tests
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    name: str
    age: int
    interests: List[str]


def test_output_parser():
    json_text = """
    Here is the requested user profile:
    ```json
    {
        "name": "Alice",
        "age": 30,
        "interests": ["quantum computing", "AI"]
    }
    ```
    """
    profile = OutputParser.parse_as_model(json_text, UserProfile)
    assert profile.name == "Alice"
    assert profile.age == 30
    assert "quantum computing" in profile.interests

    # Trailing comma recovery
    trailing_comma_json = """{"name": "Bob", "age": 25, "interests": ["rust",],}"""
    bob = OutputParser.parse_as_model(trailing_comma_json, UserProfile)
    assert bob.name == "Bob"

    # Schema instruction generation
    instruction = OutputParser.get_schema_instruction(UserProfile)
    assert "JSON Schema" in instruction
    assert "UserProfile" in instruction or "name" in instruction

    # ContextManager upfront injection of response_model
    cm = ContextManager()
    msgs = cm.assemble_messages(
        system_prompt="Base system.",
        conversation_history=[],
        current_prompt="Tell me about Bob.",
        response_model=UserProfile,
    )
    assert "Output Format Requirement" in msgs[0]["content"]
    assert "JSON Schema" in msgs[0]["content"]

    # Repair prompt generation on error
    bad_text = "This is not valid json at all."
    with pytest.raises(OutputValidationError) as exc:
        OutputParser.parse_as_model(bad_text, UserProfile)

    repair_prompt = OutputParser.build_repair_prompt(bad_text, exc.value, UserProfile)
    assert "Expected JSON Schema" in repair_prompt
    assert "UserProfile" in str(exc.value) or "validation" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 6. Human-in-the-Loop Tests
# ---------------------------------------------------------------------------

def test_callback_human_loop_approval():
    async def approve_all(tool_name, tool_call_id, args):
        return args

    hitl = CallbackHumanLoop(approval_callback=approve_all)
    loop = asyncio.new_event_loop()
    try:
        res = loop.run_until_complete(hitl.request_approval("send_email", "call_1", {"to": "test@example.com"}))
        assert res["to"] == "test@example.com"
    finally:
        loop.close()


def test_callback_human_loop_rejection():
    async def reject_all(tool_name, tool_call_id, args):
        return False

    hitl = CallbackHumanLoop(approval_callback=reject_all)
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(HumanInterventionError):
            loop.run_until_complete(hitl.request_approval("delete_account", "call_2", {}))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# 7. Agent Execution Loop & Orchestrator Tests
# ---------------------------------------------------------------------------

def test_agent_orchestrator_mocked_run():
    # Setup mock model
    mock_model = MagicMock()
    mock_model.model_name = "test-model"

    # Turn 1: tool call
    # Turn 2: final answer
    response_1 = ModelResponse(
        content=None,
        tool_calls=[
            {
                "id": "call_calc",
                "type": "function",
                "function": {"name": "calc", "arguments": '{"x": 10, "y": 20}'},
            }
        ],
        usage=ModelUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
    )
    response_2 = ModelResponse(
        content="The calculated sum is 30.",
        tool_calls=[],
        usage=ModelUsage(prompt_tokens=30, completion_tokens=10, total_tokens=40),
    )

    mock_model.generate = AsyncMock(side_effect=[response_1, response_2])
    mock_model.aclose = AsyncMock()

    @tool
    def calc(x: int, y: int) -> int:
        return x + y

    agent = Agent(
        name="MathAssistant",
        model=mock_model,
        system_prompt="You are a math assistant.",
        tools=[calc],
    )

    events_received = []
    agent.on("*", lambda ev: events_received.append(ev.type))

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(agent.run("What is 10 + 20?"))
        assert isinstance(result, AgentResult)
        assert result.text == "The calculated sum is 30."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "calc"
        assert result.tool_calls[0].result == "30"
        assert result.iterations == 2
        assert "agent.started" in events_received
        assert "tool.started" in events_received
        assert "tool.completed" in events_received
        assert "agent.finished" in events_received

        # Backward compatibility properties
        assert result.content == "The calculated sum is 30."
        assert str(result) == "The calculated sum is 30."
    finally:
        loop.close()


def test_agent_max_iterations_error():
    mock_model = MagicMock()
    mock_model.model_name = "loop-model"

    # Keep returning tool call indefinitely
    mock_model.generate = AsyncMock(
        return_value=ModelResponse(
            content=None,
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "ping", "arguments": "{}"}}],
        )
    )

    @tool
    def ping():
        return "pong"

    agent = Agent(
        model=mock_model,
        tools=[ping],
        execution_config=ExecutionConfig(max_iterations=3),
    )

    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(MaxIterationsError):
            loop.run_until_complete(agent.run("Loop test"))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# 8. Multi-Agent Coordination Tests
# ---------------------------------------------------------------------------

def test_agent_as_tool_and_supervisor():
    # Worker agent mock
    worker_model = MagicMock()
    worker_model.model_name = "worker-model"
    worker_model.generate = AsyncMock(
        return_value=ModelResponse(content="Data retrieved from database.")
    )
    worker_model.aclose = AsyncMock()

    worker = Agent(name="DatabaseWorker", model=worker_model, description="Fetches SQL records.")

    # Convert worker to tool
    w_tool = agent_as_tool(worker)
    assert w_tool.name == "databaseworker"
    assert "DatabaseWorker" in w_tool.description

    # Supervisor mock
    supervisor_model = MagicMock()
    supervisor_model.model_name = "supervisor-model"
    supervisor_model.generate = AsyncMock(
        side_effect=[
            ModelResponse(
                tool_calls=[
                    {
                        "id": "worker_call",
                        "type": "function",
                        "function": {"name": "databaseworker", "arguments": '{"query": "SELECT * FROM users"}'},
                    }
                ]
            ),
            ModelResponse(content="Final summary: Data retrieved from database."),
        ]
    )
    supervisor_model.aclose = AsyncMock()

    supervisor = Supervisor(agents=[worker], model=supervisor_model)

    loop = asyncio.new_event_loop()
    try:
        res = loop.run_until_complete(supervisor.run("Get users list"))
        assert "Data retrieved" in res.text
        assert supervisor.sub_agents != None
    finally:
        loop.close()


def test_custom_base_url_openai_prefixing():
    # Test that any custom base_url forces openai/ prefixing for proxy compatibility
    agent = Agent(
        name="ProxyAgent",
        model="command-a-03-2025",
        base_url="http://localhost:9000/v1",
        api_key="sk-1234",
    )
    assert agent.model == "openai/command-a-03-2025"
    assert str(agent.model) == "openai/command-a-03-2025"


def test_strict_provider_message_and_tool_call_sanitization():
    # Verify LiteLLMModel removes incompatible 'index' and extra keys before sending to LLM
    raw_tool_call = {
        "index": 0,
        "id": "call_abc123",
        "type": "function",
        "function": {"name": "transfer_funds", "arguments": '{"amount": 100}'},
        "extra_field": "disallowed",
    }
    sanitized_tc = LiteLLMModel._sanitize_tool_call(raw_tool_call)
    assert "index" not in sanitized_tc
    assert "extra_field" not in sanitized_tc
    assert sanitized_tc["id"] == "call_abc123"
    assert sanitized_tc["type"] == "function"
    assert sanitized_tc["function"]["name"] == "transfer_funds"

    # Verify tool message sanitization (strips 'name', ensures clean payload)
    raw_tool_msg = {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "name": "transfer_funds",
        "content": "Success",
        "token_count": 42,
    }
    sanitized_tool_msg = LiteLLMModel._sanitize_message(raw_tool_msg)
    assert sanitized_tool_msg == {
        "role": "tool",
        "content": "Success",
        "tool_call_id": "call_abc123",
    }

    # Verify assistant message with tool calls sanitization
    assistant_msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [raw_tool_call],
    }
    sanitized_asst_msg = LiteLLMModel._sanitize_message(assistant_msg)
    assert sanitized_asst_msg["role"] == "assistant"
    assert "index" not in sanitized_asst_msg["tool_calls"][0]


