import pytest
import os
import yaml
from litellm_adk.agent import LiteLLMAgent
from litellm_adk.config.agent_config import AgentConfig
from litellm_adk.tools.registry import tool_registry

# Create a dummy global tool
@tool_registry.register()
def check_weather(location: str) -> str:
    """Check the weather in a location."""
    return f"Weather in {location} is clear."

def test_declarative_config_dict():
    config_dict = {
        "name": "YAML_Agent",
        "description": "An agent built from a dictionary.",
        "model": "groq/qwen/qwen3-32b",
        "system_prompt": "You are a configured agent.",
        "tools": ["check_weather"]
    }
    
    agent = LiteLLMAgent(config=AgentConfig(**config_dict))
    
    assert agent.name == "YAML_Agent"
    assert agent.model == "groq/qwen/qwen3-32b"
    assert agent.system_prompt == "You are a configured agent."
    
    # Check that the tool was correctly resolved from string
    assert len(agent.tools) == 1
    assert agent.tools[0]["function"]["name"] == "check_weather"

def test_from_yaml_string():
    yaml_str = """
name: SubAgent
description: A sub-agent
model: openai/gpt-4o-mini
system_prompt: You are a sub agent.
"""
    agent = LiteLLMAgent.from_yaml(yaml_str)
    assert agent.name == "SubAgent"
    assert agent.model == "openai/gpt-4o-mini"
    assert agent.system_prompt == "You are a sub agent."

def test_from_yaml_file(tmp_path):
    yaml_str = """
name: ParentAgent
description: Parent agent
model: openai/gpt-4o
sub_agents:
  - name: child1
    model: openai/gpt-4o-mini
    system_prompt: Child 1
"""
    yaml_file = tmp_path / "agent.yaml"
    yaml_file.write_text(yaml_str)
    
    agent = LiteLLMAgent.from_yaml(str(yaml_file))
    assert agent.name == "ParentAgent"
    assert agent.model == "openai/gpt-4o"
    
    # Verify sub_agent was created
    assert "child1" in agent.sub_agents
    child = agent.sub_agents["child1"]
    assert child.name == "child1"
    assert child.model == "openai/gpt-4o-mini"
    assert child.system_prompt == "Child 1"
