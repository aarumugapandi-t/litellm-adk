"""Vector Search Node querying embedded vector stores and RAG collections."""

from typing import Any, Dict, List
from .base import Node, NodeContext, NodeDefinition, NodeResult
from ..expressions import evaluate_template
from ..state import ExecutionStatus
from ...vector.stores.in_memory import InMemoryVectorStore
from ...vector.retriever import Retriever
from ...vector.base import VectorItem


_SHARED_VECTOR_STORE = InMemoryVectorStore()


class VectorSearchNode:
    """Semantic vector search node retrieving top-k relevant context chunks."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="vector_search",
            name="Vector Search",
            description="Searches a semantic vector index or knowledge base using similarity matching.",
            category="Memory & Vector",
            icon="search",
            inputs=["input"],
            outputs=["output"],
            config_schema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or question (supports {{ expressions }})",
                        "default": "{{ trigger.input }}"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top matching documents to retrieve",
                        "default": 3
                    },
                    "similarity_threshold": {
                        "type": "number",
                        "description": "Minimum similarity score threshold (0.0 - 1.0)",
                        "default": 0.0
                    },
                    "seed_documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional inline documents to seed into the search index",
                        "default": []
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        raw_query = cfg.get("query", "")
        top_k = int(cfg.get("top_k", 3))
        threshold = float(cfg.get("similarity_threshold", 0.0))
        seed_docs = cfg.get("seed_documents", [])

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        query = str(evaluate_template(raw_query, eval_ctx))

        try:
            # Seed any inline documents if provided
            if seed_docs:
                items = [VectorItem(id=f"doc_{i}", content=doc) for i, doc in enumerate(seed_docs)]
                await _SHARED_VECTOR_STORE.add(items)

            retriever = Retriever(vector_store=_SHARED_VECTOR_STORE, top_k=top_k, min_score=threshold)
            results = await retriever.retrieve(query)

            docs_payload = [
                {"id": r.item.id, "content": r.item.content, "score": r.score, "metadata": r.item.metadata}
                for r in results
            ]
            return NodeResult(output=docs_payload, status=ExecutionStatus.COMPLETED)
        except Exception as e:
            return NodeResult(output=[], status=ExecutionStatus.FAILED, error=str(e))
