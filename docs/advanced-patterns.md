# Advanced Patterns

Once you've mastered the basic agent orchestration, the ADK provides native paradigms for handling complex, enterprise-level topologies.

## 1. Declarative Multi-Agent Topologies (YAML)

Hardcoding complex networks of agents in raw Python tightly couples your architecture to your codebase, making it difficult to refactor or visualize. The ADK allows you to map out your agent topologies using declarative YAML files.

```yaml
# customer_service.yaml
name: TriageAgent
model: groq/qwen/qwen3-32b
system_prompt: |
  You are the primary triage router. 
  Transfer users to the BillingAgent if they have payment issues, otherwise handle it yourself.

sub_agents:
  - name: BillingAgent
    model: groq/qwen/qwen3-32b
    system_prompt: "You are the billing specialist. You process refunds."
    tools: ["issue_refund"]
```

To deploy this topology:
```python
from litellm_adk import LiteLLMAgent

# Instantiates the master agent and recursively injects the sub-agents and tool capabilities
agent = LiteLLMAgent.from_yaml("customer_service.yaml")
```

The ADK natively handles the contextual transfer operations behind the scenes, ensuring the `BillingAgent` inherits the conversation context without requiring you to manually pass memory arrays.

## 2. Human-in-the-Loop (HITL) Authorization

Autonomous agents should not have uncontrolled access to destructive or financial functions. The ADK natively supports authorization intercepts.

By flagging a tool in the registry:
```python
@tool_registry.register(requires_approval=True)
def wipe_database(cluster_id: str):
    """Irreversible destructive operation."""
    pass
```

You can utilize the `astream` asynchronous generator to pause the execution event loop cleanly:
```python
async for event in agent.astream("Wipe cluster US-EAST"):
    if event["type"] == "requires_approval":
        # The generator pauses here! 
        print(f"Agent attempting to call: {event['pending_approvals']}")
        
        # You can prompt a human, wait for a web-hook, or await a UI button click...
        decision = {"status": "approved"}
        
        # Once approved, the loop naturally resumes and executes the tool.
```

## 3. Semantic Caching

In high-traffic environments, repeated identical (or semantically similar) queries can rapidly drain budgets and hit rate limits. The ADK integrates with vector-native caching backends (like Redis and Dragonfly).

```python
from litellm_adk.caching import CacheManager

# Enabling semantic caching requires an embedding model (default: OpenAI text-embedding-ada-002)
# Ensure OPENAI_API_KEY is in your environment.
CacheManager.enable_redis_cache(host="127.0.0.1", port=6379, semantic=True)
```

With semantic caching enabled, if User A asks "How do I reset my password?" and User B asks "What's the process to recover my login?", the ADK recognizes the vector similarity and serves the cached response to User B instantly without ever contacting the LLM API.
