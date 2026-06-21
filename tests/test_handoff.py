import pytest
from litellm_adk.handoff import HandoffAgent

def test_handoff_agent_initialization():
    agent_exception = HandoffAgent(target_agent_name="WorkerAgent", instructions="Do the heavy lifting")
    
    assert agent_exception.target_agent_name == "WorkerAgent"
    assert agent_exception.kwargs["instructions"] == "Do the heavy lifting"
    assert isinstance(agent_exception, Exception)
