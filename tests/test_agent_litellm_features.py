"""Unit tests verifying LiteLLM native feature integration for Agents.

Tests:
1. LiteLLM Router integration in Agent and LiteLLMModel
2. Cost accounting and token tracking (completion_cost, ModelUsage, AgentResult)
3. Budget enforcement (BudgetExceededError on max_budget)
4. Model Context Protocol (MCP) tool integration
5. AgentConfig.from_litellm_config and Agent.from_litellm_config
6. PII and secret redaction
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
from litellm_adk.agent import Agent, AgentConfig, ExecutionConfig
from litellm_adk.agent.result import AgentResult
from litellm_adk.exceptions import BudgetExceededError
from litellm_adk.models.base import ModelResponse, ModelUsage
from litellm_adk.models.config import ModelConfig
from litellm_adk.models.litellm import LiteLLMModel
from litellm_adk.security import PIIScrubber
from litellm_adk.tools.mcp import MCPTool, create_mcp_tool


class MockChoice:
    def __init__(self, content="Hello from mock", finish_reason="stop", tool_calls=None):
        self.message = MagicMock(content=content, role="assistant", tool_calls=tool_calls or [])
        self.finish_reason = finish_reason


class MockUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=20, total_tokens=30):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class MockRawResponse:
    def __init__(self, content="Hello from mock", finish_reason="stop", prompt_tokens=10, completion_tokens=20, total_tokens=30):
        self.choices = [MockChoice(content=content, finish_reason=finish_reason)]
        self.usage = MockUsage(prompt_tokens, completion_tokens, total_tokens)


@pytest.mark.asyncio
async def test_agent_cost_and_token_tracking():
    """Verifies that Agent and AgentResult accurately track token usage and USD cost."""
    raw_resp = MockRawResponse("Analysis complete.", prompt_tokens=50, completion_tokens=150, total_tokens=200)

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion, \
         patch("litellm.completion_cost", return_value=0.0042) as mock_cost:
        mock_acompletion.return_value = raw_resp

        agent = Agent(
            name="FinanceAgent",
            model="gpt-4o",
            api_key="sk-fake-test",
        )

        result = await agent.run("Analyze Q3 earnings")

        assert result.text == "Analysis complete."
        assert result.total_tokens == 200
        assert result.prompt_tokens == 50
        assert result.completion_tokens == 150
        assert result.cost_usd == 0.0042
        assert agent.cost_usd == 0.0042
        assert agent.total_tokens == 200

        # Run second query to verify cumulative cost tracking
        raw_resp2 = MockRawResponse("Q4 outlook is positive.", prompt_tokens=30, completion_tokens=70, total_tokens=100)
        mock_acompletion.return_value = raw_resp2
        mock_cost.return_value = 0.0018

        result2 = await agent.run("Analyze Q4 outlook")

        assert result2.cost_usd == 0.0018
        assert agent.cost_usd == pytest.approx(0.0060, rel=1e-3)
        assert agent.total_tokens == 300


@pytest.mark.asyncio
async def test_agent_budget_enforcement():
    """Verifies that AgentLoop raises BudgetExceededError when max_budget is exceeded."""
    raw_resp = MockRawResponse("Very expensive output", prompt_tokens=1000, completion_tokens=5000, total_tokens=6000)

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion, \
         patch("litellm.completion_cost", return_value=5.50):
        mock_acompletion.return_value = raw_resp

        agent = Agent(
            name="BudgetRestrictedAgent",
            model="gpt-4o",
            api_key="sk-fake-test",
            max_budget=2.00,  # $2.00 limit, but response costs $5.50
        )

        with pytest.raises(BudgetExceededError) as exc_info:
            await agent.run("Run expensive calculation")

        assert "exceeded max budget" in str(exc_info.value)
        assert exc_info.value.max_budget == 2.00
        assert exc_info.value.current_cost == 5.50


@pytest.mark.asyncio
async def test_agent_with_litellm_router():
    """Verifies that an Agent configured with a LiteLLM Router delegates generation to router.acompletion."""
    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=MockRawResponse("Routed response via failover"))

    agent = Agent(
        name="ResilientAgent",
        model="gpt-4o",
        router=mock_router,
    )

    result = await agent.run("Ping model")

    assert result.text == "Routed response via failover"
    assert mock_router.acompletion.called


def test_agent_config_from_litellm_config():
    """Verifies constructing AgentConfig and Agent from a LiteLLM proxy config dictionary."""
    litellm_proxy_dict = {
        "model_list": [
            {
                "model_name": "smart-model",
                "litellm_params": {
                    "model": "openai/gpt-4o",
                    "api_key": "os.environ/OPENAI_API_KEY",
                    "rpm": 500,
                },
            },
            {
                "model_name": "fast-model",
                "litellm_params": {
                    "model": "openai/gpt-4o-mini",
                    "api_key": "os.environ/OPENAI_API_KEY",
                },
            },
        ],
        "router_settings": {
            "routing_strategy": "usage-based-routing-v2",
            "fallbacks": [{"smart-model": ["fast-model"]}],
        },
        "litellm_settings": {
            "cache": True,
            "cache_params": {"type": "local"},
        },
    }

    cfg = AgentConfig.from_litellm_config(litellm_proxy_dict, agent_name="ConfigLoadedAgent")

    assert cfg.name == "ConfigLoadedAgent"
    assert cfg.model == "smart-model"
    assert cfg.model_list is not None
    assert len(cfg.model_list) == 2
    assert cfg.caching is True
    assert cfg.fallbacks == [{"smart-model": ["fast-model"]}]

    # Instantiate Agent directly from config
    agent = Agent.from_litellm_config(litellm_proxy_dict, agent_name="ConfigLoadedAgent")
    assert agent.name == "ConfigLoadedAgent"
    assert agent.model_name == "smart-model"


@pytest.mark.asyncio
async def test_agent_mcp_tool_integration():
    """Verifies that an Agent can mount and execute an MCPTool."""
    async def mock_mcp_handler(repo: str, issue_title: str) -> str:
        return f"Issue '{issue_title}' created in {repo} (ID: 101)"

    jira_mcp_tool = create_mcp_tool(
        name="create_issue",
        description="Creates a new issue in the project tracker.",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "issue_title": {"type": "string"},
            },
            "required": ["repo", "issue_title"],
        },
        call_handler=mock_mcp_handler,
    )

    agent = Agent(
        name="DevOpsAgent",
        model="gpt-4o",
        api_key="sk-fake",
        tools=[jira_mcp_tool],
    )

    # Verify tool schema is in OpenAPI standard format
    tools_def = agent.tools
    assert len(tools_def) == 1
    assert tools_def[0]["function"]["name"] == "create_issue"
    assert "repo" in tools_def[0]["function"]["parameters"]["properties"]

    # Execute tool directly through tool executor
    exec_result = await agent.tool_executor.execute("create_issue", {"repo": "litellm-adk", "issue_title": "Add MCP Tools"})
    assert "Issue 'Add MCP Tools' created in litellm-adk" in exec_result


def test_pii_and_secret_redaction():
    """Verifies that PIIScrubber masks credit cards, emails, SSNs, and API keys."""
    sensitive_prompt = (
        "Customer email is alice@company.com with SSN 123-45-6789. "
        "Paid with 4111-2222-3333-4444. "
        "Admin API key is sk-abcdef12345678901234567890 and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    )

    scrubbed = PIIScrubber.scrub_text(sensitive_prompt)

    assert "alice@company.com" not in scrubbed
    assert "[EMAIL_REDACTED]" in scrubbed
    assert "123-45-6789" not in scrubbed
    assert "[SSN_REDACTED]" in scrubbed
    assert "4111-2222-3333-4444" not in scrubbed
    assert "[CREDIT_CARD_REDACTED]" in scrubbed
    assert "sk-abcdef12345678901234567890" not in scrubbed
    assert "[API_KEY_REDACTED]" in scrubbed
    assert "[BEARER_TOKEN_REDACTED]" in scrubbed
