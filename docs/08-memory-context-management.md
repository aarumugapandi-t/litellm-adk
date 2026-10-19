# Memory & Context Management

The LiteLLM ADK provides a multi-layer memory architecture (`src/litellm_adk/memory/`) and context compaction engine (`src/litellm_adk/context/`) to ensure agents retain conversational context across turns without exceeding LLM context windows or incurring runaway token costs.

---

## 1. Cognitive Memory Architecture

```mermaid
graph TD
    UserTurn["User Turn Input"] --> Agent["Agent Orchestrator"]
    
    subgraph "Cognitive Memory Hierarchy"
        Agent <--> Scratchpad["1. Native Message Scratchpad\n(Tool calls & observations in active turn thread)"]
        Agent <--> ConvoMem["2. Conversation Memory\n(Session-isolated multi-turn dialog history)"]
        Agent <--> LongTermMem["3. Long-Term Memory\n(Dual-Tier: Deterministic Profile + Episodic Vector)"]
        Agent <--> VectorMem["4. Vector Store (RAG)\n(Semantic similarity lookup across domain documents)"]
    end
    
    subgraph "Storage Adapters"
        ConvoMem --> SQLite["SQLAlchemy (SQLite, Postgres, MySQL)"]
        ConvoMem --> Mongo["MongoDB Backend"]
        ConvoMem --> InMem["In-Memory Store"]
        LongTermMem --> SQLite
        LongTermMem --> Mongo
        LongTermMem --> InMem
    end
```

---

## 2. Pluggable Memory Adapters

All storage engines implement `BaseMemory`:

### 1. In-Memory Memory (`InMemoryMemory`)
Fast, non-persistent storage suitable for unit tests and stateless microservices:
```python
from litellm_adk.memory import InMemoryMemory

memory = InMemoryMemory()
```

### 2. Relational Database Memory (`SQLAlchemyMemory`)
Production-grade persistence supporting SQLite, PostgreSQL, MySQL:
```python
from litellm_adk.memory import SQLAlchemyMemory

memory = SQLAlchemyMemory(
    db_url="postgresql+asyncpg://user:password@localhost:5432/agent_memory",
    session_id="session_user_4821",
)
```

### 3. Document Database Memory (`MongoDBMemory`)
Horizontally scalable JSON document store:
```python
from litellm_adk.memory import MongoDBMemory

memory = MongoDBMemory(
    connection_string="mongodb://localhost:27017",
    database="adk_memory",
    collection="sessions",
)
```

---

## 3. Dual-Tier Long-Term Cognitive Memory (`LongTermMemory`)

`LongTermMemory` persists user facts, preferences, and historical interactions across independent sessions. It decouples memory into two specialized tiers:

### Tier 1: Deterministic User Profile Store
Multi-tenant key-value attributes (user persona, formatting requirements, constraints) strictly partitioned by `user_id`. When an agent turn begins with `user_id`, these profile attributes are **unconditionally loaded** into system instructions, guaranteeing 100% adherence to user preferences without relying on probabilistic semantic retrieval.

```python
from litellm_adk.memory import LongTermMemory

memory = LongTermMemory()

# Store deterministic persona attributes for user_123
await memory.add_profile_attribute(
    user_id="user_123",
    key="response_format",
    value="Always respond in concise markdown tables with code blocks in Python.",
)

profile = await memory.get_profile("user_123")
```

### Tier 2: Episodic Semantic Vector Store
Unstructured conversational memory, historical decisions, and notes embedded into a `VectorStore`. The agent automatically queries this store using the user's incoming message, injecting only the top-k most relevant historical context chunks.

```python
from litellm_adk.memory import LongTermMemory
from litellm_adk.vector import InMemoryVectorStore

vector_store = InMemoryVectorStore()
memory = LongTermMemory(episodic_store=vector_store)

# Store episodic memory chunks tagged by user_id
await memory.add_episodic_memory(
    user_id="user_123",
    content="User migrated production databases from MongoDB to PostgreSQL on AWS RDS in Q3.",
)

# Semantic retrieval filtered by user_id
relevant_notes = await memory.search_episodic_memory(
    user_id="user_123",
    query="What database technology does the user deploy in production?",
    limit=3,
)
```

---

## 4. Context Management & Window Compaction (`ContextManager`)

When conversation history grows, naive message appending causes context overflows and inflated latency. The `ContextManager` applies dynamic compaction policies:

```python
from litellm_adk.context import ContextManager, ContextPolicy, ContextStrategy

context_mgr = ContextManager(
    policy=ContextPolicy(
        max_tokens=4096,                          # Hard context token cap
        strategy=ContextStrategy.SLIDING_WINDOW,  # Sliding window compaction
        preserve_system_prompt=True,              # Never evict system instructions
        preserve_last_n_messages=4,               # Always preserve recent exchanges
    )
)

agent = Agent(
    model="gpt-4o",
    context_manager=context_mgr,
)
```

### Compaction Strategies (`ContextStrategy`)

1. **`SLIDING_WINDOW`**: Evicts the oldest non-system messages once token count exceeds `max_tokens`.
2. **`SUMMARIZATION`**: Uses a background LLM call to condense older conversation turns into a summarized context chunk.
3. **`SEMANTIC_TRUNCATION`**: Removes intermediate tool calling traces while keeping final assistant answers.

---

## 5. Vector Store & RAG Retrieval (`VectorStore`)

Connect vector stores directly to agents for semantic document retrieval:

```python
from litellm_adk.vector import InMemoryVectorStore, Retriever

vector_store = InMemoryVectorStore()
await vector_store.add_documents([
    "Company refund policy: Returns are accepted within 30 days with receipt.",
    "Shipping policy: Free ground shipping applies to orders over $50.",
])

retriever = Retriever(vector_store=vector_store, top_k=2)

agent = Agent(
    model="gpt-4o",
    retriever=retriever,
    system_prompt="Answer customer policy questions accurately using retrieved knowledge.",
)
```
