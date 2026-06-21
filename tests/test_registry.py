import pytest
from litellm_adk.tools.registry import ToolRegistry

def test_tool_registry():
    registry = ToolRegistry()
    
    # Register a python function
    @registry.register
    def add_numbers(a: int, b: int) -> int:
        """Adds two numbers."""
        return a + b
        
    # Check OpenAPI JSON schema generation
    defs = registry.get_tool_definitions()
    assert len(defs) == 1
    
    func_schema = defs[0]["function"]
    assert func_schema["name"] == "add_numbers"
    assert func_schema["description"] == "Adds two numbers."
    assert "a" in func_schema["parameters"]["properties"]
    assert func_schema["parameters"]["properties"]["a"]["type"] == "integer"
    assert "b" in func_schema["parameters"]["properties"]
    assert func_schema["parameters"]["properties"]["b"]["type"] == "integer"
    
    # Execute the function
    res = registry.execute("add_numbers", a=5, b=3)
    assert res == 8

def test_tool_registry_unknown_tool():
    registry = ToolRegistry()
    with pytest.raises(ValueError):
        registry.execute("unknown")
