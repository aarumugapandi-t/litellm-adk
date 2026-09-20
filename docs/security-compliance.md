# Security, Compliance, and Observability

Deploying LLMs into enterprise production requires strict adherence to data privacy standards, sandbox isolation, and comprehensive visibility.

For the complete technical guide, see [**11. Middleware, Security & Caching**](./11-middleware-security-caching.md).

---

## 1. PII Sanitization (`PIIScrubber`)

The ADK includes a native `PIIScrubber` interceptor. When enabled via `scrub_pii=True` on `Agent`, this layer scans all outgoing message strings, utilizing compiled regex patterns to mask sensitive data before the payload is transmitted to external providers:

```python
from litellm_adk import Agent

agent = Agent(
    model="gpt-4o",
    scrub_pii=True,  # Activates the PII sanitization interceptor
)

# Outgoing network payload: "User contact is [EMAIL_REDACTED]"
await agent.ainvoke("User contact is david@enterprise.com")
```

The `PIIScrubber` natively redacts:
- Email Addresses (`[EMAIL_REDACTED]`)
- Social Security Numbers (`[SSN_REDACTED]`)
- Credit Card Numbers (`[CREDIT_CARD_REDACTED]`)
- API Keys (`[API_KEY_REDACTED]`)
- Bearer Tokens (`[BEARER_TOKEN_REDACTED]`)

---

## 2. Dynamic Tool AST Sandboxing (`ASTSecurityValidator`)

All dynamic Python code synthesized at runtime is subjected to static Abstract Syntax Tree (AST) analysis before execution. Any attempts to import restricted operating system modules (`os`, `sys`, `subprocess`, `socket`) or invoke dangerous functions (`eval`, `exec`, `__import__`) raise `ToolPermissionError` and halt execution.

See [**Tools & Dynamic Tooling**](./04-tools-and-dynamic-tooling.md) for sandbox implementation details.

---

## 3. API Telemetry & Tracing

The ADK exposes OpenTelemetry (OTel) bindings for tracking token economics, latencies, and execution spans:

```python
from litellm_adk import setup_litellm_telemetry

# Initialize during application startup
setup_litellm_telemetry()
```

When integrated with observability platforms (e.g. Langfuse, Datadog, Prometheus), the ADK tracks:
- End-to-end execution latency per node and agent turn.
- Input and output token usage.
- Tool call duration and argument logs.
- Failover cascade history.

---

## 4. Model Failover & Resiliency

Configure fallback models to prevent outages caused by provider rate limits:

```python
agent = Agent(
    model="claude-3-5-sonnet",
    fallbacks=["gpt-4o", "groq/llama3-70b"],
)
```

If the primary provider returns `429 Rate Limit` or `503 Service Unavailable`, the router retries against the specified fallback models sequentially.
