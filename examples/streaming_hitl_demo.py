import os
import uuid
from dotenv import load_dotenv
from litellm_adk.agent import LiteLLMAgent
from litellm_adk.tools.registry import tool
from litellm_adk.models import ApprovalStatus

load_dotenv()

# Use the same settings as other demos
PROXY_URL = "http://localhost:9000/v1"
API_KEY = "sk-1234"

@tool
def process_refund(user_id: str, amount: float) -> str:
    """Processes a refund for a specific user and amount."""
    return f"Successfully refunded ${amount} to user {user_id}."

# Define a sensitive agent that requires approval for refunds
agent = LiteLLMAgent(
    name="refund_agent",
    model="openrouter/anthropic/claude-3-haiku",
    api_key=API_KEY,
    base_url=PROXY_URL,
    tools=[process_refund],
    system_prompt="You are a refund processing agent. For any refund request, use the process_refund tool."
)

# Force approval for the refund tool
# In production, this would be set based on tool metadata or logic
orig_should = agent._should_require_approval
agent._should_require_approval = lambda name, args: name == "process_refund" or orig_should(name, args)

def run_hitl_stream_demo():
    print("--- Streaming HITL Demo (Sync) ---")
    session_id = str(uuid.uuid4())
    user_input = "Refund $50 to user 123"
    print(f"\nUser: {user_input}")
    
    print("Agent: ", end="", flush=True)
    
    # First Pass: Should stop and ask for approval
    pending_request_id = None
    for chunk in agent.stream(user_input, session_id=session_id, stream_events=True):
        if isinstance(chunk, dict):
            if chunk.get("type") == "content":
                print(chunk.get("delta"), end="", flush=True)
            elif chunk.get("type") == "requires_approval":
                print("\n[⚠️ HITL: Approval Required]")
                approval = chunk["pending_approvals"][0]
                pending_request_id = approval["id"]
                print(f"Tool: {approval['tool_name']}")
                print(f"Args: {approval['original_args']}")
    
    if pending_request_id:
        # Simulate User Approval
        print(f"\n[USER DECISION: APPROVING {pending_request_id}]")
        agent.approval_manager.submit_decision(
            id=pending_request_id,
            status=ApprovalStatus.APPROVED,
            reason="User confirmed refund."
        )
        
        # Second Pass: Resume from history
        print("\nAgent (Resuming): ", end="", flush=True)
        # Call with empty prompt to resume from pending tool calls
        for chunk in agent.stream("", session_id=session_id, stream_events=True):
            if isinstance(chunk, dict):
                if chunk.get("type") == "content":
                    print(chunk.get("delta"), end="", flush=True)
                elif chunk.get("type") == "tool_start":
                    print(f"\n[🔄 Thinking: Executing {chunk['name']}...]", end="", flush=True)
                elif chunk.get("type") == "tool_end":
                    print(f"\n[✅ Done: {chunk['name']}]", end="", flush=True)
                    print(f"Result: {chunk['result']}")

    print("\n\nDemo complete.")

if __name__ == "__main__":
    run_hitl_stream_demo()
