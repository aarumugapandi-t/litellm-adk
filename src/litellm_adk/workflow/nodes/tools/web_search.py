"""Web Search Tool Node for AI Agent attachment and direct pipeline search."""

from typing import Any, Dict
from ..base import NodeContext, NodeDefinition, NodeResult
from ...expressions import evaluate_template
from ...state import ExecutionStatus
from ....tools.builtin.web_search import create_web_search_tool, perform_web_search


class WebSearchToolNode:
    """Provides web search capability to connected Agents or executes search directly in a pipeline."""

    @property
    def definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="web_search_tool",
            name="Web Search",
            description="Equips AI agents with live web search, or executes an internet search directly.",
            category="Tools",
            icon="search",
            inputs=["input"],
            outputs=["tool", "output"],
            config_schema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to retrieve",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (used if running sequentially in pipeline)",
                        "default": "{{ trigger.query }}"
                    }
                }
            }
        )

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node_config
        max_results = int(cfg.get("max_results", 5))
        tool_obj = create_web_search_tool(max_results=max_results)

        eval_ctx: Dict[str, Any] = {
            "trigger": context.trigger_data,
            "variables": context.variables,
            "inputs": context.inputs,
            "execution": {"id": context.execution_id},
        }
        eval_ctx.update(context.inputs)

        # If a query is provided in pipeline mode, execute direct search
        raw_query = cfg.get("query", "")
        direct_output = None
        if raw_query:
            query_rendered = str(evaluate_template(raw_query, eval_ctx)).strip()
            if query_rendered and query_rendered != "{{ trigger.query }}":
                direct_output = perform_web_search(query_rendered, max_results=max_results)

        return NodeResult(
            output=tool_obj if direct_output is None else direct_output,
            status=ExecutionStatus.COMPLETED,
            metadata={
                "tool": tool_obj,
                "tool_name": "web_search",
                "direct_output": direct_output
            }
        )
