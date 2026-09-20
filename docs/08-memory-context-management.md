# Memory & Context Management

The LiteLLM ADK provides a multi-layer memory architecture (`src/litellm_adk/memory/`) and context compaction engine (`src/litellm_adk/context/`) to ensure agents retain conversational context across turns without exceeding LLM context windows or incurring runaway token costs.

---

## 1. Multi-Layer Memory Architecture

```mermaid
graph TD
    UserTurn["User Turn Input"] --> Agent["Agent Orchestrator"]
    
    subgraph "Multi-Layer Memory Hierarchy"
        Agent <--> WorkingMem["1. Working Memory\n(Scratchpad for active reasoning turn)"]
        Agent <--> ConvoMem["2. Conversation Memory\n(Multi-turn dialog history)"]
        Agent <--> LongTermMem["3. Long-Term Memory\n(Persistent key-value / document store)"]
        Agent <--> VectorMem["4. Vector Store (RAG)\n(Semantic similarity lookup)"]
    end
    
    subgraph "Storage Adapters"
        LongTermMem --> SQLite["SQLAlchemy (SQLite, Postgres, MySQL)"]
        LongTermMem --> Mongo["MongoDB Backend"]
        LongTermMem --> Files["FileMemory (JSON / YAML)"]
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

## 3. Context Management & Window Compaction (`ContextManager`)

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

## 4. Vector Store & RAG Retrieval (`VectorStore`)

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
