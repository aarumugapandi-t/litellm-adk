import pytest
import asyncio
from litellm_adk.memory import InMemoryMemory
from litellm_adk.memory.vector_store import VectorStore

@pytest.mark.asyncio
async def test_in_memory_memory():
    mem = InMemoryMemory()
    await mem.add_message("session_1", {"role": "user", "content": "hello"})
    
    msgs = await mem.get_messages("session_1")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "hello"
    
    await mem.add_messages("session_1", [{"role": "assistant", "content": "hi"}])
    msgs2 = await mem.get_messages("session_1")
    assert len(msgs2) == 2
    assert msgs2[1]["role"] == "assistant"
