"""Native Agent Tool abstraction for vector and knowledge base retrieval."""

from typing import Any, Dict, List, Optional
from ..tools.base import Tool, ToolPermission


class RetrieverTool(Tool):
    """First-class Agent Tool enabling the LLM to search knowledge bases autonomously.
    
    The LLM decides when to search, reformulates queries, resolves coreferences,
    and can invoke search multiple times (including parallel calls) during reasoning.
    """

    def __init__(
        self,
        retriever: Any,
        name: str = "search_knowledge_base",
        description: Optional[str] = None,
        top_k: Optional[int] = None,
        working_memory: Optional[Any] = None,
    ):
        self.retriever = retriever
        self.top_k = top_k
        self.working_memory = working_memory
        self._seen_hashes: set = set()

        def reset_cache() -> None:
            """Resets deduplication cache at the beginning of a reasoning turn."""
            self._seen_hashes.clear()

        self.reset_cache = reset_cache

        tool_desc = description or (
            "Searches the knowledge base / document repository for relevant information. "
            "Use this tool whenever you need factual domain knowledge, policies, technical documentation, "
            "or verification. Formulate the query as a specific, standalone search query, resolving "
            "any pronouns or references from conversation history."
        )

        async def _search_knowledge(query: str, limit: Optional[int] = None) -> str:
            """Execute semantic retrieval against the knowledge base with turn-level deduplication."""
            effective_k = limit if limit is not None else self.top_k
            results = await self.retriever.retrieve_context(query, top_k=effective_k)

            if not results:
                return "No relevant documents found in knowledge base."

            # Deduplicate chunks across concurrent/parallel tool calls in the same turn
            unique_results = []
            for doc in results:
                d_hash = hash(doc.strip())
                if d_hash not in self._seen_hashes:
                    self._seen_hashes.add(d_hash)
                    unique_results.append(doc)

            if not unique_results:
                return "Relevant documents were already retrieved in this turn. Refer to previous search results."

            formatted_docs = []
            for idx, doc in enumerate(unique_results, start=1):
                formatted_docs.append(f"[{idx}] {doc}")

            return "\n\n".join(formatted_docs)

        parameters: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The specific, standalone search query. Resolve any pronouns, ambiguous terms, "
                        "or contextual references from previous turns."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional maximum number of document chunks to retrieve.",
                },
            },
            "required": ["query"],
        }

        super().__init__(
            func=_search_knowledge,
            name=name,
            description=tool_desc,
            parameters=parameters,
            permissions={ToolPermission.READ},
        )
