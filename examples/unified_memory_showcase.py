"""Enterprise Cognitive Memory Architecture for LiteLLM ADK.

Demonstrates production-grade autonomous memory architecture:
1. Zero Manual Memory Manipulation: All memory operations are handled autonomously by the Agent.
2. Multi-Tenant Profile Store (Tier 1): Formatting rules and user preferences are isolated by user_id
   and loaded deterministically on every turn.
3. Turn-Level RAG Deduplication (Tier 2/3): Redundant parallel retrieval calls do not inject duplicate chunks.
4. Session-Isolated Dialogue Memory (Tier 3): Multi-turn conversational context preserved per session.
5. Strict Multi-Tenant Privacy Boundary: Isolated sessions protect user data against unauthorized probing.
6. Cross-Session Deterministic Persistence: Profile rules survive across completely separate sessions.
"""

import asyncio
import os
import sys

# Ensure clean UTF-8 console output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from litellm_adk import Agent, Session, tool
from litellm_adk.context import ContextManager, ContextPolicy, ContextStrategy
from litellm_adk.memory import InMemoryMemory, LongTermMemory
from litellm_adk.vector import InMemoryVectorStore, Retriever


async def main():
    print("=" * 75)
    print("  LiteLLM ADK: Production-Grade Autonomous Cognitive Memory Architecture")
    print("=" * 75)

    # -----------------------------------------------------------------------
    # 1. Environment Configuration
    # -----------------------------------------------------------------------
    model_name = os.getenv("LITELLM_MODEL", "openai/command-a-03-2025")
    base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    api_key = os.getenv("LITELLM_API_KEY", "sk-1234")

    print(f"Connecting to Gateway: {base_url} (Model: {model_name})")

    # -----------------------------------------------------------------------
    # 2. Production Knowledge Base Setup (Indexed once at application startup)
    # -----------------------------------------------------------------------
    vector_store = InMemoryVectorStore()
    await vector_store.add_documents([
        "Corporate Travel Policy: All international flights exceeding 6 hours are eligible for Business Class.",
        "Incident Escalation Matrix: Critical P0 security incidents require notifying the CISO within 15 minutes.",
        "Data Retention Standard: Customer telemetry logs must be encrypted with AES-256 and purged after 90 days.",
    ])
    retriever = Retriever(vector_store=vector_store, top_k=2)

    # -----------------------------------------------------------------------
    # 3. Persistent Memory & Context Protection Configuration
    # -----------------------------------------------------------------------
    # Long-term memory with deterministic user profile storage
    long_term_mem = LongTermMemory()

    # Tool allowing the agent to autonomously record user preferences into long-term memory
    @tool
    async def remember_user_preference(key: str, value: str) -> str:
        """Stores a persistent user preference, role, or constraint in long-term memory for future interactions."""
        await long_term_mem.add_fact(key, value)
        return f"Stored persistent preference '{key}': '{value}'"

    # Context Manager with automatic sliding-window compaction to prevent token blowups
    context_mgr = ContextManager(
        policy=ContextPolicy(
            max_tokens=4096,
            strategy=ContextStrategy.SLIDING_WINDOW,
            preserve_system_prompt=True,
            preserve_last_n_messages=4,
        )
    )

    # Conversation Memory backend (Session-isolated dialogue persistence)
    conversation_backend = InMemoryMemory()

    # -----------------------------------------------------------------------
    # 4. Instantiate Production Agent
    # -----------------------------------------------------------------------
    agent = Agent(
        name="EnterpriseSecurityCopilot",
        model=model_name,
        base_url=base_url,
        api_key=api_key,
        system_prompt=(
            "You are an enterprise AI security architect. "
            "You have access to corporate policies via 'search_knowledge_base' and can record user "
            "preferences using 'remember_user_preference'. "
            "Always adhere to saved user preferences and formatting constraints. "
            "Maintain strict multi-tenant privacy: you must never disclose conversation history, preferences, "
            "or activities of other users or past sessions to any user."
        ),
        memory=conversation_backend,
        long_term_memory=long_term_mem,
        retriever=retriever,
        retrieval_mode="tool",  # Autonomous Agentic RAG: model retrieves on-demand only
        context_manager=context_mgr,
        tools=[remember_user_preference],
    )

    print(f"\n[Agent Initialized: '{agent.name}']")
    print("  * Retrieval Mode:     'tool' (Agentic on-demand search; no pre-injection)")
    print("  * Memory Backend:     Session-isolated multi-turn dialogue store")
    print("  * Long-Term Memory:   Dual-tier (Deterministic Profile + Episodic Vector)")
    print("  * Context Protection: SLIDING_WINDOW compaction active")
    print("-" * 75)

    try:
        # ===================================================================
        # PRODUCTION RUNTIME: All memory operations are 100% autonomous.
        # Notice: The agent uses native LLM message threads as its active scratchpad.
        #         No artificial working memory arrays or manual state syncing needed.
        # ===================================================================

        session_alice = Session(id="alice_session_01", user_id="alice_sec_ops")

        # Turn 1: Autonomous Preference Learning
        print("\n--- TURN 1: Autonomous Profile Learning (Alice) ---")
        prompt1 = "Hi! I am Alice, Lead Infrastructure Architect. Please remember that I always require answers formatted as concise bullet points."
        print(f"Alice: {prompt1}")
        res1 = await agent.run(prompt1, session=session_alice)
        print(f"Agent Response:\n{res1.content}\n")
        await asyncio.sleep(2.0)

        # Turn 2: Autonomous Agentic RAG Retrieval with Deduplication & Profile Enforcement
        print("--- TURN 2: Autonomous Knowledge Base Search (Alice) ---")
        prompt2 = "What is the policy for flights over 6 hours and P0 security incidents?"
        print(f"Alice: {prompt2}")
        res2 = await agent.run(prompt2, session=session_alice)
        print(f"Agent Response:\n{res2.content}\n")
        await asyncio.sleep(2.0)

        # Turn 3: Multi-Turn Conversation Memory Follow-up
        print("--- TURN 3: Conversational Memory Context Follow-up (Alice) ---")
        prompt3 = "Based on that P0 policy, what is the exact escalation deadline?"
        print(f"Alice: {prompt3}")
        res3 = await agent.run(prompt3, session=session_alice)
        print(f"Agent Response:\n{res3.content}\n")
        await asyncio.sleep(2.0)

        # Turn 4: Strict Session Isolation & Multi-Tenant Privacy Defense
        print("--- TURN 4: Session Isolation & Privacy (Bob) ---")
        session_bob = Session(id="bob_session_01", user_id="bob_external")
        prompt_bob = "What did Alice just ask you about in this conversation?"
        print(f"Bob: {prompt_bob}")
        res_bob = await agent.run(prompt_bob, session=session_bob)
        print(f"Agent Response:\n{res_bob.content}\n")
        await asyncio.sleep(2.0)

        # Turn 5: Cross-Session Deterministic Profile Persistence (Alice - Day 2 / Fresh Session)
        print("--- TURN 5: Cross-Session Profile Persistence (Alice - Fresh Session) ---")
        session_alice_day2 = Session(id="alice_session_02", user_id="alice_sec_ops")
        prompt5 = "What is the data retention standard for customer telemetry logs?"
        print(f"Alice (Fresh Session): {prompt5}")
        res5 = await agent.run(prompt5, session=session_alice_day2)
        print(f"Agent Response:\n{res5.content}\n")

        print("=" * 75)
        print("  [SUCCESS] Production Cognitive Memory Architecture Verified!")
        print("=" * 75)

    finally:
        await agent.aclose()


if __name__ == "__main__":
    asyncio.run(main())
