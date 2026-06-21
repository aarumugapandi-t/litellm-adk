import pytest
from litellm_adk.context import ContextManager

def test_atomic_truncation_drops_tool_pair():
    """
    Ensures that when truncation occurs, it never severs an assistant tool_call
    from its corresponding tool result. Both are dropped as an atomic block.
    """
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user 1"},
        {"role": "assistant", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "test"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "tool 1 result"},
        {"role": "user", "content": "user 2"}
    ]
    
    # Force a very tight token budget so it has to drop the middle messages
    # Using 10 tokens will force it to keep only the required System prompt and the very last block
    truncated = ContextManager.truncate_history(messages, "gpt-4", max_tokens=15, reserve_tokens=0)
    
    roles = [m["role"] for m in truncated]
    
    # It should cleanly drop the middle assistant + tool pair
    assert "tool" not in roles
    assert "assistant" not in roles
    assert roles == ["system", "user"]
    assert truncated[1]["content"] == "user 2"

def test_atomic_truncation_keeps_tool_pair():
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user 1"},
        {"role": "assistant", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "test"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "tool 1 result"},
        {"role": "user", "content": "user 2"}
    ]
    
    # High budget should keep everything
    truncated = ContextManager.truncate_history(messages, "gpt-4", max_tokens=1000, reserve_tokens=0)
    
    roles = [m["role"] for m in truncated]
    assert roles == ["system", "user", "assistant", "tool", "user"]
