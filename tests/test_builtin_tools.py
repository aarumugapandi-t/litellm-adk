"""Unit tests for built-in framework tools and visual tool node connections."""

import pytest
from unittest.mock import patch, MagicMock
from litellm_adk.tools.builtin.web_search import perform_web_search, create_web_search_tool
from litellm_adk.tools.builtin.calculator import calculate, create_calculator_tool
from litellm_adk.workflow.schema import WorkflowDefinition, WorkflowNode, WorkflowEdge
from litellm_adk.workflow.state import ExecutionStatus
from litellm_adk.workflow.engine import WorkflowEngine
from litellm_adk.workflow.nodes.registry import node_registry


def test_builtin_web_search_tool():
    tool = create_web_search_tool(max_results=3)
    assert tool.name == "web_search"
    assert "query" in tool.definition["function"]["parameters"]["properties"]

    res = perform_web_search("Python FastAPI", max_results=2)
    assert "Web Search Results" in res
    assert "FastAPI" in res or "Python" in res


def test_builtin_calculator_tool():
    tool = create_calculator_tool()
    assert tool.name == "calculator"
    assert calculate("10 + 5 * 2") == "20"
    assert calculate("sqrt(144) + 8") == "20"
    assert calculate("2 ** 3") == "8"
    assert "Calculation Error" in calculate("invalid syntax !!")


def test_tool_node_registration():
    web_node = node_registry.get_node("web_search_tool")
    calc_node = node_registry.get_node("calculator_tool")
    http_node = node_registry.get_node("http_tool")

    assert web_node is not None
    assert calc_node is not None
    assert http_node is not None
    assert "tool" in web_node.definition.outputs
    assert "tool" in calc_node.definition.outputs


@pytest.mark.asyncio
async def test_agent_with_attached_tool_node_execution():
    """Verifies that an Agent node automatically receives tools wired via its 'tools' handle."""
    wf = WorkflowDefinition(
        id="agent_with_tool_wf",
        name="Agent With Tool Node",
        variables={"default_model": "openrouter/mistralai/ministral-3b-2512", "api_key": "sk-test-key"},
        nodes=[
            WorkflowNode(id="trig", type="manual_trigger"),
            WorkflowNode(id="search_node", type="web_search_tool", config={"max_results": 3}),
            WorkflowNode(
                id="agent_node",
                type="agent",
                config={"prompt": "Search for latest AI news"}
            ),
            WorkflowNode(id="out", type="output", config={"response": "{{ agent_node.output }}"}),
        ],
        edges=[
            WorkflowEdge(id="e1", source="trig", target="agent_node"),
            # Wire web search tool into Agent's 'tools' handle!
            WorkflowEdge(id="e2", source="search_node", target="agent_node", source_handle="tool", target_handle="tools"),
            WorkflowEdge(id="e3", source="agent_node", target="out"),
        ],
    )

    engine = WorkflowEngine()

    with patch("litellm_adk.workflow.nodes.agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.ainvoke = pytest.importorskip("unittest.mock").AsyncMock(return_value=MagicMock(
            status="completed",
            text="Here is the AI news from the attached web search tool.",
            tool_calls=[],
            usage=MagicMock(total_tokens=100),
            duration=0.2,
        ))
        MockAgent.return_value = mock_agent_instance

        state = await engine.execute(wf, trigger_data={"query": "AI News"})

        assert state.status == ExecutionStatus.COMPLETED
        assert state.node_outputs["out"] == "Here is the AI news from the attached web search tool."

        # Verify Agent was constructed with the attached web search tool!
        MockAgent.assert_called_once()
        call_kwargs = MockAgent.call_args[1]
        assert call_kwargs["api_key"] == "sk-test-key"  # Verified variable inheritance!
        tools_list = call_kwargs["tools"]
        assert any(getattr(t, "name", "") == "web_search" for t in tools_list)
