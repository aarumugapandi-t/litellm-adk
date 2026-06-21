import pytest
from unittest.mock import patch, Mock
from litellm_adk.agent import LiteLLMAgent
from litellm_adk.security import PIIScrubber

@pytest.mark.asyncio
async def test_token_count_stripped_before_completion():
    """
    Validates that internal ADK metadata (like token_count) is successfully 
    stripped out of the payload before being transmitted to strict LLM providers.
    """
    with patch("litellm_adk.agent.litellm.acompletion") as mock_acompletion:
        mock_acompletion.return_value.choices = [Mock(message={"role": "assistant", "content": "Hello!"})]
        mock_acompletion.return_value.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
        
        agent = LiteLLMAgent(
            model="test-model",
            system_prompt="You are a test assistant.",
        )
        
        # Inject an internal token_count simulating ADK context manager behavior
        messages = [
            {"role": "system", "content": "You are a test assistant.", "token_count": 5},
            {"role": "user", "content": "Hi", "token_count": 2}
        ]
        
        await agent._aget_completion(messages=messages)
        
        # Assert acompletion was called
        mock_acompletion.assert_called_once()
        
        # Get the actual messages that were passed to litellm
        called_messages = mock_acompletion.call_args.kwargs["messages"]
        
        for msg in called_messages:
            # Crucial validation: token_count must not exist in the outgoing payload!
            assert "token_count" not in msg

@pytest.mark.asyncio
async def test_pii_scrubber_integration():
    """
    Validates that PIIScrubber correctly intercepts and masks sensitive data 
    inside the agent's completion pipeline when scrub_pii=True.
    """
    with patch("litellm_adk.agent.litellm.acompletion") as mock_acompletion:
        mock_acompletion.return_value.choices = [Mock(message={"role": "assistant", "content": "Redacted!"})]
        mock_acompletion.return_value.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
        
        agent = LiteLLMAgent(
            model="test-model",
            scrub_pii=True
        )
        
        messages = [
            {"role": "user", "content": "My SSN is 123-45-6789 and my email is test@example.com."}
        ]
        
        await agent._aget_completion(messages=messages)
        
        # Get the actual messages that were passed to litellm
        called_messages = mock_acompletion.call_args.kwargs["messages"]
        
        # Validate the PII was scrubbed
        content = called_messages[0]["content"]
        assert "123-45-6789" not in content
        assert "[SSN_REDACTED]" in content
        assert "test@example.com" not in content
        assert "[EMAIL_REDACTED]" in content
