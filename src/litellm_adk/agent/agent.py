"""Primary Agent orchestrator coordinating modular specialized components."""

import asyncio
import inspect
import os
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, Set, Type, Union
import uuid
from pydantic import BaseModel
import yaml

from ..config.settings import settings
from ..context.manager import ContextManager
from ..context.policy import ContextPolicy
from ..events.bus import EventBus
from ..events.types import Event, HumanApprovalRequired, TextDelta, ToolCallCompleted, ToolCallStarted
from ..human.approval import ApprovalManager, InMemoryApprovalManager
from ..human.base import HumanInTheLoop
from ..memory.base import BaseMemory
from ..memory.conversation import ConversationMemory
from ..memory.in_memory import InMemoryMemory
from ..memory.long_term import LongTermMemory
from ..memory.working import WorkingMemory
from ..middleware.base import Middleware, MiddlewarePipeline
from ..middleware.logging import LoggingMiddleware
from ..middleware.security import PIIScrubbingMiddleware
from ..models.base import Model
from ..models.config import ModelConfig
from ..models.litellm import LiteLLMModel
from ..observability.logger import adk_logger
from ..session.session import Session
from ..tools.base import Tool
from ..tools.executor import ToolExecutor
from ..tools.permissions import ToolPermission
from ..tools.registry import ToolRegistry, tool_registry
from ..vector.base import VectorStore
from ..vector.retriever import RetrievalConfig, Retriever
from .config import AgentConfig, ExecutionConfig
from .loop import AgentLoop
from .result import AgentResult


class AgentStream:
    """Stream wrapper providing both asynchronous (`async for`) and synchronous (`for`) iteration."""

    def __init__(self, async_generator_func: Callable[[], AsyncIterator[Any]]):
        self._generator_func = async_generator_func

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._generator_func()

    def __iter__(self) -> Iterator[Any]:
        import queue
        import threading

        q: queue.Queue = queue.Queue(maxsize=100)
        sentinel = object()

        def _worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def _run():
                try:
                    async for item in self._generator_func():
                        q.put(item)
                except Exception as ex:
                    q.put(ex)
                finally:
                    q.put(sentinel)
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        while True:
            item = q.get()
            if item is sentinel:
                break
            if isinstance(item, Exception):
                raise item
            yield item


class Agent:
    """Production Agent framework orchestrating independent specialized components."""

    def __init__(
        self,
        name: str = "Assistant",
        description: str = "A helpful AI assistant.",
        model: Optional[Union[str, ModelConfig, Model]] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        system_prompt: Union[str, Callable[[Any], str]] = "You are a helpful assistant.",
        developer_prompt: Optional[str] = None,
        instructions: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        memory: Optional[BaseMemory] = None,
        vector_store: Optional[VectorStore] = None,
        retriever: Optional[Retriever] = None,
        human_in_the_loop: Optional[HumanInTheLoop] = None,
        context_manager: Optional[ContextManager] = None,
        event_bus: Optional[EventBus] = None,
        middleware: Optional[Union[List[Middleware], MiddlewarePipeline]] = None,
        execution_config: Optional[ExecutionConfig] = None,
        max_context_tokens: Optional[int] = None,
        fallbacks: Optional[List[Union[str, Dict[str, Any]]]] = None,
        sub_agents: Optional[Union[List[Any], Dict[str, Any]]] = None,
        approval_manager: Optional[Any] = None,
        scrub_pii: bool = False,
        use_global_tools: bool = False,
        response_model: Optional[Type[BaseModel]] = None,
        vision_cache: Optional[Any] = None,
        config: Optional[AgentConfig] = None,
        policy_engine: Optional[Any] = None,
        **kwargs: Any,
    ):
        # 1. Resolve configuration
        if config:
            name = config.name
            description = config.description
            model = config.model or model
            api_key = config.api_key or api_key
            base_url = config.base_url or base_url
            system_prompt = config.system_prompt or system_prompt
            developer_prompt = config.developer_prompt or developer_prompt
            instructions = config.instructions or instructions
            tools = config.tools or tools
            max_context_tokens = config.max_context_tokens or max_context_tokens
            fallbacks = config.fallbacks or fallbacks
            sub_agents = config.sub_agents or sub_agents
            scrub_pii = config.scrub_pii or scrub_pii
            use_global_tools = config.use_global_tools or use_global_tools
            execution_config = config.execution or execution_config
            kwargs.update(config.extra_kwargs)

        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.developer_prompt = developer_prompt
        self.instructions = instructions
        self.response_model = response_model
        self.vision_cache = vision_cache
        self.sub_agents: Dict[str, Any] = {}
        self.api_key = api_key or settings.api_key
        self.base_url = base_url or settings.base_url
        self.policy_engine = policy_engine or kwargs.get("policy_engine")
        self.scrub_pii = scrub_pii

        # 2. Model gateway initialization
        resolved_model_name = model or settings.model or "gpt-4o"
        if hasattr(resolved_model_name, "generate") or isinstance(resolved_model_name, Model):
            self.model: Model = resolved_model_name
        elif isinstance(resolved_model_name, ModelConfig):
            self.model = LiteLLMModel(resolved_model_name)
        else:
            model_cfg = ModelConfig(
                model=str(resolved_model_name),
                api_key=api_key or settings.api_key,
                api_base=base_url or settings.base_url,
                fallbacks=fallbacks,
                extra_kwargs=kwargs,
            )
            self.model = LiteLLMModel(model_cfg)

        # 3. Memory systems
        self.conversation_memory = ConversationMemory(backend=memory or InMemoryMemory())
        self.working_memory = WorkingMemory()
        self.long_term_memory = LongTermMemory()

        # 4. Context management
        resolved_context_tokens = max_context_tokens or getattr(settings, "max_context_tokens", None)
        ctx_policy = ContextPolicy(max_tokens=resolved_context_tokens)
        self.context_manager = context_manager or ContextManager(policy=ctx_policy)

        # 5. Tool registry & executor
        self.tool_registry = ToolRegistry()
        if use_global_tools:
            for t_name, t_obj in tool_registry._tools.items():
                self.tool_registry.register_tool(t_obj)

        if tools:
            self._register_provided_tools(tools)

        self.tool_executor = ToolExecutor(registry=self.tool_registry)

        # 6. Vector store & Retrieval
        self.vector_store = vector_store
        if retriever:
            self.retriever = retriever
        elif vector_store:
            self.retriever = Retriever(vector_store=vector_store)
        else:
            self.retriever = None

        # 7. Human in the loop
        if human_in_the_loop:
            self.human_in_the_loop = human_in_the_loop
        elif approval_manager:
            self.human_in_the_loop = approval_manager
        else:
            self.human_in_the_loop = InMemoryApprovalManager()

        # 8. Event bus
        self.event_bus = event_bus or EventBus()

        # 9. Middleware pipeline
        if isinstance(middleware, MiddlewarePipeline):
            self.middleware = middleware
        else:
            self.middleware = MiddlewarePipeline(middlewares=list(middleware or []))

        # Add default middlewares if requested
        if scrub_pii:
            self.middleware.add(PIIScrubbingMiddleware())

        # 10. Execution loop
        self.loop = AgentLoop(
            model=self.model,
            tool_executor=self.tool_executor,
            context_manager=self.context_manager,
            event_bus=self.event_bus,
            middleware=self.middleware,
            execution_config=execution_config or ExecutionConfig(),
            human_in_the_loop=self.human_in_the_loop,
            agent=self,
        )

        # 11. Register sub-agents
        if sub_agents:
            self._register_subagents(sub_agents)

    def _register_provided_tools(self, tools: List[Any]) -> None:
        """Resolves tool references (functions, names, tool objects, dictionaries)."""
        for item in tools:
            if isinstance(item, Tool):
                self.tool_registry.register_tool(item)
            elif isinstance(item, str):
                # Look up in global registry
                found = tool_registry.get_tool(item)
                if found:
                    self.tool_registry.register_tool(found)
                else:
                    adk_logger.warning(f"Tool named '{item}' not found in global registry.")
            elif callable(item):
                self.tool_registry.register(item)
            elif isinstance(item, dict):
                fn = item.get("function", item)
                t_name = fn.get("name", "custom_tool")
                t_desc = fn.get("description", "")
                t_params = fn.get("parameters", {})
                dummy_tool = Tool(
                    func=lambda **kw: "Tool executed",
                    name=t_name,
                    description=t_desc,
                    parameters=t_params,
                )
                self.tool_registry.register_tool(dummy_tool)

    def _register_subagents(self, sub_agents: Union[List[Any], Dict[str, Any]]) -> None:
        """Registers subagents and wraps them as tools for this agent."""
        sub_list = sub_agents.values() if isinstance(sub_agents, dict) else sub_agents
        for sa in sub_list:
            if isinstance(sa, Agent):
                agent_instance = sa
            elif isinstance(sa, AgentConfig):
                agent_instance = Agent(config=sa)
            elif isinstance(sa, dict):
                agent_instance = Agent(config=AgentConfig(**sa))
            else:
                agent_instance = sa

            sa_name = getattr(agent_instance, "name", str(uuid.uuid4()))
            self.sub_agents[sa_name] = agent_instance

    @property
    def tools(self) -> List[Dict[str, Any]]:
        """Returns OpenAPI definitions of all tools available to this agent."""
        return self.tool_registry.get_tool_definitions()

    @property
    def model_name(self) -> str:
        return self.model.model_name

    # Compatibility property for tests checking agent.model
    @property
    def model_property(self) -> str:
        return self.model.model_name

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        from unittest.mock import Mock
        if hasattr(self, "model") and not isinstance(self.model, Mock) and hasattr(self.model, "config") and hasattr(self.model.config, name):
            return getattr(self.model.config, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def on(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribes an event handler to agent execution events."""
        self.event_bus.subscribe(event_type, handler)

    def create_session(self, user_id: Optional[str] = None) -> Session:
        """Generates a new session with an isolated identifier."""
        return Session(user_id=user_id, app_name=self.name)

    def save_session(self, session: Union[str, Session]) -> None:
        """Saves session metadata into the conversation memory backend."""
        if isinstance(session, str):
            session = Session(id=session)
        if hasattr(self.conversation_memory, "backend") and hasattr(self.conversation_memory.backend, "save_session_metadata"):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.conversation_memory.backend.save_session_metadata(session.id, session.model_dump()))
                else:
                    loop.run_until_complete(self.conversation_memory.backend.save_session_metadata(session.id, session.model_dump()))
            except Exception as e:
                adk_logger.warning(f"Failed to save session metadata: {e}")

    def approve(self, request_id: str, reviewer: str = "human", reason: Optional[str] = None) -> None:
        """Convenience method to approve a pending HITL request."""
        if hasattr(self.human_in_the_loop, "submit_decision"):
            from ..human.approval import ApprovalStatus
            self.human_in_the_loop.submit_decision(request_id, ApprovalStatus.APPROVED, reviewer=reviewer, reason=reason)

    def reject(self, request_id: str, reviewer: str = "human", reason: Optional[str] = None) -> None:
        """Convenience method to reject a pending HITL request."""
        if hasattr(self.human_in_the_loop, "submit_decision"):
            from ..human.approval import ApprovalStatus
            self.human_in_the_loop.submit_decision(request_id, ApprovalStatus.REJECTED, reviewer=reviewer, reason=reason)

    def modify(self, request_id: str, modified_args: Dict[str, Any], reviewer: str = "human", reason: Optional[str] = None) -> None:
        """Convenience method to modify args and approve a pending HITL request."""
        if hasattr(self.human_in_the_loop, "submit_decision"):
            from ..human.approval import ApprovalStatus
            self.human_in_the_loop.submit_decision(request_id, ApprovalStatus.MODIFIED, reviewer=reviewer, reason=reason, modified_args=modified_args)

    async def _process_images_async(self, images: List[str]) -> List[str]:
        """Asynchronously processes raw image inputs into optimized base64 data URLs."""
        if not images:
            return []
        try:
            from ..utils.vision import VisionOptimizer
            tasks = [VisionOptimizer.process_image(img, cache=getattr(self, "vision_cache", None)) for img in images]
            return await asyncio.gather(*tasks)
        except Exception as e:
            adk_logger.warning(f"Image optimization note: {e}. Falling back to original image sources.")
            return images

    @property
    def approval_manager(self) -> Any:
        """Alias returning the HumanInTheLoop / ApprovalManager instance."""
        return self.human_in_the_loop

    def _should_require_approval(self, name: str, args: Dict[str, Any]) -> bool:
        """Determines if a tool call requires human approval."""
        if hasattr(self, "_custom_should_require_approval"):
            return self._custom_should_require_approval(name, args)
        if getattr(self, "policy_engine", None):
            pe = self.policy_engine
            if hasattr(pe, "evaluate"):
                res = pe.evaluate(name, args)
                return getattr(res, "requires_approval", False)
            if hasattr(pe, "check_approval_required"):
                return pe.check_approval_required(name, args)
        return False

    def _resolve_runtime_tools(self, runtime_tools: Optional[List[Any]]) -> Optional[List[Dict[str, Any]]]:
        """Resolves ad-hoc runtime tool definitions."""
        if not runtime_tools:
            return self.tools or None
        temp_registry = ToolRegistry()
        for t in self.tool_registry.list_tools():
            temp_registry.register_tool(t)
        for item in runtime_tools:
            if isinstance(item, Tool):
                temp_registry.register_tool(item)
            elif callable(item):
                temp_registry.register(item)
            elif isinstance(item, dict):
                fn = item.get("function", item)
                t_name = fn.get("name", "custom_tool")
                t_desc = fn.get("description", "")
                t_params = fn.get("parameters", {})
                dummy_tool = Tool(
                    func=lambda **kw: "Tool executed",
                    name=t_name,
                    description=t_desc,
                    parameters=t_params,
                )
                temp_registry.register_tool(dummy_tool)
        return temp_registry.get_tool_definitions()

    async def run(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session: Optional[Union[str, Session]] = None,
        session_id: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None,
        images: Optional[List[str]] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Asynchronously executes the agent reasoning loop to completion."""
        target_session = session or session_id or kwargs.pop("session_id", None)
        actual_session_id = target_session.id if isinstance(target_session, Session) else (target_session or str(uuid.uuid4()))

        # Optimize/process images if present
        processed_images = None
        if images:
            processed_images = await self._process_images_async(images)

        # Retrieve RAG context if retriever configured
        retrieved_docs = None
        if self.retriever and isinstance(prompt, str):
            retrieved_docs = await self.retriever.retrieve_context(prompt)

        # Retrieve long-term memories
        mem_query = prompt if isinstance(prompt, str) else str(prompt)
        memories = await self.long_term_memory.retrieve_relevant_facts(mem_query)

        # Get existing conversation turns
        history = await self.conversation_memory.get_messages(actual_session_id)

        # Collect tools
        tool_defs = self._resolve_runtime_tools(tools) if tools else (self.tools or None)
        resp_model = response_model or self.response_model

        result = await self.loop.run(
            prompt=prompt,
            session_id=actual_session_id,
            system_prompt=self.system_prompt,
            conversation_history=history,
            images=processed_images,
            developer_prompt=self.developer_prompt,
            working_memory_notes=self.working_memory.get_summary_notes(),
            long_term_memories=memories,
            retrieved_documents=retrieved_docs,
            response_model=resp_model,
            tools=tool_defs,
            agent_name=self.name,
        )

        # Sync back updated messages to conversation memory
        await self.conversation_memory.backend.clear(actual_session_id)
        await self.conversation_memory.backend.add_messages(actual_session_id, history)

        return result

    def run_sync(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session: Optional[Union[str, Session]] = None,
        session_id: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None,
        images: Optional[List[str]] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Synchronously executes the agent reasoning loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        self.run(
                            prompt,
                            session=session,
                            session_id=session_id,
                            response_model=response_model,
                            images=images,
                            tools=tools,
                            **kwargs,
                        )
                    )
                )
                return future.result()
        else:
            return asyncio.run(
                self.run(
                    prompt,
                    session=session,
                    session_id=session_id,
                    response_model=response_model,
                    images=images,
                    tools=tools,
                    **kwargs,
                )
            )

    # Backward compatibility aliases
    def invoke(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session: Optional[Union[str, Session]] = None,
        session_id: Optional[str] = None,
        images: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Backward compatible invocation method executing the agent reasoning loop synchronously."""
        return self.run_sync(
            prompt,
            session=session,
            session_id=session_id,
            response_model=response_model,
            images=images,
            tools=tools,
            **kwargs,
        )

    async def ainvoke(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session: Optional[Union[str, Session]] = None,
        session_id: Optional[str] = None,
        images: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Backward compatible async invocation method."""
        return await self.run(
            prompt,
            session=session,
            session_id=session_id,
            response_model=response_model,
            images=images,
            tools=tools,
            **kwargs,
        )

    def stream(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session: Optional[Union[str, Session]] = None,
        session_id: Optional[str] = None,
        images: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Any]] = None,
        stream_events: bool = False,
        **kwargs: Any,
    ) -> AgentStream:
        """Streams live events emitted during agent execution. Supports both async for and sync for."""
        target_session = session or session_id or kwargs.pop("session_id", None)
        actual_session_id = target_session.id if isinstance(target_session, Session) else (target_session or str(uuid.uuid4()))

        async def _generator() -> AsyncIterator[Union[Event, Dict[str, Any]]]:
            processed_images = None
            if images:
                processed_images = await self._process_images_async(images)

            retrieved_docs = None
            if self.retriever and isinstance(prompt, str):
                retrieved_docs = await self.retriever.retrieve_context(prompt)

            mem_query = prompt if isinstance(prompt, str) else str(prompt)
            memories = await self.long_term_memory.retrieve_relevant_facts(mem_query)
            history = await self.conversation_memory.get_messages(actual_session_id)
            tool_defs = self._resolve_runtime_tools(tools) if tools else (self.tools or None)
            resp_model = response_model or self.response_model

            async for event in self.loop.stream(
                prompt=prompt,
                session_id=actual_session_id,
                system_prompt=self.system_prompt,
                conversation_history=history,
                images=processed_images,
                developer_prompt=self.developer_prompt,
                working_memory_notes=self.working_memory.get_summary_notes(),
                long_term_memories=memories,
                retrieved_documents=retrieved_docs,
                response_model=resp_model,
                tools=tool_defs,
                agent_name=self.name,
            ):
                if stream_events:
                    if isinstance(event, TextDelta):
                        yield {"type": "content", "delta": event.delta}
                    elif isinstance(event, ToolCallStarted):
                        yield {"type": "tool_start", "name": event.tool_name, "arguments": event.arguments}
                    elif isinstance(event, ToolCallCompleted):
                        yield {"type": "tool_end", "name": event.tool_name, "result": event.result}
                    elif isinstance(event, HumanApprovalRequired):
                        yield {
                            "type": "requires_approval",
                            "pending_approvals": [
                                {
                                    "id": event.tool_call_id,
                                    "tool_name": event.tool_name,
                                    "original_args": event.arguments,
                                }
                            ],
                            "session_id": actual_session_id,
                        }
                    elif isinstance(event, dict):
                        yield event
                    else:
                        yield {"type": event.type, **getattr(event, "data", {})}
                else:
                    yield event

        return AgentStream(_generator)

    def astream(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session: Optional[Union[str, Session]] = None,
        session_id: Optional[str] = None,
        images: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Any]] = None,
        stream_events: bool = False,
        **kwargs: Any,
    ) -> AgentStream:
        """Asynchronously streams output tokens or events. Supports both async for and sync for."""
        target_session = session or session_id or kwargs.pop("session_id", None)
        actual_session_id = target_session.id if isinstance(target_session, Session) else (target_session or str(uuid.uuid4()))

        async def _generator() -> AsyncIterator[Union[str, Dict[str, Any], Event]]:
            base_stream = self.stream(
                prompt=prompt,
                session=target_session,
                session_id=actual_session_id,
                images=images,
                response_model=response_model,
                tools=tools,
                stream_events=stream_events,
                **kwargs,
            )
            async for item in base_stream:
                if stream_events:
                    yield item
                else:
                    if isinstance(item, TextDelta):
                        yield item.delta
                    elif isinstance(item, str):
                        yield item
                    elif hasattr(item, "delta"):
                        yield getattr(item, "delta")
                    elif isinstance(item, dict) and "delta" in item:
                        yield item["delta"]

        return AgentStream(_generator)

    async def _aget_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Any:
        """Internal helper for backward compatibility with completion mocks."""
        import litellm
        from ..security import PIIScrubber

        clean_messages = []
        for msg in messages:
            cleaned = {k: v for k, v in msg.items() if k != "token_count"}
            clean_messages.append(cleaned)

        if getattr(self, "scrub_pii", False):
            clean_messages = PIIScrubber.scrub_messages(clean_messages)

        call_kwargs: Dict[str, Any] = {
            "model": str(self.model),
            "messages": clean_messages,
        }
        if tools:
            call_kwargs["tools"] = tools
        call_kwargs.update(kwargs)
        return await litellm.acompletion(**call_kwargs)

    @classmethod
    def from_config(cls, config: AgentConfig, **kwargs: Any) -> "Agent":
        """Instantiates an Agent from an AgentConfig model."""
        return cls(config=config, **kwargs)

    @classmethod
    def from_yaml(cls, yaml_content_or_path: str, **kwargs: Any) -> "Agent":
        """Instantiates an Agent from a YAML string or file path."""
        cfg = AgentConfig.from_yaml(yaml_content_or_path)
        return cls(config=cfg, **kwargs)

    async def aclose(self) -> None:
        """Closes model client connections and memory resources."""
        await self.model.aclose()
        if hasattr(self.conversation_memory, "close"):
            await self.conversation_memory.close()

    async def __aenter__(self) -> "Agent":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()


# Backward compatibility subclass/alias
LiteLLMAgent = Agent
