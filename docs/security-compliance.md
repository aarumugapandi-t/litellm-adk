# Security, Compliance, and Observability

Deploying LLMs into production requires strict adherence to data privacy standards and comprehensive visibility into system performance.

## 1. PII Sanitization (PIIScrubber)

The ADK ships with a native `PIIScrubber` interceptor. When enabled, this layer scans all outgoing `messages` arrays, utilizing localized Regex and NLP patterns to mask Personally Identifiable Information (PII) before the payload is ever serialized and transmitted to external APIs.

```python
from litellm_adk import LiteLLMAgent

agent = LiteLLMAgent(
    model="openai/gpt-4o",
    scrub_pii=True # Activates the sanitization interceptor
)

# Outgoing network payload: "User contact is [EMAIL_REDACTED]"
await agent.ainvoke("User contact is david@enterprise.com")
```

Currently, the `PIIScrubber` natively intercepts:
- Emails
- Social Security Numbers (SSN)
- Credit Card Numbers
- Standardized Phone Numbers

## 2. API Telemetry & Tracing

Visibility into token economics and latency spans is critical. Instead of requiring massive refactors, the ADK exposes a zero-configuration hook that binds directly to the OpenTelemetry (OTel) standard.

```python
from litellm_adk import setup_litellm_telemetry

# Execute this once during application startup
setup_litellm_telemetry()
```

When integrated with an observability platform like **Langfuse**, **DataDog**, or **New Relic**, this hook automatically maps:
- End-to-end execution latency
- Input/Output token counts
- Prompt and Completion strings
- Execution errors and failover cascade logs

## 3. Automatic Failover Resiliency

Model providers frequently experience degraded performance or strict rate limits. The ADK ensures high availability through automated, graceful degradation.

You can configure fallbacks dynamically:
```python
agent = LiteLLMAgent(
    model="anthropic/claude-3-opus",
    fallbacks=["groq/llama3-70b", "openai/gpt-3.5-turbo"]
)
```

If the primary model returns a `429 Rate Limit` or a `503 Service Unavailable`, the ADK intercepts the exception natively within the `_get_completion` router and automatically retries the identical payload against the fallbacks sequentially until a successful response is generated.
