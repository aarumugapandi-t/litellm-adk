import pytest
from unittest.mock import patch, MagicMock
from litellm_adk.agent import LiteLLMAgent

@patch("litellm_adk.agent.litellm.completion")
def test_agent_initialization_and_invoke(mock_completion):
    # Mock Litellm Response
    mock_msg = MagicMock()
    mock_msg.content = "Hello from the mocked agent"
    mock_msg.role = "assistant"
    mock_msg.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    mock_completion.return_value = mock_response
    
    # Initialize with custom routing and fallback
    agent = LiteLLMAgent(
        name="TestAgent", 
        model="gpt-4o", 
        base_url="https://api.openai.com", 
        fallbacks=["gpt-3.5-turbo"]
    )
    
    # Check OpenAI proxy prefixing feature
    assert agent.model == "openai/gpt-4o"
    assert agent.fallbacks[0]["model"] == "openai/gpt-3.5-turbo"
    
    # Test invoke
    res = agent.invoke("Hi")
    assert res.content == "Hello from the mocked agent"
    assert mock_completion.called
