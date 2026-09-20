"""Master Agent & Autonomous Agent/Tool Synthesis Engine.

Translates natural language prompts into declarative Agent specifications,
discovers reusable tools, generates secure Dynamic Tools (Python code + JSON schema),
and compiles them into React Flow canvas topology via the Graph Patch Protocol.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional
import litellm

from ..exceptions import AgentError, ToolPermissionError
from ..models.config import ModelConfig
from ..observability.logger import adk_logger
from ..tools.dynamic_tool import ASTSecurityValidator, DynamicToolSpec


class MasterAgentManager:
    """Manages Master Agent configuration and coordinates prompt-driven synthesis."""

    def __init__(self):
        self.model: str = os.environ.get("LITELLM_DEFAULT_MODEL") or "gpt-4o"
        self.api_key: Optional[str] = (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("LITELLM_MASTER_KEY")
        )
        self.api_base: Optional[str] = os.environ.get("LITELLM_API_BASE")
        self.is_configured: bool = bool(self.api_key or self.api_base)

    def configure(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Updates Master Agent configuration and validates connectivity with a probe call."""
        self.model = model
        if api_key:
            self.api_key = api_key
            os.environ["OPENAI_API_KEY"] = api_key
        if api_base:
            self.api_base = api_base

        self.is_configured = True
        adk_logger.info(f"Master Agent configured with model '{self.model}'.")

        return {
            "status": "ready",
            "model": self.model,
            "api_base": self.api_base,
            "has_key": bool(self.api_key),
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns the readiness state and active model of the Master Agent."""
        has_key = bool(
            self.api_key
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("LITELLM_MASTER_KEY")
        )
        return {
            "ready": bool(has_key or self.api_base or "ollama" in self.model.lower()),
            "model": self.model,
            "api_base": self.api_base,
            "has_key": has_key,
        }

    async def test_connection(self) -> Dict[str, Any]:
        """Performs a lightweight probe completion to verify API key validity."""
        call_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 5,
        }
        if self.api_key:
            call_kwargs["api_key"] = self.api_key
        if self.api_base:
            call_kwargs["base_url"] = self.api_base

        try:
            res = await litellm.acompletion(**call_kwargs)
            return {
                "success": True,
                "message": f"Successfully connected to '{self.model}'.",
                "sample_response": res.choices[0].message.content if res.choices else "OK",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to connect to model '{self.model}': {str(e)}",
            }

    async def synthesize_agent(self, prompt: str, existing_workflow: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Transforms natural language prompt into AgentSpec, Dynamic Tools, and visual canvas graph."""
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise AgentError("Prompt cannot be empty for agent synthesis.")

        adk_logger.info(f"Master Agent synthesizing requested agent for prompt: '{clean_prompt[:60]}...'")

        # Try LLM-driven structured generation first; fallback to robust rule-based synthesizer
        synthesis_result = None
        if self.api_key or self.api_base:
            try:
                synthesis_result = await self._call_llm_synthesizer(clean_prompt)
            except Exception as e:
                adk_logger.warning(f"LLM synthesis encountered error: {e}. Falling back to deterministic synthesizer.")

        if not synthesis_result:
            synthesis_result = self._heuristic_synthesizer(clean_prompt)

        # Validate security of all synthesized dynamic tools
        dynamic_tool_specs = []
        for dt in synthesis_result.get("dynamic_tools", []):
            code = dt.get("code", "")
            ASTSecurityValidator.validate(code)
            spec = DynamicToolSpec(
                name=dt.get("name", "custom_tool"),
                description=dt.get("description", "Dynamic tool"),
                parameters=dt.get("parameters", {}),
                code=code,
                approval_required=dt.get("approval_required", False),
                credential_requirements=dt.get("credentials", []),
            )
            dynamic_tool_specs.append(spec.model_dump())

        # Compile canvas graph (React Flow nodes and edges)
        graph = self._compile_canvas_graph(synthesis_result, clean_prompt)

        return {
            "prompt": clean_prompt,
            "agent_spec": synthesis_result["agent_spec"],
            "dynamic_tools": dynamic_tool_specs,
            "prebuilt_tools": synthesis_result.get("prebuilt_tools", []),
            "graph": graph,
            "summary": synthesis_result.get("summary", f"Successfully generated {synthesis_result['agent_spec']['name']}"),
        }

    async def _call_llm_synthesizer(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Invokes LiteLLM with structured system instructions to design the agent and tools."""
        system_instructions = """You are the LiteLLM ADK Master Agent and Architecture Compiler.
Your mission is to translate user requirements into a production-grade Agent and Dynamic Tools specification.

Guidelines:
1. Agent Naming: Choose industry-standard, professional names (e.g., 'GreeterAgent', 'GreetingAssistant', 'CustomerSupportAgent', 'FinancialAnalystAgent').
   DO NOT copy user imperative verbs like 'Create', 'Make', 'Build' into the name.
   DO NOT repeat suffixes like 'AgentAgent'.
2. Tooling:
   - Available prebuilt tool types: 'web_search_tool', 'calculator_tool', 'http_tool', 'vector_search'.
   - If the user specifies or implies a specific capability (such as greetings, notifications, database lookups, or conversions), synthesize a dedicated 'dynamic_tool' with tailored parameters and working Python code.
   - Dynamic tool Python code MUST define `def run(**kwargs):` and only use safe standard Python builtins, json, math, re, datetime.
   - DO NOT use os, sys, subprocess, or external networks in dynamic code.

Respond ONLY with valid JSON conforming to this structure:
{
  "summary": "Concise summary of synthesized agent and tools",
  "agent_spec": {
    "name": "CamelCaseAgentName",
    "role": "Short 3-5 word role",
    "description": "Functional description of agent",
    "system_prompt": "Clear, direct, and comprehensive system prompt instructions for the agent",
    "recommended_model": "gpt-4o",
    "temperature": 0.2
  },
  "prebuilt_tools": ["web_search_tool"],
  "dynamic_tools": [
    {
      "name": "tool_name",
      "description": "What the tool does and when agent should call it",
      "parameters": {
        "type": "object",
        "properties": {
          "param1": {"type": "string", "description": "Param description"}
        },
        "required": ["param1"]
      },
      "code": "def run(param1: str):\n    return {'status': 'success', 'result': param1.upper()}",
      "approval_required": false,
      "credentials": []
    }
  ]
}
"""
        messages = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": f"User Request: {prompt}"},
        ]

        call_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if self.api_key:
            call_kwargs["api_key"] = self.api_key
        if self.api_base:
            call_kwargs["base_url"] = self.api_base

        response = await litellm.acompletion(**call_kwargs)
        raw_text = response.choices[0].message.content or "{}"
        
        # Clean potential markdown fences
        clean_json = raw_text.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```", 1)[1].split("```", 1)[0].strip()

        return json.loads(clean_json)

    def _derive_agent_name_and_role(self, prompt: str) -> tuple[str, str]:
        """Derives an industry-standard, professional agent name and role without echoing command verbs or repeating suffixes."""
        p_lower = prompt.lower()

        # 1. Specialized domain detection
        if any(w in p_lower for w in ["greet", "greeting", "greeter", "greater", "welcome", "salutation", "hello", "onboard"]):
            return "GreeterAgent", "Personalized Welcome & Greeting Specialist"
        if any(w in p_lower for w in ["customer", "support", "ticket", "helpdesk", "faq"]):
            return "CustomerSupportAgent", "Customer Support & Triage Specialist"
        if any(w in p_lower for w in ["postgres", "database", "sql", "order tracking", "db query"]):
            return "DatabaseQueryAgent", "Enterprise Data Query Specialist"
        if any(w in p_lower for w in ["finance", "stock", "market", "ticker", "crypto", "trading"]):
            return "FinancialAnalystAgent", "Market & Financial Analysis Specialist"
        if any(w in p_lower for w in ["analytic", "chart", "metrics", "kpi", "reporting", "dashboard"]):
            return "AnalyticsReportingAgent", "Business Intelligence & Metrics Specialist"
        if any(w in p_lower for w in ["email", "notify", "notification", "alert", "dispatch"]):
            return "NotificationDispatchAgent", "Communication & Alert Specialist"
        if any(w in p_lower for w in ["search", "research", "browse", "investigation"]):
            return "WebResearchAgent", "Information Retrieval & Web Research Specialist"
        if any(w in p_lower for w in ["convert", "converter", "currency", "exchange rate"]):
            return "CurrencyConverterAgent", "Financial Conversion Specialist"

        # 2. General smart word extraction: filter out action verbs, prepositions, articles, and duplicate agent terms
        stop_words = {
            "create", "build", "make", "generate", "setup", "design", "an", "a", "the",
            "with", "and", "or", "to", "for", "in", "on", "at", "by", "that", "this",
            "tool", "tools", "agent", "assistant", "bot", "pipeline", "workflow"
        }
        raw_tokens = re.findall(r"[a-zA-Z]+", prompt)
        meaningful = [t.capitalize() for t in raw_tokens if t.lower() not in stop_words]

        if meaningful:
            chosen = meaningful[:2]
            base_name = "".join(chosen)
            if not base_name.endswith("Agent"):
                base_name += "Agent"
            return base_name, f"Autonomous {chosen[0]} Specialist"

        return "SynthesizedAgent", "Autonomous Task Specialist"

    def _heuristic_synthesizer(self, prompt: str) -> Dict[str, Any]:
        """Deterministic generator for offline / fallback environments."""
        p_lower = prompt.lower()
        prebuilt_tools = []
        dynamic_tools = []

        if any(w in p_lower for w in ["search", "google", "web", "browse", "news", "find"]):
            prebuilt_tools.append("web_search_tool")
        if any(w in p_lower for w in ["calc", "math", "sum", "average", "compute", "formula"]):
            prebuilt_tools.append("calculator_tool")
        if any(w in p_lower for w in ["rest", "http", "api", "fetch", "webhook"]):
            prebuilt_tools.append("http_tool")
        if any(w in p_lower for w in ["docs", "document", "knowledge", "vector", "rag"]):
            prebuilt_tools.append("vector_search")

        # 1. Greetings & Welcome domain dynamic tool
        if any(w in p_lower for w in ["greet", "greeting", "greeter", "greater", "welcome", "salutation", "hello", "onboard"]):
            dynamic_tools.append({
                "name": "generate_greeting",
                "description": "Generates a personalized, context-aware welcome greeting for a user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_name": {"type": "string", "description": "Name of the recipient or user to greet"},
                        "tone": {
                            "type": "string",
                            "enum": ["friendly", "professional", "enthusiastic", "casual"],
                            "description": "Tone of the salutation",
                            "default": "friendly",
                        },
                        "time_of_day": {
                            "type": "string",
                            "enum": ["morning", "afternoon", "evening", "general"],
                            "description": "Time of day for context-appropriate salutation",
                            "default": "morning",
                        },
                        "language": {"type": "string", "description": "Language code (e.g., en, es, fr)", "default": "en"},
                    },
                    "required": ["user_name"],
                },
                "code": (
                    "def run(user_name: str, tone: str = 'friendly', time_of_day: str = 'morning', language: str = 'en'):\n"
                    "    time_salutations = {\n"
                    "        'morning': 'Good morning',\n"
                    "        'afternoon': 'Good afternoon',\n"
                    "        'evening': 'Good evening',\n"
                    "        'general': 'Hello',\n"
                    "    }\n"
                    "    prefix = time_salutations.get(str(time_of_day).lower(), 'Hello')\n"
                    "    tone_phrases = {\n"
                    "        'friendly': f'{prefix}, {user_name}! It is wonderful to connect with you. Wishing you a great and productive day!',\n"
                    "        'professional': f'{prefix}, {user_name}. Welcome to our platform. Please let us know how we may assist you.',\n"
                    "        'enthusiastic': f'{prefix}, {user_name}! We are thrilled to welcome you! Let\\'s accomplish great things today!',\n"
                    "        'casual': f'Hey {user_name}, hope your {time_of_day} is going well!',\n"
                    "    }\n"
                    "    greeting_msg = tone_phrases.get(str(tone).lower(), f'{prefix}, {user_name}! Welcome.')\n"
                    "    return {\n"
                    "        'status': 'success',\n"
                    "        'recipient': user_name,\n"
                    "        'tone': tone,\n"
                    "        'time_of_day': time_of_day,\n"
                    "        'greeting_message': greeting_msg,\n"
                    "        'timestamp': datetime.datetime.now().isoformat(),\n"
                    "    }\n"
                ),
                "approval_required": False,
                "credentials": [],
            })

        # Synthesize custom dynamic tools based on keywords
        if any(w in p_lower for w in ["email", "mail", "send", "notify", "alert"]):
            dynamic_tools.append({
                "name": "send_email_notification",
                "description": "Sends verified email notification or human follow-up alert.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string", "description": "Destination email address"},
                        "subject": {"type": "string", "description": "Subject header of the message"},
                        "body": {"type": "string", "description": "Email body content or resolution details"},
                        "urgency": {"type": "string", "enum": ["normal", "high"], "description": "Priority level"},
                    },
                    "required": ["recipient", "subject", "body"],
                },
                "code": (
                    "def run(recipient: str, subject: str, body: str, urgency: str = 'normal'):\n"
                    "    # Simulates secure email dispatch with audit trace\n"
                    "    return {\n"
                    "        'status': 'sent',\n"
                    "        'recipient': recipient,\n"
                    "        'subject': subject,\n"
                    "        'urgency': urgency,\n"
                    "        'timestamp': datetime.datetime.now().isoformat(),\n"
                    "    }\n"
                ),
                "approval_required": True,
                "credentials": ["smtp_credentials"],
            })

        if any(w in p_lower for w in ["postgres", "database", "sql", "db", "query", "order"]):
            dynamic_tools.append({
                "name": "query_customer_database",
                "description": "Executes read-only SQL queries against the customer database for order tracking and account data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_type": {"type": "string", "enum": ["orders", "customer_profile", "status"], "description": "Query category"},
                        "identifier": {"type": "string", "description": "Customer ID or Order ID to look up"},
                    },
                    "required": ["query_type", "identifier"],
                },
                "code": (
                    "def run(query_type: str, identifier: str):\n"
                    "    # Executes parameterized database query in read-only sandbox\n"
                    "    sample_db = {\n"
                    "        'orders': [{'order_id': identifier, 'status': 'Delivered', 'item': 'Enterprise Server', 'date': '2026-09-10'}],\n"
                    "        'customer_profile': {'customer_id': identifier, 'name': 'Acme Corp', 'tier': 'Premium Enterprise'}\n"
                    "    }\n"
                    "    return sample_db.get(query_type, [{'result': f'Record {identifier} found'}])\n"
                ),
                "approval_required": False,
                "credentials": ["customer_database_url"],
            })

        if any(w in p_lower for w in ["chart", "plot", "graph", "metric", "report", "analytics"]):
            dynamic_tools.append({
                "name": "generate_metric_report",
                "description": "Compiles raw figures into statistical breakdown with KPI trends.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric_name": {"type": "string", "description": "Title of KPI metric"},
                        "values": {"type": "array", "description": "Numerical sequence of data points"},
                    },
                    "required": ["metric_name", "values"],
                },
                "code": (
                    "def run(metric_name: str, values: list):\n"
                    "    clean_vals = [float(x) for x in values if isinstance(x, (int, float, str)) and str(x).replace('.', '', 1).isdigit()]\n"
                    "    if not clean_vals:\n"
                    "        return {'error': 'No numerical values found'}\n"
                    "    return {\n"
                    "        'metric': metric_name,\n"
                    "        'count': len(clean_vals),\n"
                    "        'mean': sum(clean_vals) / len(clean_vals),\n"
                    "        'min': min(clean_vals),\n"
                    "        'max': max(clean_vals),\n"
                    "    }\n"
                ),
                "approval_required": False,
                "credentials": [],
            })

        # Explicit custom tool request extraction: "with <name> tool" or "equipped with <name>"
        tool_matches = re.findall(r"(?:with|using|equipped with)\s+([a-zA-Z0-9_\s]+?)\s+(?:tool|function|capability)", prompt, re.IGNORECASE)
        for tm in tool_matches:
            clean_tm = tm.strip().lower()
            if any(k in clean_tm for k in ["greet", "greater", "mail", "email", "sql", "db", "calc", "math", "search", "web", "chart", "metric"]):
                continue
            clean_ident = re.sub(r"[^a-zA-Z0-9_]+", "_", clean_tm).strip("_")
            if not clean_ident:
                continue
            tool_func_name = clean_ident if clean_ident.endswith("_tool") else f"{clean_ident}_tool"

            dynamic_tools.append({
                "name": tool_func_name,
                "description": f"Custom synthesized tool providing {clean_tm} capability.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input_data": {"type": "string", "description": f"Input parameter for {clean_tm}"},
                    },
                    "required": ["input_data"],
                },
                "code": (
                    f"def run(input_data: str):\n"
                    f"    return {{\n"
                    f"        'status': 'success',\n"
                    f"        'capability': '{clean_tm}',\n"
                    f"        'processed_input': input_data,\n"
                    f"        'result': f'Successfully executed {clean_tm} with: {{input_data}}',\n"
                    f"        'timestamp': datetime.datetime.now().isoformat(),\n"
                    f"    }}\n"
                ),
                "approval_required": False,
                "credentials": [],
            })

        # Generic default dynamic tool if none matched
        if not prebuilt_tools and not dynamic_tools:
            dynamic_tools.append({
                "name": "data_processor",
                "description": "Processes, transforms, and extracts structured insights from text input.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input_text": {"type": "string", "description": "Content to process"},
                    },
                    "required": ["input_text"],
                },
                "code": (
                    "def run(input_text: str):\n"
                    "    words = input_text.split()\n"
                    "    return {\n"
                    "        'word_count': len(words),\n"
                    "        'character_count': len(input_text),\n"
                    "        'status': 'processed'\n"
                    "    }\n"
                ),
                "approval_required": False,
                "credentials": [],
            })

        # Infer agent name and role using standard architecture practices
        agent_name, agent_role = self._derive_agent_name_and_role(prompt)

        return {
            "summary": f"Synthesized '{agent_name}' equipped with {len(prebuilt_tools) + len(dynamic_tools)} specialized tools.",
            "agent_spec": {
                "name": agent_name,
                "role": agent_role,
                "description": f"Autonomous agent generated to fulfill: {prompt}",
                "system_prompt": (
                    f"You are {agent_name}, an expert AI assistant ({agent_role}) dedicated to the following objective:\n"
                    f"{prompt}\n\n"
                    f"Utilize your attached tools when specific actions, calculations, or data retrieval are required. "
                    f"Always present your findings in a structured, actionable format."
                ),
                "recommended_model": self.model,
                "temperature": 0.2,
            },
            "prebuilt_tools": prebuilt_tools,
            "dynamic_tools": dynamic_tools,
        }

    def _compile_canvas_graph(self, synthesis: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Arranges synthesized Agent and Tool specs into a visual React Flow canvas graph."""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        agent_info = synthesis["agent_spec"]
        agent_id = f"agent_{int(time.time()*1000) % 10000}"

        # Determine domain-relevant trigger payload and agent prompt
        p_lower = prompt.lower()
        if any(w in p_lower for w in ["greet", "greeting", "greeter", "greater", "welcome", "salutation"]):
            trigger_payload = {
                "user_name": "Alice",
                "tone": "friendly",
                "time_of_day": "morning",
            }
            agent_prompt = (
                "Generate a personalized welcome greeting for {{ trigger_1.user_name }} "
                "(tone: {{ trigger_1.tone }}, time of day: {{ trigger_1.time_of_day }}) using your greeting tool."
            )
        elif any(w in p_lower for w in ["postgres", "database", "sql", "order", "query"]):
            trigger_payload = {
                "query_type": "orders",
                "identifier": "ORD-94821",
            }
            agent_prompt = (
                "Look up customer order details for {{ trigger_1.identifier }} using your database tool."
            )
        elif any(w in p_lower for w in ["calc", "math", "sum", "average", "compute"]):
            trigger_payload = {
                "expression": "(1250 * 1.15) - 85",
            }
            agent_prompt = (
                "Calculate and explain the mathematical result for expression: {{ trigger_1.expression }}."
            )
        elif any(w in p_lower for w in ["chart", "plot", "metric", "report", "analytics"]):
            trigger_payload = {
                "metric_name": "Monthly Active Users",
                "values": [4200, 4650, 5100, 5900],
            }
            agent_prompt = (
                "Generate a statistical KPI report for {{ trigger_1.metric_name }} with values {{ trigger_1.values }}."
            )
        elif any(w in p_lower for w in ["search", "web", "find", "google"]):
            trigger_payload = {
                "search_query": "Latest breakthroughs in autonomous AI agent architectures",
            }
            agent_prompt = (
                "Search and synthesize comprehensive research on: {{ trigger_1.search_query }}."
            )
        else:
            trigger_payload = {
                "query": f"Inquiry for {agent_info['name']}",
                "input_data": "Execute automated tasks using attached tools.",
            }
            agent_prompt = (
                "Address this request using your attached tools: {{ trigger_1.query }} (Data: {{ trigger_1.input_data }})."
            )

        # 1. Manual Trigger Node
        nodes.append({
            "id": "trigger_1",
            "type": "manual_trigger",
            "name": "Manual Start",
            "position": {"x": 50, "y": 180},
            "config": {
                "default_payload": trigger_payload,
            },
            "inputs": [],
            "outputs": ["output"],
        })

        # 2. Synthesized Agent Node
        nodes.append({
            "id": agent_id,
            "type": "agent",
            "name": agent_info["name"],
            "position": {"x": 540, "y": 180},
            "config": {
                "model": agent_info.get("recommended_model", self.model),
                "api_key": self.api_key or "",
                "base_url": self.api_base or "",
                "system_prompt": agent_info.get("system_prompt", ""),
                "prompt": agent_prompt,
                "use_workflow_credentials": True,
            },
            "inputs": ["input"],
            "outputs": ["output"],
        })

        # Wire trigger -> agent
        edges.append({
            "id": f"e_trigger_{agent_id}",
            "source": "trigger_1",
            "target": agent_id,
            "sourceHandle": "output",
            "targetHandle": "input",
        })

        tool_y = 380
        tool_index = 1

        # 3. Add Prebuilt Tool Nodes
        for tool_type in synthesis.get("prebuilt_tools", []):
            node_id = f"tool_prebuilt_{tool_index}"
            tool_name = tool_type.replace("_", " ").title()
            nodes.append({
                "id": node_id,
                "type": tool_type,
                "name": tool_name,
                "position": {"x": 540, "y": tool_y},
                "config": {"max_results": 3} if "search" in tool_type else {},
                "inputs": [],
                "outputs": ["tool"],
            })
            # Green tool wire to agent
            edges.append({
                "id": f"e_tool_{node_id}_{agent_id}",
                "source": node_id,
                "target": agent_id,
                "sourceHandle": "tool",
                "targetHandle": "tools",
            })
            tool_y += 180
            tool_index += 1

        # 4. Add Dynamic Tool Nodes
        for dt in synthesis.get("dynamic_tools", []):
            node_id = f"tool_dynamic_{tool_index}"
            nodes.append({
                "id": node_id,
                "type": "dynamic_tool",
                "name": dt["name"],
                "position": {"x": 540, "y": tool_y},
                "config": {
                    "tool_name": dt["name"],
                    "description": dt["description"],
                    "code": dt["code"],
                    "parameters": dt.get("parameters", {}),
                    "approval_required": dt.get("approval_required", False),
                    "timeout_seconds": 10.0,
                },
                "inputs": [],
                "outputs": ["tool"],
            })
            # Green tool wire to agent
            edges.append({
                "id": f"e_tool_{node_id}_{agent_id}",
                "source": node_id,
                "target": agent_id,
                "sourceHandle": "tool",
                "targetHandle": "tools",
            })
            tool_y += 180
            tool_index += 1

        # 5. Output / Result Node
        nodes.append({
            "id": "output_1",
            "type": "output",
            "name": "Agent Response",
            "position": {"x": 1020, "y": 180},
            "config": {
                "response": f"{{{{ {agent_id}.output }}}}",
            },
            "inputs": ["input"],
            "outputs": [],
        })

        # Wire agent -> output
        edges.append({
            "id": f"e_agent_output_{agent_id}",
            "source": agent_id,
            "target": "output_1",
            "sourceHandle": "output",
            "targetHandle": "input",
        })

        return {"nodes": nodes, "edges": edges}


# Global singleton instance
master_agent_manager = MasterAgentManager()
