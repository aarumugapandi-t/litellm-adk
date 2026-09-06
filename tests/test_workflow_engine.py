"""Unit tests for the LiteLLM ADK Workflow Engine, expressions, DAGs, and nodes."""

import pytest
from unittest.mock import patch, MagicMock
from litellm_adk.workflow.schema import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowEdge,
    WorkflowSettings,
    WorkflowStatus,
)
from litellm_adk.workflow.expressions import evaluate_template, resolve_expression
from litellm_adk.workflow.graph import WorkflowGraph, WorkflowGraphError
from litellm_adk.workflow.state import ExecutionStatus
from litellm_adk.workflow.engine import WorkflowEngine
from litellm_adk.workflow.nodes.registry import node_registry


def test_workflow_schema_serialization():
    wf = WorkflowDefinition(
        id="test_wf",
        name="Test Workflow",
        nodes=[
            WorkflowNode(id="n1", type="manual_trigger", name="Trigger"),
            WorkflowNode(id="n2", type="output", name="Output", config={"response": "{{ n1.output }}"}),
        ],
        edges=[WorkflowEdge(id="e1", source="n1", target="n2")],
    )
    assert wf.id == "test_wf"
    assert len(wf.nodes) == 2
    assert len(wf.edges) == 1
    dumped = wf.model_dump()
    assert dumped["name"] == "Test Workflow"
    restored = WorkflowDefinition.model_validate(dumped)
    assert restored.id == wf.id


def test_safe_expression_evaluator():
    ctx = {
        "trigger": {"user_id": 42, "name": "Alice"},
        "node_1": {"output": {"scores": [95, 88], "status": "approved"}},
        "variables": {"env": "production"},
    }

    # Single path preserving type
    assert evaluate_template("{{ trigger.user_id }}", ctx) == 42
    assert evaluate_template("{{ node_1.output.scores }}", ctx) == [95, 88]

    # String interpolation
    res_str = evaluate_template("User {{ trigger.name }} in {{ variables.env }} has status {{ node_1.output.status }}", ctx)
    assert res_str == "User Alice in production has status approved"

    # Missing path returns empty string in template
    assert evaluate_template("Missing: {{ trigger.nonexistent }}", ctx) == "Missing: "

    # Security: injection attempts return None/empty
    assert resolve_expression("__class__", ctx) is None
    assert resolve_expression("eval('1+1')", ctx) is None


def test_graph_validation_and_cycle_detection():
    # Valid DAG
    wf_valid = WorkflowDefinition(
        id="valid_dag",
        name="Valid DAG",
        nodes=[
            WorkflowNode(id="a", type="manual_trigger"),
            WorkflowNode(id="b", type="transform"),
            WorkflowNode(id="c", type="output"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ],
    )
    graph = WorkflowGraph(wf_valid)
    graph.validate()
    batches = graph.get_topological_batches()
    assert len(batches) == 3
    assert batches[0][0].id == "a"
    assert batches[1][0].id == "b"
    assert batches[2][0].id == "c"

    # Cycle DAG
    wf_cycle = WorkflowDefinition(
        id="cycle_dag",
        name="Cycle DAG",
        nodes=[
            WorkflowNode(id="x", type="transform"),
            WorkflowNode(id="y", type="transform"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="x", target="y"),
            WorkflowEdge(id="e2", source="y", target="x"),
        ],
    )
    graph_cycle = WorkflowGraph(wf_cycle)
    with pytest.raises(WorkflowGraphError):
        graph_cycle.validate()


@pytest.mark.asyncio
async def test_linear_workflow_execution():
    wf = WorkflowDefinition(
        id="linear_wf",
        name="Linear Pipeline",
        nodes=[
            WorkflowNode(id="trig", type="manual_trigger"),
            WorkflowNode(
                id="trans",
                type="transform",
                config={"template": {"greeting": "Hello {{ trigger.name }}!"}}
            ),
            WorkflowNode(
                id="out",
                type="output",
                config={"response": "{{ trans.output.greeting }}"}
            ),
        ],
        edges=[
            WorkflowEdge(id="e1", source="trig", target="trans"),
            WorkflowEdge(id="e2", source="trans", target="out"),
        ],
    )

    engine = WorkflowEngine()
    events = []
    engine.subscribe(lambda et, data: events.append(et))

    state = await engine.execute(wf, trigger_data={"name": "Antigravity"})

    assert state.status == ExecutionStatus.COMPLETED
    assert "workflow.started" in events
    assert "workflow.completed" in events
    assert state.node_outputs["trans"] == {"greeting": "Hello Antigravity!"}
    assert state.node_outputs["out"] == "Hello Antigravity!"


@pytest.mark.asyncio
async def test_conditional_branching_execution():
    wf = WorkflowDefinition(
        id="branch_wf",
        name="Conditional Workflow",
        nodes=[
            WorkflowNode(id="trig", type="manual_trigger"),
            WorkflowNode(
                id="cond",
                type="condition",
                config={"left_value": "{{ trigger.score }}", "operator": "greater_than", "right_value": "80"}
            ),
            WorkflowNode(
                id="pass_node",
                type="transform",
                config={"template": {"result": "PASSED"}}
            ),
            WorkflowNode(
                id="fail_node",
                type="transform",
                config={"template": {"result": "FAILED"}}
            ),
        ],
        edges=[
            WorkflowEdge(id="e1", source="trig", target="cond"),
            WorkflowEdge(id="e2", source="cond", target="pass_node", source_handle="true"),
            WorkflowEdge(id="e3", source="cond", target="fail_node", source_handle="false"),
        ],
    )

    engine = WorkflowEngine()

    # Scenario 1: Score 95 -> True branch
    state1 = await engine.execute(wf, trigger_data={"score": 95})
    assert state1.status == ExecutionStatus.COMPLETED
    assert "pass_node" in state1.completed_nodes
    assert "fail_node" not in state1.completed_nodes
    assert state1.node_outputs["pass_node"] == {"result": "PASSED"}

    # Scenario 2: Score 60 -> False branch
    state2 = await engine.execute(wf, trigger_data={"score": 60})
    assert state2.status == ExecutionStatus.COMPLETED
    assert "fail_node" in state2.completed_nodes
    assert "pass_node" not in state2.completed_nodes
    assert state2.node_outputs["fail_node"] == {"result": "FAILED"}


@pytest.mark.asyncio
async def test_human_in_the_loop_pause_and_resume():
    wf = WorkflowDefinition(
        id="hitl_wf",
        name="HITL Workflow",
        nodes=[
            WorkflowNode(id="trig", type="manual_trigger"),
            WorkflowNode(
                id="review",
                type="human",
                config={"message": "Please approve transfer of ${{ trigger.amount }}"}
            ),
            WorkflowNode(
                id="finish",
                type="output",
                config={"response": "{{ review.output }}"}
            ),
        ],
        edges=[
            WorkflowEdge(id="e1", source="trig", target="review"),
            WorkflowEdge(id="e2", source="review", target="finish", source_handle="approved"),
        ],
    )

    engine = WorkflowEngine()

    # Step 1: Execute -> Should pause at HumanNode
    state = await engine.execute(wf, trigger_data={"amount": 1000})
    assert state.status == ExecutionStatus.WAITING_FOR_HUMAN
    assert state.pending_approval is not None
    assert "1000" in state.pending_approval["message"]

    # Step 2: Resume with human approval
    decision = {"approved": True, "user_input": "Approved by auditor"}
    resumed_state = await engine.execute(
        wf,
        existing_state=state,
        human_decision=decision,
    )

    assert resumed_state.status == ExecutionStatus.COMPLETED
    assert resumed_state.node_outputs["finish"] == decision


@pytest.mark.asyncio
async def test_agent_node_configuration_and_execution():
    from litellm_adk.workflow.nodes.agent import AgentNode
    from litellm_adk.workflow.nodes.base import NodeContext
    from unittest.mock import AsyncMock

    node = AgentNode()
    schema = node.definition.config_schema
    assert "model" in schema["properties"]
    assert "api_key" in schema["properties"]
    assert "base_url" in schema["properties"]
    assert "tools" in schema["properties"]
    assert schema["properties"]["api_key"]["format"] == "password"
    assert "model" in schema["required"]
    assert "api_key" in schema["required"]
    assert "base_url" in schema["required"]

    context = NodeContext(
        workflow_id="test_wf",
        node_id="agent_fin",
        node_config={
            "model": "openrouter/mistralai/ministral-3b-2512",
            "api_key": "sk-1234",
            "base_url": "http://localhost:9000/v1",
            "system_prompt": "You are a financial advisor assistant.",
            "prompt": "Explain what the stock prices mean for {{ trigger.symbol }}",
            "tools": ["fetch_stock_price"],
        },
        inputs={},
        trigger_data={"symbol": "NVDA"},
        variables={},
        execution_id="exec_test_agent",
    )

    with patch("litellm_adk.workflow.nodes.agent.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.ainvoke = AsyncMock(return_value=MagicMock(
            status="completed",
            text="NVDA is experiencing strong AI infrastructure demand.",
            tool_calls=[],
            usage=MagicMock(total_tokens=150),
            duration=0.45,
        ))
        MockAgent.return_value = mock_agent_instance

        result = await node.execute(context)

        assert result.status == ExecutionStatus.COMPLETED
        assert "NVDA" in result.output
        MockAgent.assert_called_once()
        call_kwargs = MockAgent.call_args[1]
        assert call_kwargs["model"] == "openrouter/mistralai/ministral-3b-2512"
        assert call_kwargs["api_key"] == "sk-1234"
        assert call_kwargs["base_url"] == "http://localhost:9000/v1"
        assert call_kwargs["system_prompt"] == "You are a financial advisor assistant."
        assert "fetch_stock_price" in call_kwargs["tools"]

