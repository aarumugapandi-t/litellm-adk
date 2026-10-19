"""Transformers, query decomposers, rank fusion, and routers for retrieval."""

import asyncio
import difflib
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Union

from ..observability.logger import adk_logger
from .base import VectorSearchResult
from .strategy import (
    MultiQueryConfig,
    QueryTransformationConfig,
    QueryTransformationResult,
    RetrievalRouterConfig,
    RetrievalStrategy,
)


class ReciprocalRankFusion:
    """Merges and deduplicates multiple ranked search result lists via Reciprocal Rank Fusion (RRF)."""

    @classmethod
    def fuse(
        cls,
        ranked_lists: Sequence[Sequence[VectorSearchResult]],
        k: int = 60,
        top_k: Optional[int] = None,
    ) -> List[VectorSearchResult]:
        """Fuses multiple ranked result lists using standard RRF score: 1 / (k + rank)."""
        if not ranked_lists:
            return []

        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, VectorSearchResult] = {}

        for r_list in ranked_lists:
            for rank, item in enumerate(r_list):
                # Unique identifier based on id or text hash
                item_id = getattr(item.item, "id", None) if hasattr(item, "item") else getattr(item, "id", None)
                doc_key = item_id or item.text
                doc_map[doc_key] = item
                score = 1.0 / (k + (rank + 1))
                doc_scores[doc_key] = doc_scores.get(doc_key, 0.0) + score

        # Sort descending by fused RRF score
        sorted_keys = sorted(doc_scores.keys(), key=lambda dk: doc_scores[dk], reverse=True)

        fused_results: List[VectorSearchResult] = []
        for dk in sorted_keys:
            orig = doc_map[dk]
            item_obj = orig.item if hasattr(orig, "item") else orig
            fused_results.append(
                VectorSearchResult(
                    item=item_obj,
                    score=doc_scores[dk],
                )
            )

        if top_k is not None and top_k > 0:
            return fused_results[:top_k]
        return fused_results


class ConditionalQueryTransformer:
    """Analyzes user input and conversation history dynamically to determine if search is needed and rewrites queries."""

    def __init__(
        self,
        model: Optional[Any] = None,
        config: Optional[QueryTransformationConfig] = None,
    ):
        self.model = model
        self.config = config or QueryTransformationConfig()

    def _matches_intent_heuristic(self, query: str) -> Optional[bool]:
        """Evaluates optional user-configured intent evaluator or custom phrases dynamically."""
        if self.config.intent_evaluator and callable(self.config.intent_evaluator):
            res = self.config.intent_evaluator(query)
            if res is not None:
                return bool(res)

        if self.config.custom_chitchat_phrases:
            cleaned = re.sub(r"[^\w\s]", "", query.strip().lower())
            if difflib.get_close_matches(cleaned, self.config.custom_chitchat_phrases, n=1, cutoff=0.75):
                return False

        # Trivial single-character or empty inputs do not require external search
        words = query.strip().split()
        if len(words) == 0 or (len(words) == 1 and len(words[0]) <= 1):
            return False

        return None

    async def transform(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> QueryTransformationResult:
        """Evaluates whether external search is needed and produces standalone search query."""
        # 1. Check dynamic intent heuristic / custom config
        heuristic_res = self._matches_intent_heuristic(query)
        if heuristic_res is False:
            return QueryTransformationResult(
                needs_search=False,
                reasoning="Query matched non-retrieval intent criteria.",
                search_query=None,
            )

        # 2. If no model provided, proceed with direct search without hardcoded assumptions
        if not self.model:
            return QueryTransformationResult(
                needs_search=True,
                reasoning="No transformer model configured; proceeding with direct query search.",
                search_query=query,
            )

        # 3. Model-based evaluation and coreference resolution
        recent_history = []
        if history:
            turns = self.config.include_history_turns * 2
            recent_history = history[-turns:]

        prompt = (
            "Analyze the following user query and dialogue history to determine if external knowledge "
            "base retrieval is required.\n\n"
            "Guidelines:\n"
            "1. 'needs_search': false if the query is pure greetings, self-contained logic/math, "
            "programming questions not referencing external docs, or already answerable from previous turns.\n"
            "2. 'needs_search': true if the query asks for specific factual documentation, policies, "
            "company facts, or domain knowledge.\n"
            "3. 'search_query': if needs_search is true, formulate a clear, standalone search query "
            "resolving any pronouns ('it', 'they', 'that') using the dialogue history.\n\n"
            f"Dialogue History: {json.dumps(recent_history)}\n"
            f"User Query: {query}\n\n"
            "Respond ONLY with valid JSON matching this schema:\n"
            '{"needs_search": true/false, "reasoning": "...", "search_query": "..."}'
        )

        try:
            if hasattr(self.model, "generate"):
                resp = await self.model.generate(prompt=prompt)
                content = getattr(resp, "content", "")
            elif hasattr(self.model, "acompletion"):
                resp = await self.model.acompletion(messages=[{"role": "user", "content": prompt}])
                content = resp.choices[0].message.content
            else:
                return QueryTransformationResult(needs_search=True, search_query=query)

            # Parse JSON from response
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return QueryTransformationResult(
                    needs_search=bool(data.get("needs_search", True)),
                    reasoning=data.get("reasoning"),
                    search_query=data.get("search_query") or query,
                )
        except Exception as e:
            adk_logger.warning("Query transformation model error: %s. Falling back to direct query.", e)

        return QueryTransformationResult(needs_search=True, search_query=query)


class MultiQueryDecomposer:
    """Decomposes multi-faceted or comparative questions into focused sub-queries."""

    def __init__(
        self,
        model: Optional[Any] = None,
        config: Optional[MultiQueryConfig] = None,
    ):
        self.model = model
        self.config = config or MultiQueryConfig()

    def _heuristic_split(self, query: str) -> List[str]:
        # Fast split on comparative constructs
        patterns = [r"\bvs\b", r"\bversus\b", r"\bcompared to\b", r"\bdifference between\b"]
        for p in patterns:
            parts = re.split(p, query, flags=re.IGNORECASE)
            if len(parts) > 1:
                cleaned = [part.strip(" ,.?!") for part in parts if part.strip(" ,.?!")]
                if len(cleaned) > 1:
                    return cleaned[: self.config.max_sub_queries]
        return [query]

    async def decompose(self, query: str) -> List[str]:
        """Generates sub-queries for parallel multi-faceted search."""
        if not self.model:
            return self._heuristic_split(query)

        prompt = (
            f"Decompose the following complex query into 2 to {self.config.max_sub_queries} distinct, "
            "concise sub-queries for independent vector database search.\n"
            f"Query: {query}\n\n"
            "Output each sub-query on a separate line without numbers or bullet points."
        )

        try:
            if hasattr(self.model, "generate"):
                resp = await self.model.generate(prompt=prompt)
                content = getattr(resp, "content", "")
            elif hasattr(self.model, "acompletion"):
                resp = await self.model.acompletion(messages=[{"role": "user", "content": prompt}])
                content = resp.choices[0].message.content
            else:
                return self._heuristic_split(query)

            lines = [line.strip("- *").strip() for line in content.splitlines() if line.strip("- *").strip()]
            if lines:
                return lines[: self.config.max_sub_queries]
        except Exception as e:
            adk_logger.warning("Multi-query decomposition error: %s. Falling back to heuristic split.", e)

        return self._heuristic_split(query)


class RetrievalRouter:
    """Directs incoming queries dynamically to the optimal retrieval strategy.

    Supports LLM semantic classification and dynamic, typo-tolerant fuzzy matching
    so queries with spelling mistakes and phrasing variations are routed accurately.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        config: Optional[RetrievalRouterConfig] = None,
    ):
        self.model = model
        self.config = config or RetrievalRouterConfig()

    async def route(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> RetrievalStrategy:
        """Dynamically routes queries using model semantic classification when available."""
        if self.model:
            prompt = (
                "Classify the following user query into the optimal retrieval strategy, taking into account "
                "context and any potential typos or spelling mistakes:\n"
                "- 'multi_query': Comparative or multifaceted queries exploring multiple topics or options.\n"
                "- 'conditional_transform': Ambiguous queries, contextual follow-ups, or queries referencing previous conversation turns/pronouns.\n"
                "- 'direct': Standalone factual inquiries.\n\n"
                f"Query: {query}\n\n"
                "Respond with ONLY one word: 'multi_query', 'conditional_transform', or 'direct'."
            )
            try:
                if hasattr(self.model, "generate"):
                    resp = await self.model.generate(prompt=prompt)
                    decision = getattr(resp, "content", "").strip().lower()
                elif hasattr(self.model, "acompletion"):
                    resp = await self.model.acompletion(messages=[{"role": "user", "content": prompt}])
                    decision = resp.choices[0].message.content.strip().lower()
                else:
                    decision = ""

                clean = re.sub(r"[^\w_]", "", decision)
                if "multi" in clean:
                    return RetrievalStrategy.MULTI_QUERY
                if "transform" in clean or "condition" in clean:
                    return RetrievalStrategy.CONDITIONAL_TRANSFORM
                if "direct" in clean:
                    return RetrievalStrategy.DIRECT
            except Exception as e:
                adk_logger.warning("Router model classification error: %s. Using dynamic fuzzy routing.", e)

        return self.route_fuzzy(query)

    def route_fuzzy(self, query: str) -> RetrievalStrategy:
        """Dynamic typo-tolerant string similarity matching using difflib close matches."""
        q_clean = query.strip().lower()
        tokens = [w for w in re.findall(r"\b\w+\b", q_clean) if len(w) > 1]
        cutoff = self.config.fuzzy_cutoff

        comparative_pool = self.config.comparative_keywords or [
            "compare", "versus", "difference", "differ", "pros and cons", "trade-offs"
        ]
        contextual_pool = self.config.contextual_pronouns or [
            "it", "they", "them", "that", "this", "its", "those", "these", "their"
        ]

        # 1. Comparative check with typo tolerance (e.g. "copmare" -> "compare", "differnce" -> "difference")
        for token in tokens:
            if difflib.get_close_matches(token, comparative_pool, n=1, cutoff=cutoff):
                return RetrievalStrategy.MULTI_QUERY

        # 2. Contextual pronoun check with typo tolerance (e.g. "theri" -> "their", "taht" -> "that")
        for token in tokens:
            if difflib.get_close_matches(token, contextual_pool, n=1, cutoff=cutoff):
                return RetrievalStrategy.CONDITIONAL_TRANSFORM

        return RetrievalStrategy.DIRECT

    def route_heuristic(self, query: str) -> RetrievalStrategy:
        """Backward-compatible synchronous method delegating to typo-tolerant route_fuzzy."""
        return self.route_fuzzy(query)
