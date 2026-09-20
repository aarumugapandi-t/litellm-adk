"""Tests for Dynamic Tool AST validation, sandbox execution, Master Agent synthesis, and API routes."""

import pytest
from fastapi.testclient import TestClient

from litellm_adk.tools.dynamic_tool import (
    ASTSecurityValidator,
    SafeCodeSandbox,
    DynamicToolSpec,
    create_dynamic_tool_instance,
)
from litellm_adk.exceptions import ToolPermissionError, ToolError
from litellm_adk.agent.manager import MasterAgentManager
from litellm_adk.server.app import app


@pytest.mark.asyncio
async def test_dynamic_tool_sandbox_execution():
    """Verifies that safe dynamic Python code compiles and executes with arguments."""
    code = """
def run(base_price: float, discount_pct: float = 10.0, customer_tier: str = "standard"):
    discount = base_price * (discount_pct / 100.0)
    final_price = base_price - discount
    if customer_tier == "vip":
        final_price -= 5.0
    return {
        "original": base_price,
        "final": max(0.0, final_price),
        "discount_applied": discount
    }
"""
    # 1. AST Validation
    ASTSecurityValidator.validate(code)

    # 2. Sandbox Execution
    result = await SafeCodeSandbox.execute(
        code=code,
        arguments={"base_price": 100.0, "discount_pct": 20.0, "customer_tier": "vip"},
    )

    assert result.success is True
    assert result.output["original"] == 100.0
    assert result.output["final"] == 75.0
    assert result.output["discount_applied"] == 20.0


@pytest.mark.asyncio
async def test_dynamic_tool_security_ast_blocking():
    """Verifies that malicious or restricted imports/calls are blocked."""
    unsafe_codes = [
        "import os\ndef run():\n    os.system('rm -rf /')",
        "import subprocess\ndef run():\n    subprocess.Popen(['ls'])",
        "def run():\n    eval('1 + 1')",
        "def run():\n    exec('x = 2')",
        "from shutil import rmtree\ndef run():\n    rmtree('/tmp')",
        "def run():\n    return ().__class__.__bases__[0]",
    ]

    for malicious_code in unsafe_codes:
        with pytest.raises(ToolPermissionError):
            ASTSecurityValidator.validate(malicious_code)

        # Ensure sandbox also rejects it
        res = await SafeCodeSandbox.execute(code=malicious_code)
        assert res.success is False
        assert "Security check failed" in res.error


@pytest.mark.asyncio
async def test_dynamic_tool_adk_wrapper():
    """Verifies that a DynamicToolSpec wraps into an ADK Tool callable."""
    spec = DynamicToolSpec(
        name="currency_converter",
        description="Converts USD to EUR",
        parameters={
            "amount": {"type": "number", "description": "Amount in USD"},
            "rate": {"type": "number", "description": "Exchange rate", "default": 0.92},
        },
        code="""
def run(amount: float, rate: float = 0.92):
    return round(amount * rate, 2)
""",
        approval_required=False,
    )

    adk_tool = create_dynamic_tool_instance(spec)
    assert adk_tool.name == "currency_converter"
    assert adk_tool.description == "Converts USD to EUR"

    res = await adk_tool.func(amount=50.0, rate=0.9)
    assert res == 45.0


@pytest.mark.asyncio
async def test_master_agent_synthesis_heuristic():
    """Verifies that MasterAgentManager synthesizes AgentSpec, tools, and canvas graph."""
    manager = MasterAgentManager()
    prompt = "Create a customer support agent to query postgres orders and send email notification when urgent."

    res = await manager.synthesize_agent(prompt)

    assert "agent_spec" in res
    assert "Customer" in res["agent_spec"]["name"] or "Agent" in res["agent_spec"]["name"]
    assert "graph" in res
    assert len(res["graph"]["nodes"]) >= 3  # trigger, agent, output + tool(s)
    assert len(res["graph"]["edges"]) >= 2

    # Verify tool wires
    tool_edges = [e for e in res["graph"]["edges"] if e.get("targetHandle") == "tools"]
    assert len(tool_edges) >= 1

    # Verify dynamic tools
    assert len(res["dynamic_tools"]) >= 1
    assert any("email" in dt["name"] or "database" in dt["name"] or "order" in dt["name"] for dt in res["dynamic_tools"])


def test_manager_api_routes():
    """Verifies manager status, configure, synthesize, and tool testing endpoints."""
    client = TestClient(app)

    # 1. Status
    res = client.get("/api/v1/manager/status")
    assert res.status_code == 200
    data = res.json()
    assert "ready" in data
    assert "model" in data

    # 2. Templates
    res = client.get("/api/v1/manager/templates")
    assert res.status_code == 200
    templates = res.json()
    assert len(templates) >= 3
    assert any("Customer Support" in t["title"] for t in templates)

    # 3. Dynamic Tool Sandbox test endpoint
    test_req = {
        "code": "def run(x: int, y: int):\n    return {'sum': x + y}",
        "arguments": {"x": 14, "y": 28},
        "timeout_seconds": 5.0,
    }
    res = client.post("/api/v1/manager/tools/test", json=test_req)
    assert res.status_code == 200
    tool_res = res.json()
    assert tool_res["success"] is True
    assert tool_res["output"]["sum"] == 42

    # 4. Synthesize endpoint
    synth_req = {
        "prompt": "Create an analytics agent that calculates averages and plots metrics."
    }
    res = client.post("/api/v1/manager/synthesize", json=synth_req)
    assert res.status_code == 200
    synth_data = res.json()
    assert "agent_spec" in synth_data
    assert "graph" in synth_data
    assert len(synth_data["graph"]["nodes"]) >= 3


@pytest.mark.asyncio
async def test_greeting_agent_and_tool_synthesis():
    """Verifies that 'Create greater agent with greeting tool' generates GreeterAgent with generate_greeting tool."""
    manager = MasterAgentManager()
    prompt = "Create greater agent with greeting tool"

    res = await manager.synthesize_agent(prompt)

    # 1. Verify Clean Naming (Industry Standard, no 'Create', no duplicate 'AgentAgent')
    agent_spec = res["agent_spec"]
    assert agent_spec["name"] == "GreeterAgent"
    assert "AgentAgent" not in agent_spec["name"]
    assert "Create" not in agent_spec["name"]

    # 2. Verify Exact Greeting Tool Synthesis (NOT data_processor fallback)
    dynamic_tools = res["dynamic_tools"]
    assert len(dynamic_tools) >= 1
    tool_names = [t["name"] for t in dynamic_tools]
    assert "generate_greeting" in tool_names
    assert "data_processor" not in tool_names

    # 3. Verify Realistic Trigger Payload
    trigger_node = next(n for n in res["graph"]["nodes"] if n["type"] == "manual_trigger")
    payload = trigger_node["config"]["default_payload"]
    assert "user_name" in payload
    assert "tone" in payload

    # 4. Verify Tool Execution in Sandbox
    greeting_tool = next(t for t in dynamic_tools if t["name"] == "generate_greeting")
    run_res = await SafeCodeSandbox.execute(
        code=greeting_tool["code"],
        arguments={"user_name": "Bob", "tone": "friendly", "time_of_day": "morning"},
    )
    assert run_res.success is True
    assert "Bob" in run_res.output["greeting_message"]
    assert run_res.output["status"] == "success"


@pytest.mark.asyncio
async def test_end_to_end_synthesized_workflow_execution():
    """Verifies that the synthesized greeting workflow executes end-to-end to status COMPLETED."""
    from litellm_adk.workflow.engine import WorkflowEngine
    from litellm_adk.workflow.schema import WorkflowDefinition, WorkflowNode, WorkflowEdge
    from litellm_adk.workflow.state import ExecutionStatus

    manager = MasterAgentManager()
    res = await manager.synthesize_agent("Create greater agent with greeting tool")

    graph_data = res["graph"]
    wf = WorkflowDefinition(
        id="wf_greeting_test",
        name="Greeting Test Workflow",
        nodes=[WorkflowNode(**n) for n in graph_data["nodes"]],
        edges=[WorkflowEdge(**e) for e in graph_data["edges"]],
    )

    engine = WorkflowEngine()
    trigger_payload = next(n for n in graph_data["nodes"] if n["type"] == "manual_trigger")["config"]["default_payload"]

    state = await engine.execute(wf, trigger_data=trigger_payload)

    assert state.status == ExecutionStatus.COMPLETED
    assert len(state.errors) == 0

    # Verify agent node completed
    agent_nodes = [n for n in graph_data["nodes"] if n["type"] == "agent"]
    assert len(agent_nodes) == 1
    agent_id = agent_nodes[0]["id"]
    assert agent_id in state.completed_nodes
    assert state.node_records[agent_id].status == ExecutionStatus.COMPLETED

    # Verify tool execution occurred
    rec = state.node_records[agent_id]
    assert rec.metadata.get("tool_calls") is not None
    assert len(rec.metadata["tool_calls"]) >= 1
    assert "generate_greeting" in rec.metadata["tool_calls"][0]["name"]

