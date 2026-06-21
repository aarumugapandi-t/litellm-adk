import pytest
from litellm_adk.policy import PolicyEngine

def test_policy_engine():
    engine = PolicyEngine()
    
    # Add rules
    engine.add_rule("delete_file", lambda args: True) # Always requires approval
    engine.add_rule("read_file", lambda args: "secret" in args.get("path", ""))
    
    # Test execution
    assert engine.should_require_approval("delete_file", {}) is True
    assert engine.should_require_approval("read_file", {"path": "public.txt"}) is False
    assert engine.should_require_approval("read_file", {"path": "secret.txt"}) is True
    
    # Unknown tools do not require approval by default
    assert engine.should_require_approval("unknown_tool", {}) is False
