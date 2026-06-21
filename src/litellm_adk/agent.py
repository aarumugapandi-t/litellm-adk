import uuid
import litellm
import json
import logging
import asyncio
import os
import requests  # type: ignore
import aiohttp
import base64
import mimetypes
from collections import OrderedDict
from types import SimpleNamespace
from typing import List, Dict, Any, Optional, Union, Callable, Generator, AsyncGenerator
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from litellm.exceptions import RateLimitError, APIConnectionError, ServiceUnavailableError, Timeout

from .base import BaseAgent
from .observability.logger import adk_logger
from .observability.telemetry import trace_span
from .config.settings import settings
from .session import Session
from .tools.registry import tool_registry
from .memory import BaseMemory, InMemoryMemory
from .memory.vector_store import VectorStore
from .context import ContextManager
from .approval import ApprovalManager
from .models import ApprovalStatus, ApprovalRequest, AgentResponse, UsageInfo
from .policy import PolicyEngine
from .handoff import HandoffAgent, HandoffResult
from .utils.vision import VisionOptimizer, BaseVisionCache, SQLiteVisionCache

# Global LiteLLM configuration for resilience
litellm.drop_params = True

class LiteLLMAgent(BaseAgent):
    """
    Multiservice agent supporting dynamic overrides for base_url and api_key.
    """

    async def aclose(self):
        """
        Properly close all global litellm async clients and agent resources.
        This provides a structural resolution to the 'coroutine never awaited' 
        warning often seen on Windows at script exit.
        """
        # 1. Close instance resources
        if getattr(self, "vector_store", None) and hasattr(self.vector_store, "close"):
            try:
                # Check if it's async or sync close
                if asyncio.iscoroutinefunction(self.vector_store.close):
                    await self.vector_store.close()
                else:
                    self.vector_store.close()
                adk_logger.debug("Closed vector_store connection.")
            except Exception as e:
                adk_logger.warning(f"Error closing vector_store: {e}")

        # 2. Close memory resources if applicable
        if getattr(self, "memory", None) and hasattr(self.memory, "close"):
             try:
                if asyncio.iscoroutinefunction(self.memory.close):
                    await self.memory.close()
                else:
                    self.memory.close()
             except Exception:
                 pass

        try:
            # 3. Global LiteLLM Cleanup (Aggressively close any cached clients)
            if hasattr(litellm, "in_memory_llm_clients_cache"):
                cache = litellm.in_memory_llm_clients_cache
                if hasattr(cache, "cache_dict"):
                    for key, client in list(cache.cache_dict.items()):
                        try:
                            if hasattr(client, "aclose"):
                                await client.aclose()
                            elif hasattr(client, "close"):
                                if asyncio.iscoroutinefunction(client.close):
                                    await client.close()
                                else:
                                    client.close()
                        except Exception:
                            pass
                    # Clear the cache so we don't try again or leave refs
                    cache.cache_dict.clear()
            
            # 4. Call official cleanup
            await litellm.close_litellm_async_clients()
            
            # 5. Windows/aiohttp fix: Give time for underlying connections to close
            await asyncio.sleep(0.250)

            # 4. Structural Resolution: Patch litellm's cleanup to be a no-op 
            # This prevents its internal atexit handler from creating un-awaited coroutines
            try:
                import litellm.llms.custom_httpx.async_client_cleanup as cleanup_mod
                
                # We return a completed future so that run_until_complete(close_...) still works
                # but doesn't actually start any new async work or leave coroutines hanging.
                def sync_noop(*args, **kwargs):
                    f = asyncio.Future()
                    f.set_result(None)
                    return f
                
                cleanup_mod.close_litellm_async_clients = sync_noop
            except ImportError:
                pass
            
            adk_logger.debug("Global LiteLLM async clients closed and cache cleared.")
        except Exception as e:
            adk_logger.debug(f"Error during LiteLLM cleanup: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    def __init__(
        self,
        name: str = "Assistant",
        description: str = "A helpful AI assistant.",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        tools: Optional[List[Dict[str, Any]]] = None,
        memory: Optional[BaseMemory] = None,
        max_context_tokens: Optional[int] = None,
        fallbacks: Optional[List[Union[str, Dict[str, Any]]]] = None,
        vector_store: Optional['VectorStore'] = None,
        sub_agents: Optional[List['LiteLLMAgent']] = None,
        handoff_context: str = "clean",
        handoff_memory: str = "ephemeral",
        use_global_tools: bool = False,
        approval_manager: Optional[Any] = None,
        vision_cache: Optional[BaseVisionCache] = None,
        **kwargs
    ):
        self.name = name
        self.description = description
        self.model = model or settings.model
        self.api_key = api_key or settings.api_key
        self.base_url = base_url or settings.base_url
        
        # Automatically prepend 'openai/' if a base_url is used to force proxy/OpenAI-compatible routing
        if self.base_url and not self.model.startswith("openai/"):
            adk_logger.debug(f"Custom base_url detected. Prepending 'openai/' to model {self.model}")
            self.model = f"openai/{self.model}"
            
        self.system_prompt = system_prompt
        self.sub_agents = {agent.name: agent for agent in (sub_agents or [])}
        
        # Handoff context strategy:
        #   "clean"     - sub-agent receives only the last user message (safe, provider-agnostic)
        #   "user_only" - sub-agent receives all user turns from parent history (no assistant/tool msgs)
        #   "full"      - sub-agent receives full parent history (most context, strict-provider risk)
        if handoff_context not in ("clean", "user_only", "full"):
            raise ValueError(f"Invalid handoff_context '{handoff_context}'. Must be 'clean', 'user_only', or 'full'.")
        self.handoff_context = handoff_context
        
        # Whether sub-agent work is persisted to sub-agent's memory on handoff:
        #   "ephemeral" - sub-agent does NOT write to its memory during handoff (default, safest)
        #   "persist"   - sub-agent writes exchange to its own memory under an isolated session UUID
        if handoff_memory not in ("ephemeral", "persist"):
            raise ValueError(f"Invalid handoff_memory '{handoff_memory}'. Must be 'ephemeral' or 'persist'.")
        self.handoff_memory = handoff_memory
        
        # Smart Tool Resolution
        if tools is None:
            # Only use global registry if explicitly requested
            self.tools = tool_registry.get_tool_definitions() if use_global_tools else []
        else:
            # Process provided list (can be definitions OR functions)
            processed_tools = []
            for t in tools:
                if callable(t):
                    # It's a function, register it (if not already) and get definition
                    processed_tools.append(tool_registry._register_function(t))
                elif isinstance(t, dict):
                     processed_tools.append(t)
            self.tools = processed_tools
            
        # Dynamically inject transfer tools for sub_agents
        for agent_name, sub_agent in self.sub_agents.items():
            transfer_tool = {
                "type": "function",
                "function": {
                    "name": f"transfer_to_{agent_name}",
                    "description": f"Transfer control to {agent_name}. {sub_agent.description} Use this when the user's request should be handled by this specialist.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instructions": {
                                "type": "string",
                                "description": "Optional context or task instructions to pass to the sub-agent."
                            }
                        },
                        "required": []
                    }
                }
            }
            # Only add if a tool with this name doesn't already exist
            if not any(t.get("function", {}).get("name") == f"transfer_to_{agent_name}" for t in self.tools):
                self.tools.append(transfer_tool)
        
        # Initialize BaseAgent (Model, Memory, VectorStore)
        resolved_memory = memory or InMemoryMemory()
        super().__init__(
            model=self.model,
            system_prompt=system_prompt,
            memory=resolved_memory,
            vector_store=vector_store
        )
        
        self.max_context_tokens = max_context_tokens
        
        # Set up pluggable stores (defaulting to SQLite for process-safety)
        self.approval_manager = approval_manager or ApprovalManager()
        self.vision_cache = vision_cache or SQLiteVisionCache()
        
        self.policy_engine = PolicyEngine()
        
        # Setup Fallbacks
        self.fallbacks = fallbacks or []
        
        adk_logger.info(f"Agent initialized with model: {self.model}")
        
        # LRU Cache for Vector Retrieval
        self._context_cache: OrderedDict[str, str] = OrderedDict()
        self._max_cache_size = kwargs.pop("vector_cache_size", 50)
        self.vector_search_threshold = kwargs.pop("vector_search_threshold", None)
        self._max_cache_size = kwargs.pop("vector_cache_size", 50)
        
        # Determine tool execution mode (defaulting to Parallel if not specified)
        parallel_tools = kwargs.pop("parallel_tool_calls", None)
        if parallel_tools is not None:
             self.sequential_tool_execution = not parallel_tools
        else:
             self.sequential_tool_execution = kwargs.pop("sequential_tool_execution", settings.sequential_execution)

        self.extra_kwargs = kwargs
        
        if "parallel_tool_calls" not in self.extra_kwargs:
            self.extra_kwargs["parallel_tool_calls"] = True
            
        # Memory Persistence
        self.memory: BaseMemory = memory or resolved_memory
        self.max_context_tokens = max_context_tokens
        
        # Process fallbacks: ensure they are standardized
        self.fallbacks = []
        if fallbacks:
            for f in fallbacks:
                config = {"model": f} if isinstance(f, str) else f.copy()
                
                # Apply model prefixing to fallbacks if using custom base_url (and fallback doesn't override it)
                target_base_url = config.get("base_url", self.base_url)
                if target_base_url and not config["model"].startswith("openai/"):
                    config["model"] = f"openai/{config['model']}"
                    
                self.fallbacks.append(config)
        
        adk_logger.debug(f"Initialized LiteLLMAgent as a service for model={self.model}")

    def save_session(self, session: Union[str, Session]):
        """Persist session metadata and state to memory."""
        actual_id = session.id if isinstance(session, Session) else session
        
        # If it's a Session object, we dump the full metadata
        if isinstance(session, Session):
            asyncio.run(self.memory.save_session_metadata(actual_id, session.model_dump()))
        # If it's just an ID, there's nothing to dump from the service layer

    # --- HITL Convenience Methods ---
    def approve(self, request_id: str, reviewer: str = "human", reason: Optional[str] = None):
        """Approve a pending tool call."""
        self.approval_manager.submit_decision(request_id, ApprovalStatus.APPROVED, reviewer, reason)

    def reject(self, request_id: str, reviewer: str = "human", reason: Optional[str] = None):
        """Reject a pending tool call."""
        self.approval_manager.submit_decision(request_id, ApprovalStatus.REJECTED, reviewer, reason)

    def modify(self, request_id: str, modified_args: Dict[str, Any], reviewer: str = "human", reason: Optional[str] = None):
        """Provide modified arguments and approve the tool call."""
        self.approval_manager.submit_decision(request_id, ApprovalStatus.MODIFIED, reviewer, reason, modified_args)

    async def _retrieve_context(self, prompt: str) -> Optional[str]:
        """Async semantic search for relevant context with LRU Caching."""
        if not self.vector_store or not prompt:
            return None
        
        # 1. Check Cache
        if prompt in self._context_cache:
            adk_logger.debug(f"Cache hit for vector context: {prompt[:30]}...")
            self._context_cache.move_to_end(prompt)
            return self._context_cache[prompt]
            
        try:
            results = await self.vector_store.search(prompt, k=3, score_threshold=self.vector_search_threshold)
            if not results:
                return None
            
            adk_logger.info(f"Retrieved {len(results)} chunks for context:")
            for i, r in enumerate(results):
                content = r.get('text', '')
                preview = content[:200] + "..." if len(content) > 200 else content
                adk_logger.info(f"Chunk {i+1}: {preview}")
            
            context_block = "\n".join([f"- {r['text']}" for r in results])
            result_str = f"Relevant Context from Memory:\n{context_block}"
            
            # 2. Update Cache
            self._context_cache[prompt] = result_str
            self._context_cache.move_to_end(prompt)
            if len(self._context_cache) > self._max_cache_size:
                self._context_cache.popitem(last=False)
                
            return result_str
        except Exception as e:
            adk_logger.warning(f"Vector retrieval failed: {e}")
            return None

    def _retrieve_context_sync(self, prompt: str) -> Optional[str]:
        """Synchronous wrapper for vector context retrieval."""
        if not self.vector_store or not prompt:
            return None
        
        # Check cache first (sync)
        if prompt in self._context_cache:
            self._context_cache.move_to_end(prompt)
            return self._context_cache[prompt]

        try:
            # Run the async search in a sync context
            # NOTE: asyncio.run creates a NEW event loop. Safe for standalone scripts using .invoke()
            return asyncio.run(self._retrieve_context(prompt))
        except Exception as e:
            adk_logger.warning(f"Sync vector retrieval failed: {e}")
            return None


    async def _aauto_process_images(self, images: List[str]) -> List[str]:
        """
        Asynchronously processes raw image inputs into optimized data URLs.
        """
        async with aiohttp.ClientSession() as session:
            tasks = [VisionOptimizer.process_image(img, session, self.vision_cache) for img in images]
            return await asyncio.gather(*tasks)

    def _auto_process_images(self, images: List[str]) -> List[str]:
        """
        Processes a list of raw image inputs (local paths or URLs) into optimized data URLs.
        """
        try:
            return asyncio.run(self._aauto_process_images(images))
        except Exception as e:
            adk_logger.warning(f"Sync image processing failed: {e}")
            return images

    @trace_span("agent.prepare_messages")
    def _prepare_messages(self, prompt: str, actual_session_id: str, images: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Build the message list for an LLM call from persistent memory."""
        try:
            # Sync wrapper for async memory retrieval
            history = asyncio.run(self.memory.get_messages(actual_session_id))
        except Exception as e:
            adk_logger.warning(f"Sync memory retrieval failed: {e}")
            history = []

        is_new_session = not history
        if is_new_session:
            history = [{"role": "system", "content": self.system_prompt}]
        messages = history.copy()
        
        if prompt or images:
            if images:
                content = []
                if prompt:
                    content.append({"type": "text", "text": prompt})
                
                # Automatically process images for "comfort" (files + URLs + MIME fixing)
                processed_images = self._auto_process_images(images)
                for img_data in processed_images:
                    content.append({"type": "image_url", "image_url": {"url": img_data}})  # type: ignore
                user_msg = {"role": "user", "content": content}
            else:
                user_msg = {"role": "user", "content": prompt}
            
            messages.append(user_msg)
            
            # Persistent Storage for User Message
            current_user_msg = self._sanitize_message(user_msg)
            current_user_msg["token_count"] = ContextManager.count_tokens([current_user_msg], self.model)
            if is_new_session:
                system_msg = self._sanitize_message(messages[0])
                system_msg["token_count"] = ContextManager.count_tokens([system_msg], self.model)
                try:
                    asyncio.run(self.memory.add_messages(actual_session_id, [system_msg, current_user_msg]))
                except Exception: pass
            else:
                try:
                    asyncio.run(self.memory.add_message(actual_session_id, current_user_msg))
                except Exception: pass
        
        # Apply token budget management
        if self.max_context_tokens:
            messages = ContextManager.truncate_history(messages, self.model, self.max_context_tokens)
            
        return messages

    @trace_span("agent.prepare_messages_async")
    async def _aprepare_messages(self, prompt: str, actual_session_id: str, images: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Async version of _prepare_messages to ensure non-blocking image processing and memory access."""
        history = await self.memory.get_messages(actual_session_id)
        is_new_session = not history
        if is_new_session:
            history = [{"role": "system", "content": self.system_prompt}]
        messages = history.copy()
        
        if prompt or images:
            if images:
                content: List[Dict[str, Any]] = []
                if prompt: content.append({"type": "text", "text": prompt})
                processed_images = await self._aauto_process_images(images)
                for img_data in processed_images:
                    content.append({"type": "image_url", "image_url": {"url": img_data}})
                user_msg = {"role": "user", "content": content}
            else:
                user_msg = {"role": "user", "content": prompt}
            
            messages.append(user_msg)
            current_user_msg = self._sanitize_message(user_msg)
            current_user_msg["token_count"] = ContextManager.count_tokens([current_user_msg], self.model)
            if is_new_session:
                system_msg = self._sanitize_message(messages[0])
                system_msg["token_count"] = ContextManager.count_tokens([system_msg], self.model)
                await self.memory.add_messages(actual_session_id, [system_msg, current_user_msg])
            else:
                await self.memory.add_message(actual_session_id, current_user_msg)
        
        if self.max_context_tokens:
            messages = ContextManager.truncate_history(messages, self.model, self.max_context_tokens)
        return messages

    def _build_subagent_messages(
        self,
        parent_messages: List[Dict[str, Any]],
        target_agent: 'LiteLLMAgent',
        instructions: Optional[str]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Build the context message list to pass to a sub-agent during a handoff.
        
        Returns None for 'clean' mode (sub-agent uses its own fresh _prepare_messages).
        Returns a pre-built message list for 'user_only' and 'full' modes.
        """
        sys_msg = {"role": "system", "content": target_agent.system_prompt}
        instr_msg = {
            "role": "system",
            "content": f"Supervisor instructions: {instructions}"
        } if instructions else None
        
        if self.handoff_context == "clean":
            # Sub-agent will use its own _prepare_messages with a fresh session — return None
            return None
        
        elif self.handoff_context == "user_only":
            # Extract all user messages from parent history
            user_msgs = [m for m in parent_messages if m.get("role") == "user"]
            msgs = [sys_msg]
            if instr_msg:
                msgs.append(instr_msg)
            msgs.extend(user_msgs)
            return msgs
        
        elif self.handoff_context == "full":
            # Full parent history, system replaced, trailing tool_calls-only assistant msg dropped
            msgs = list(parent_messages)  # shallow copy
            if msgs and msgs[0].get("role") == "system":
                msgs[0] = sys_msg
            else:
                msgs.insert(0, sys_msg)
            
            # Drop trailing assistant message that was solely used to call the transfer tool
            # (its entire purpose was to trigger the handoff — confuses sub-agent LLM)
            if msgs and msgs[-1].get("role") == "assistant" and "tool_calls" in msgs[-1]:
                msgs = msgs[:-1]
            
            if instr_msg:
                msgs.append(instr_msg)
            return msgs
        
        return None  # Fallback

    def _dispatch_to_subagent(
        self,
        target_agent: 'LiteLLMAgent',
        parent_messages: List[Dict[str, Any]],
        instructions: Optional[str],
        tool_call_id: str,
        session_id: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Synchronously dispatch a handoff to a sub-agent and return a tool result dict.
        """
        override_messages = self._build_subagent_messages(parent_messages, target_agent, instructions)
        last_user_msg = next((m["content"] for m in reversed(parent_messages) if m.get("role") == "user"), "Please handle the user's request.")
        task_prompt = instructions or last_user_msg
        
        sub_session_id = str(uuid.uuid4())
        persist = (self.handoff_memory == "persist")
        
        if override_messages is None:
            adk_logger.info(f"[Handoff:clean] → {target_agent.name}")
            sub_response = target_agent.invoke(task_prompt, session_id=sub_session_id, _persist_history=persist, **kwargs)
        else:
            adk_logger.info(f"[Handoff:{self.handoff_context}] → {target_agent.name}")
            sub_response = target_agent.invoke(
                "",
                session_id=sub_session_id,
                _override_messages=override_messages,
                _persist_history=persist,
                **kwargs
            )
        
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": f"[{target_agent.name}]: {sub_response.content}"
        }

    def _dispatch_to_subagent_sync_streaming(
        self,
        target_agent: 'LiteLLMAgent',
        parent_messages: List[Dict[str, Any]],
        instructions: Optional[str],
        tool_call_id: str,
        session_id: Optional[str],
        stream_events: bool,
        **kwargs
    ):
        """
        Generator for sync streaming handoffs. Uses invoke for sub-agent to avoid nested generators.
        """
        override_messages = self._build_subagent_messages(parent_messages, target_agent, instructions)
        last_user_msg = next((m["content"] for m in reversed(parent_messages) if m.get("role") == "user"), "Please handle the user's request.")
        task_prompt = instructions or last_user_msg

        sub_session_id = str(uuid.uuid4())
        persist = (self.handoff_memory == "persist")
        adk_logger.info(f"[Handoff:{self.handoff_context}] → {target_agent.name} (sync-stream) | prompt='{task_prompt[:60]}'")

        if override_messages is None:
            sub_response = target_agent.invoke(task_prompt, session_id=sub_session_id, _persist_history=persist)
        else:
            sub_response = target_agent.invoke(
                "",
                session_id=sub_session_id,
                _override_messages=override_messages,
                _persist_history=persist
            )

        sub_content = sub_response.content if sub_response.content else ""
        if sub_content:
            if stream_events:
                yield {"type": "content", "delta": sub_content}
            else:
                yield sub_content

        yield {
            "_tool_result": {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"[{target_agent.name}]: {sub_content}"
            }
        }

    async def _adispatch_to_subagent(
        self,
        target_agent: 'LiteLLMAgent',
        parent_messages: List[Dict[str, Any]],
        instructions: Optional[str],
        tool_call_id: str,
        session_id: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Asynchronously dispatch a handoff to a sub-agent and return a tool result dict.
        """
        override_messages = self._build_subagent_messages(parent_messages, target_agent, instructions)
        last_user_msg = next((m["content"] for m in reversed(parent_messages) if m.get("role") == "user"), "Please handle the user's request.")
        task_prompt = instructions or last_user_msg
        
        sub_session_id = str(uuid.uuid4())
        persist = (self.handoff_memory == "persist")
        
        if override_messages is None:
            adk_logger.info(f"[Handoff:clean] → {target_agent.name}")
            sub_response = await target_agent.ainvoke(task_prompt, session_id=sub_session_id, _persist_history=persist, **kwargs)
        else:
            adk_logger.info(f"[Handoff:{self.handoff_context}] → {target_agent.name}")
            sub_response = await target_agent.ainvoke(
                "",
                session_id=sub_session_id,
                _override_messages=override_messages,
                _persist_history=persist,
                **kwargs
            )
        
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": f"[{target_agent.name}]: {sub_response.content}"
        }

    async def _adispatch_to_subagent_streaming(
        self,
        target_agent: 'LiteLLMAgent',
        parent_messages: List[Dict[str, Any]],
        instructions: Optional[str],
        tool_call_id: str,
        session_id: Optional[str],
        stream_events: bool,
        **kwargs
    ):
        """
        Async generator that dispatches a handoff to a sub-agent and streams the result.

        NOTE: Sub-agent is invoked via ainvoke (not astream) to avoid nested async generator
        short-circuit issues. The sub-agent fully executes all its own tools internally,
        then the final response is yielded as a streaming content chunk to the parent.
        This matches industry practice (LangChain, CrewAI, OpenAI Swarm).
        """
        override_messages = self._build_subagent_messages(parent_messages, target_agent, instructions)
        last_user_msg = next((m["content"] for m in reversed(parent_messages) if m.get("role") == "user"), "Please handle the user's request.")
        task_prompt = instructions or last_user_msg

        sub_session_id = str(uuid.uuid4())
        persist = (self.handoff_memory == "persist")
        adk_logger.info(f"[Handoff:{self.handoff_context}] → {target_agent.name} | prompt='{task_prompt[:60]}' | override={override_messages is not None}")

        if override_messages is None:
            sub_response = await target_agent.ainvoke(task_prompt, session_id=sub_session_id, _persist_history=persist)
        else:
            sub_response = await target_agent.ainvoke(
                "",
                session_id=sub_session_id,
                _override_messages=override_messages,
                _persist_history=persist
            )

        sub_content = sub_response.content if sub_response.content else ""

        # Stream the sub-agent's response as a content chunk into the parent stream
        if sub_content:
            if stream_events:
                yield {"type": "content", "delta": sub_content}
            else:
                yield sub_content

        # Sentinel: signals end of sub-agent stream with the tool result
        yield {
            "_tool_result": {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"[{target_agent.name}]: {sub_content}"
            }
        }


    def _update_history(self, new_messages: List[Dict[str, Any]], actual_session_id: str):
        """Persist new messages to memory with token counts."""
        if not new_messages:
            return
            
        sanitized = []
        for m in new_messages:
            s = self._sanitize_message(m)
            if "token_count" not in s:
                s["token_count"] = ContextManager.count_tokens([s], self.model)
            sanitized.append(s)
            
        try:
            asyncio.run(self.memory.add_messages(actual_session_id, sanitized))
        except Exception as e:
            adk_logger.warning(f"Sync history update failed: {e}")

    async def _aupdate_history(self, new_messages: List[Dict[str, Any]], actual_session_id: str):
        """Asynchronously persist new messages to memory."""
        if not new_messages:
            return
            
        sanitized = []
        for m in new_messages:
            s = self._sanitize_message(m)
            if "token_count" not in s:
                s["token_count"] = ContextManager.count_tokens([s], self.model)
            sanitized.append(s)
            
        await self.memory.add_messages(actual_session_id, sanitized)

    def _sanitize_message(self, message: Any) -> Dict[str, Any]:
        """
        Convert LiteLLM message objects to strictly compliant dictionaries.
        Ensures compatibility with strict providers like OCI.
        """
        # If it's already a dict, extract only what we need to avoid 'extra key' errors
        role = getattr(message, "role", "assistant") if not isinstance(message, dict) else message.get("role", "assistant")
        content = getattr(message, "content", "") if not isinstance(message, dict) else message.get("content", "")
        
        # OCI/OpenAI standard: content cannot be None for assistant/user/system
        if content is None:
            content = ""
            
        msg_dict = {
            "role": role,
            "content": content
        }
        
        # Handle Tool Calls (Assistant Message)
        tool_calls = getattr(message, "tool_calls", None) if not isinstance(message, dict) else message.get("tool_calls")
        if tool_calls:
            msg_dict["tool_calls"] = [self._sanitize_tool_call(tc) for tc in tool_calls]
            
        # Handle Tool Result (Tool Role)
        if role == "tool":
            msg_dict["tool_call_id"] = getattr(message, "tool_call_id", None) if not isinstance(message, dict) else message.get("tool_call_id")
            # Cohere and some other strict providers reject "name" in tool responses, although OpenAI recommends it.
            name = getattr(message, "name", None) if not isinstance(message, dict) else message.get("name")
            if name:
                # msg_dict["name"] = name  # We will omit name to be safe across providers.
                pass
                
        return msg_dict

    def _sanitize_tool_call(self, tc: Any) -> Dict[str, Any]:
        """Convert a tool call object to a standard dictionary."""
        if isinstance(tc, dict):
            return tc
            
        tc_dict = {
            "id": getattr(tc, "id", None),
            "type": getattr(tc, "type", "function"),
            "function": {
                "name": None,
                "arguments": ""
            }
        }
        
        func = getattr(tc, "function", None)
        if func:
            tc_dict["function"]["name"] = getattr(func, "name", None)  # type: ignore
            tc_dict["function"]["arguments"] = getattr(func, "arguments", "")  # type: ignore
            
        return tc_dict

    def _should_handle_sequentially(self) -> bool:
        """Determines if we should process tool calls one by one."""
        return self.sequential_tool_execution

    def _should_require_approval(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Centralized check for tool approval requirements."""
        # 1. Check registry flag (can be bool OR predicate)
        from .tools.registry import tool_registry
        registry_meta = tool_registry._tools.get(tool_name, {})
        req = registry_meta.get("requires_approval")
        
        if callable(req):
            if req(arguments): return True
        elif req is True:
            return True
            
        # 2. Check Policy Engine rules
        if self.policy_engine.should_require_approval(tool_name, arguments):
            return True
            
        return False

    @trace_span("agent.execute_tool_async")
    async def _aexecute_tool(self, tool_call) -> Dict[str, Any]:
        """Helper to execute a tool call asynchronously and return formatted result."""
        function_name = self._get_tc_val(tool_call, "function", "name")
        raw_args = self._get_tc_val(tool_call, "function", "arguments") or "{}"
        t_id = self._get_tc_val(tool_call, "id")
        
        arguments = self._parse_arguments(raw_args)
        return await self._aexecute_tool_with_args(function_name, t_id, arguments)

    async def _aexecute_tool_with_args(self, tool_name: str, tool_call_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Core async tool execution logic."""
        # Check Approval Status
        request = self.approval_manager.get_request(tool_call_id)
        is_modified = False
        if request:
            if request.status == ApprovalStatus.REJECTED:
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"Error: Tool call REJECTED by human reviewer. Reason: {request.reason or 'Not specified.'}"
                }
            if request.status == ApprovalStatus.MODIFIED:
                # Use effective args (overridden by human)
                arguments = self.approval_manager.get_effective_args(tool_call_id, default_args=arguments)
                is_modified = True

        if tool_name.startswith("transfer_to_"):
            target_agent = tool_name.replace("transfer_to_", "")
            if target_agent in self.sub_agents:
                adk_logger.info(f"Handing off to sub-agent: {target_agent}")
                raise HandoffAgent(target_agent_name=target_agent, **arguments)
                
        result = await tool_registry.aexecute(tool_name, **arguments)
        content = str(result)
        if is_modified:
            content = f"[HUMAN OVERRIDE: Parameters were modified by a reviewer for safety/compliance] {content}"
            
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }

    def _execute_tool_with_args(self, tool_name: str, tool_call_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Core sync tool execution logic. Returns a standard tool response message."""
        # Check Approval Status
        request = self.approval_manager.get_request(tool_call_id)
        is_modified = False
        if request:
            if request.status == ApprovalStatus.REJECTED:
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"Error: Tool call REJECTED by human reviewer. Reason: {request.reason or 'Not specified.'}"
                }
            if request.status == ApprovalStatus.MODIFIED:
                # Use effective args (overridden by human)
                arguments = self.approval_manager.get_effective_args(tool_call_id, default_args=arguments)
                is_modified = True

        if tool_name.startswith("transfer_to_"):
            target_agent = tool_name.replace("transfer_to_", "")
            if target_agent in self.sub_agents:
                adk_logger.info(f"Handing off to sub-agent: {target_agent}")
                raise HandoffAgent(target_agent_name=target_agent, **arguments)
                
        result = tool_registry.execute(tool_name, **arguments)
        content = str(result)
        if is_modified:
            content = f"[HUMAN OVERRIDE: Parameters were modified by a reviewer for safety/compliance] {content}"

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }

    def _get_tc_val(self, tool_call, attr, subattr=None):
        """Helper to get value from either object or dict tool call."""
        if isinstance(tool_call, dict):
            val = tool_call.get(attr)
            if val and subattr:
                return val.get(subattr)
            return val
        else:
            val = getattr(tool_call, attr, None)
            if val and subattr:
                return getattr(val, subattr, None)
            return val

    def _parse_arguments(self, args: Any) -> Dict[str, Any]:
        """Robustly parses tool arguments."""
        if isinstance(args, dict):
            return args
        try:
            return json.loads(args or "{}")
        except json.JSONDecodeError:
            # RECOVERY: Handle concatenated JSON objects like {"a":1}{"b":2}
            if isinstance(args, str) and "}{" in args:
                try:
                    # Take only the first valid JSON object
                    decoder = json.JSONDecoder()
                    arguments, _ = decoder.raw_decode(args)
                    return arguments
                except Exception:
                    pass
            adk_logger.warning(f"Failed to parse tool arguments: {args}")
            return {}

    @trace_span("agent.execute_tool")
    def _execute_tool(self, tool_call) -> Any:
        """Helper to execute a tool call and handle JSON parsing."""
        function_name = self._get_tc_val(tool_call, "function", "name")
        raw_args = self._get_tc_val(tool_call, "function", "arguments") or "{}"
        
        try:
            if isinstance(raw_args, dict):
                arguments = raw_args
            else:
                # Try standard parsing
                arguments = json.loads(raw_args)
        except json.JSONDecodeError:
            # RECOVERY: Handle concatenated JSON objects like {"a":1}{"b":2}
            if isinstance(raw_args, str) and "}{" in raw_args:
                try:
                    # Take only the first valid JSON object
                    decoder = json.JSONDecoder()
                    arguments, _ = decoder.raw_decode(raw_args)
                except Exception:
                    adk_logger.error(f"Failed to recover tool arguments: {raw_args}")
                    arguments = {}
            else:
                adk_logger.warning(f"Failed to parse tool arguments for {function_name}: {raw_args}")
                arguments = {}
        
        if function_name.startswith("transfer_to_"):
            target_agent = function_name.replace("transfer_to_", "")
            if target_agent in self.sub_agents:
                adk_logger.info(f"Handing off to sub-agent: {target_agent}")
                raise HandoffAgent(target_agent_name=target_agent, **arguments)
                
        return tool_registry.execute(function_name, **arguments)

    @trace_span("agent.completion")
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, ServiceUnavailableError, Timeout)),
        reraise=True
    )
    def _get_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        """Execute a completion call with automatic failover support."""
        configs = [{"model": self.model, "api_key": self.api_key, "base_url": self.base_url}] + self.fallbacks
        
        last_err = None
        for config in configs:
            try:
                model = config.get("model")  # type: ignore
                api_key = config.get("api_key", self.api_key)  # type: ignore
                base_url = config.get("base_url", self.base_url)  # type: ignore
                
                return litellm.completion(
                    model=model,
                    messages=messages,
                    api_key=api_key,
                    base_url=base_url,
                    tools=tools,
                    **{**self.extra_kwargs, **kwargs}
                )
            except Exception as e:
                # Only failover on specific recoverable errors
                recoverable = (
                    "rate_limit" in str(e).lower() or 
                    "timeout" in str(e).lower() or 
                    "service_unavailable" in str(e).lower() or
                    "internal_server_error" in str(e).lower() or
                    isinstance(e, (litellm.RateLimitError, litellm.ServiceUnavailableError, litellm.APIError))
                )
                
                if recoverable and config != configs[-1]:
                    adk_logger.warning(f"Model {model} failed with recoverable error: {e}. Switching to fallback...")
                    last_err = e
                    continue
                raise e
        raise last_err  # type: ignore

    @trace_span("agent.completion_async")
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, ServiceUnavailableError, Timeout)),
        reraise=True
    )
    async def _aget_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        """Execute an async completion call with automatic failover support."""
        configs = [{"model": self.model, "api_key": self.api_key, "base_url": self.base_url}] + self.fallbacks
        
        last_err = None
        for config in configs:
            try:
                model = config.get("model")  # type: ignore
                api_key = config.get("api_key", self.api_key)  # type: ignore
                base_url = config.get("base_url", self.base_url)  # type: ignore
                
                return await litellm.acompletion(
                    model=model,
                    messages=messages,
                    api_key=api_key,
                    base_url=base_url,
                    tools=tools,
                    **{**self.extra_kwargs, **kwargs}
                )
            except Exception as e:
                recoverable = (
                    "rate_limit" in str(e).lower() or 
                    "timeout" in str(e).lower() or 
                    "service_unavailable" in str(e).lower() or
                    "internal_server_error" in str(e).lower() or
                    isinstance(e, (litellm.RateLimitError, litellm.ServiceUnavailableError, litellm.APIError, litellm.BadRequestError))
                )
                
                if recoverable and config != configs[-1]:
                    adk_logger.warning(f"Model {model} failed with recoverable error: {e}. Switching to fallback...")
                    last_err = e
                    continue
                raise e
        raise last_err  # type: ignore

    @trace_span("agent.invoke")
    def invoke(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, session_id: Optional[Union[str, Session]] = None, images: Optional[List[str]] = None, **kwargs) -> Union['AgentResponse', Dict[str, Any]]:
        """
        Execute a synchronous completion with automatic tool calling.
        """
        _persist_history = kwargs.pop("_persist_history", True)
        actual_session_id = session_id.id if isinstance(session_id, Session) else (session_id or str(uuid.uuid4()))
        _override_messages = kwargs.pop("_override_messages", None)
        messages = _override_messages if _override_messages is not None else self._prepare_messages(prompt, actual_session_id=actual_session_id, images=images)
        
        # Inject Vector Context (Sync)
        if prompt and self.vector_store:
            context_str = self._retrieve_context_sync(prompt)
            if context_str:
                messages.insert(1, {"role": "system", "content": context_str})

        tools = tools or self.tools
        new_turns: List[Dict[str, Any]] = [] # Track only what's new in this specific call
        accumulated_content: List[str] = []
        executed_tool_calls: List[Any] = []
        total_usage = UsageInfo()
        
        adk_logger.info(f"Invoking completion for model: {self.model}")
        
        while True:
            # Check for Resume from Approval
            last_msg = messages[-1]
            if not prompt and len(new_turns) == 0 and last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
                adk_logger.info("Resuming from pending tool calls...")
                message = last_msg
                tool_calls_from_llm = last_msg.get("tool_calls", [])
            else:
                response = self._get_completion(messages=messages, tools=tools, **kwargs)
                message = response.choices[0].message
                tool_calls_from_llm = getattr(message, "tool_calls", [])

                # Update usage
                if hasattr(response, "usage"):
                    u = response.usage
                    total_usage.prompt_tokens += u.get("prompt_tokens", 0)
                    total_usage.completion_tokens += u.get("completion_tokens", 0)
                    total_usage.total_tokens += u.get("total_tokens", 0)
                    total_usage.cost += getattr(response, "_response_cost", 0) or 0

            if tool_calls_from_llm:
                pending_requests = []
                for tc in tool_calls_from_llm:
                    t_name = self._get_tc_val(tc, "function", "name")
                    t_id = self._get_tc_val(tc, "id")
                    t_args = self._parse_arguments(self._get_tc_val(tc, "function", "arguments"))
                    
                    # Check if this tool already has a decision in the ApprovalManager
                    request = self.approval_manager.get_request(t_id)
                    
                    if not request:
                        # NEW TOOL CALL: Check if it requires approval
                        if self._should_require_approval(t_name, t_args):
                            request = self.approval_manager.create_request(t_id, actual_session_id, t_name, t_args)
                    
                    if request and request.status == ApprovalStatus.PENDING:
                        pending_requests.append(request)

                if pending_requests:
                    # Atomic Pause: if any tool in batch is pending, pause the whole turn
                    if last_msg != self._sanitize_message(message):
                        sanitized_msg = self._sanitize_message(message)
                        asyncio.run(self.memory.add_message(actual_session_id, sanitized_msg))
                    
                    return {
                        "status": "requires_approval",
                        "pending_approvals": [r.model_dump(mode='json') for r in pending_requests],
                        "session_id": actual_session_id
                    }

                # If we get here, all tools are either safe or have a final decision (APPROVED/REJECTED/MODIFIED)
                tool_calls_to_process = [tool_calls_from_llm[0]] if self._should_handle_sequentially() else tool_calls_from_llm

                if self._should_handle_sequentially():
                    if isinstance(message, dict):
                        message["tool_calls"] = tool_calls_to_process
                    else:
                        message.tool_calls = tool_calls_to_process

                if last_msg != self._sanitize_message(message):
                    sanitized_msg = self._sanitize_message(message)
                    messages.append(sanitized_msg)
                    new_turns.append(sanitized_msg)
                    if sanitized_msg.get("content"):
                         accumulated_content.append(sanitized_msg["content"].strip())
                
                for tool_call in tool_calls_to_process:
                    executed_tool_calls.append(self._sanitize_tool_call(tool_call))
                    t_id = self._get_tc_val(tool_call, "id")

                    try:
                        tool_result = self._execute_tool(tool_call)
                    except HandoffAgent as handoff:
                        target_agent = self.sub_agents[handoff.target_agent_name]
                        tool_result = self._dispatch_to_subagent(
                            target_agent=target_agent,
                            parent_messages=messages,
                            instructions=handoff.kwargs.get("instructions"),
                            tool_call_id=t_id,
                            session_id=actual_session_id,
                            **kwargs
                        )
                    
                    messages.append(tool_result)
                    new_turns.append(tool_result)
                continue
            
            final_msg = self._sanitize_message(message)
            messages.append(final_msg)
            new_turns.append(final_msg)
            if final_msg.get("content"):
                 accumulated_content.append(final_msg["content"].strip())
            
            if _persist_history:
                self._update_history(new_turns, actual_session_id=actual_session_id)
            
            return AgentResponse(
                content=final_msg.get("content") or "",
                accumulated_content="\n".join(accumulated_content),
                tool_calls=executed_tool_calls,
                session_id=actual_session_id,
                usage=total_usage
            )

    @trace_span("agent.invoke_async")
    async def ainvoke(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, session_id: Optional[Union[str, Session]] = None, images: Optional[List[str]] = None, **kwargs) -> Union['AgentResponse', Dict[str, Any]]:
        """
        Execute an asynchronous completion with automatic tool calling.
        """
        _persist_history = kwargs.pop("_persist_history", True)
        actual_session_id = session_id.id if isinstance(session_id, Session) else (session_id or str(uuid.uuid4()))
        _override_messages = kwargs.pop("_override_messages", None)
        messages = _override_messages if _override_messages is not None else await self._aprepare_messages(prompt, actual_session_id=actual_session_id, images=images)
        
        # Inject Vector Context (Async)
        if prompt and self.vector_store:
            context_str = await self._retrieve_context(prompt)
            if context_str:
                messages.insert(1, {"role": "system", "content": context_str})

        tools = tools or self.tools
        new_turns = []  # type: ignore
        accumulated_content = []
        executed_tool_calls = []  # type: ignore
        total_usage = UsageInfo()
        
        adk_logger.info(f"Invoking async completion for model: {self.model}")
        
        while True:
            # RESUME LOGIC
            last_msg = messages[-1]
            if not prompt and len(new_turns) == 0 and last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
                adk_logger.info("Resuming from pending tool calls (async)...")
                message = last_msg
                tool_calls_from_llm = last_msg.get("tool_calls", [])
            else:
                response = await self._aget_completion(messages=messages, tools=tools, **kwargs)
                message = response.choices[0].message
                tool_calls_from_llm = getattr(message, "tool_calls", [])

                # Update usage
                if hasattr(response, "usage"):
                    u = response.usage
                    total_usage.prompt_tokens += u.get("prompt_tokens", 0)
                    total_usage.completion_tokens += u.get("completion_tokens", 0)
                    total_usage.total_tokens += u.get("total_tokens", 0)
                    total_usage.cost += getattr(response, "_response_cost", 0) or 0
            
            if tool_calls_from_llm:
                pending_requests = []
                for tc in tool_calls_from_llm:
                    t_name = self._get_tc_val(tc, "function", "name")
                    t_id = self._get_tc_val(tc, "id")
                    t_args = self._parse_arguments(self._get_tc_val(tc, "function", "arguments"))
                    
                    request = self.approval_manager.get_request(t_id)
                    if not request:
                        if self._should_require_approval(t_name, t_args):
                            request = self.approval_manager.create_request(t_id, actual_session_id, t_name, t_args)
                    
                    if request and request.status == ApprovalStatus.PENDING:
                        pending_requests.append(request)

                if pending_requests:
                    if last_msg != self._sanitize_message(message):
                        sanitized_msg = self._sanitize_message(message)
                        await self.memory.add_message(actual_session_id, sanitized_msg)
                    return {
                        "status": "requires_approval",
                        "pending_approvals": [r.model_dump(mode='json') for r in pending_requests],
                        "session_id": actual_session_id
                    }

                tool_calls_to_process = [tool_calls_from_llm[0]] if self._should_handle_sequentially() else tool_calls_from_llm

                if self._should_handle_sequentially():
                    if isinstance(message, dict):
                        message["tool_calls"] = tool_calls_to_process
                    else:
                        message.tool_calls = tool_calls_to_process

                if last_msg != self._sanitize_message(message):
                    sanitized_msg = self._sanitize_message(message)
                    messages.append(sanitized_msg)
                    new_turns.append(sanitized_msg)
                    if sanitized_msg.get("content"):
                         accumulated_content.append(sanitized_msg["content"].strip())
                
                if self._should_handle_sequentially():
                    for tool_call in tool_calls_to_process:
                        t_id = self._get_tc_val(tool_call, "id")
                        try:
                            result = await self._aexecute_tool(tool_call)
                        except HandoffAgent as handoff:
                            target_agent = self.sub_agents[handoff.target_agent_name]
                            result = await self._adispatch_to_subagent(
                                target_agent=target_agent,
                                parent_messages=messages,
                                instructions=handoff.kwargs.get("instructions"),
                                tool_call_id=t_id,
                                session_id=actual_session_id,
                                **kwargs
                            )

                        messages.append(result)
                        new_turns.append(result)
                else:
                    # Parallel Execution
                    import asyncio

                    async def exec_tool_parallel(tc):
                        t_id_p = self._get_tc_val(tc, "id")
                        try:
                            return await self._aexecute_tool(tc)
                        except HandoffAgent as handoff:
                            target_agent = self.sub_agents[handoff.target_agent_name]
                            return await self._adispatch_to_subagent(
                                target_agent=target_agent,
                                parent_messages=messages,
                                instructions=handoff.kwargs.get("instructions"),
                                tool_call_id=t_id_p,
                                session_id=actual_session_id,
                                **kwargs
                            )

                    parallel_results = await asyncio.gather(*[exec_tool_parallel(tc) for tc in tool_calls_to_process])
                    for res in parallel_results:
                        messages.append(res)
                        new_turns.append(res)
                continue
            
            final_msg = self._sanitize_message(message)
            messages.append(final_msg)
            new_turns.append(final_msg)
            if final_msg.get("content"):
                 accumulated_content.append(final_msg["content"].strip())
            
            if _persist_history:
                await self._aupdate_history(new_turns, actual_session_id=actual_session_id)
            
            return AgentResponse(
                content=final_msg.get("content") or "",
                accumulated_content="\n".join(accumulated_content),
                tool_calls=executed_tool_calls,
                session_id=actual_session_id,
                usage=total_usage
            )
    def stream(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, session_id: Optional[Union[str, Session]] = None, stream_events: bool = False, images: Optional[List[str]] = None, **kwargs) -> Generator[Union[str, Dict[str, Any]], None, None]:
        """
        Execute a streaming completion with automatic tool calling.
        If stream_events=True, yields structured dictionaries instead of strings.
        """
        _persist_history = kwargs.pop("_persist_history", True)
        actual_session_id = session_id.id if isinstance(session_id, Session) else (session_id or str(uuid.uuid4()))
        _override_messages = kwargs.pop("_override_messages", None)
        messages = _override_messages if _override_messages is not None else self._prepare_messages(prompt, actual_session_id=actual_session_id, images=images)

        # Inject Vector Context (Sync)
        if prompt and self.vector_store:
            context_str = self._retrieve_context_sync(prompt)
            if context_str:
                messages.insert(1, {"role": "system", "content": context_str})

        tools = tools or self.tools
        
        new_turns: List[Dict[str, Any]] = []
        
        while True:
            # Check for Resume
            last_msg = messages[-1]
            is_resume = (not prompt and len(new_turns) == 0 and 
                        last_msg.get("role") == "assistant" and 
                        last_msg.get("tool_calls"))
            
            if is_resume:
                adk_logger.info("Resuming from pending tool calls (stream)...")
                tool_calls = last_msg.get("tool_calls", [])
                full_content = last_msg.get("content") or ""
            else:
                response = self._get_completion(messages=messages, tools=tools, stream=True, **kwargs)
                
                # Accumulate tool call parts
                full_content = ""
                tool_calls_by_index: Dict[int, Any] = {} # map of index -> list of SimpleNamespace  # type: ignore
                notified_tools = set()

                for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_content += delta.content
                        if stream_events:
                            yield {"type": "content", "delta": delta.content}
                        else:
                            yield delta.content
                    
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_by_index:
                                tool_calls_by_index[idx] = []
                            
                            last_tc = tool_calls_by_index[idx][-1] if tool_calls_by_index[idx] else None
                            start_new = False
                            if last_tc is None:
                                start_new = True
                            else:
                                if tc_delta.function and tc_delta.function.name and last_tc.function.name:
                                    start_new = True
                                elif tc_delta.id and last_tc.id and tc_delta.id != last_tc.id:
                                    start_new = True
                            
                            if start_new:
                                new_tc = SimpleNamespace(
                                    id=tc_delta.id,
                                    function=SimpleNamespace(
                                        name=tc_delta.function.name if tc_delta.function else None,
                                        arguments=tc_delta.function.arguments if tc_delta.function else ""
                                    )
                                )
                                tool_calls_by_index[idx].append(new_tc)
                            else:
                                if tc_delta.id:
                                    last_tc.id = tc_delta.id  # type: ignore
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        last_tc.function.name = (last_tc.function.name or "") + tc_delta.function.name  # type: ignore
                                    if tc_delta.function.arguments:
                                        if last_tc.function.arguments is None:  # type: ignore
                                            last_tc.function.arguments = ""  # type: ignore
                                        last_tc.function.arguments += tc_delta.function.arguments  # type: ignore
                            
                            # Yield "Thinking" event as soon as name is known
                            current_tc = tool_calls_by_index[idx][-1]
                            if current_tc.function.name and idx not in notified_tools:
                                if stream_events:
                                    yield {"type": "tool_start", "name": current_tc.function.name, "index": idx}
                                notified_tools.add(idx)

                # Build final flat tool calls list
                tool_calls = []
                for idx in sorted(tool_calls_by_index.keys()):
                    for tc_obj in tool_calls_by_index[idx]:
                        if tc_obj.function.name:
                            tool_calls.append({
                                "id": tc_obj.id,
                                "type": "function",
                                "function": {
                                    "name": tc_obj.function.name,
                                    "arguments": tc_obj.function.arguments
                                }
                            })
            if tool_calls:
                # HITL APPROVAL CHECK
                pending_requests = []
                for tc in tool_calls:
                    t_name = self._get_tc_val(tc, "function", "name")
                    t_id = self._get_tc_val(tc, "id")
                    t_args = self._parse_arguments(self._get_tc_val(tc, "function", "arguments"))
                    
                    request = self.approval_manager.get_request(t_id)
                    if not request:
                        if self._should_require_approval(t_name, t_args):
                            request = self.approval_manager.create_request(t_id, actual_session_id, t_name, t_args)
                    
                    if request and request.status == ApprovalStatus.PENDING:
                        pending_requests.append(request)

                if pending_requests:
                    # Persist assistant msg so we can resume later
                    assistant_msg = self._sanitize_message({"role": "assistant", "tool_calls": tool_calls, "content": full_content})
                    if assistant_msg not in messages:
                        messages.append(assistant_msg)
                        new_turns.append(assistant_msg)
                    if _persist_history:
                        self._update_history(new_turns, actual_session_id=actual_session_id)
                    
                    yield {
                        "type": "requires_approval",
                        "pending_approvals": [r.model_dump(mode='json') for r in pending_requests],
                        "session_id": actual_session_id
                    }
                    return

                if self._should_handle_sequentially():
                    tool_calls = [tool_calls[0]]
  
                assistant_msg = self._sanitize_message({"role": "assistant", "tool_calls": tool_calls, "content": full_content})
                messages.append(assistant_msg)
                new_turns.append(assistant_msg)
                
                # Execute sequentially (sync stream is always sequential execution in practice for simplicity)
                for tool_call in tool_calls:
                    t_name = tool_call["function"]["name"]
                    t_id = tool_call["id"]
                    tool_result_val = None
                    try:
                        result = self._execute_tool(tool_call)
                        tool_result_val = {
                            "role": "tool",
                            "tool_call_id": t_id,
                            "content": str(result)
                        }
                    except HandoffAgent as handoff:
                        target_agent = self.sub_agents[handoff.target_agent_name]
                        tool_result_val = None
                        for chunk in self._dispatch_to_subagent_sync_streaming(
                            target_agent=target_agent,
                            parent_messages=messages,
                            instructions=handoff.kwargs.get("instructions"),
                            tool_call_id=t_id,
                            session_id=actual_session_id,
                            stream_events=stream_events,
                            **kwargs
                        ):
                            sentinel = chunk.get("_tool_result") if isinstance(chunk, dict) else None
                            if sentinel is not None:
                                tool_result_val = sentinel
                            else:
                                yield chunk
                    
                    if stream_events:
                        yield {"type": "tool_end", "name": t_name, "result": str(tool_result_val["content"])}  # type: ignore
                         
                    messages.append(tool_result_val)
                    new_turns.append(tool_result_val)  # type: ignore
                
                continue
            
            final_msg = self._sanitize_message({"role": "assistant", "content": full_content})
            messages.append(final_msg)
            new_turns.append(final_msg)
            if _persist_history:
                self._update_history(new_turns, actual_session_id=actual_session_id)
            return

    async def astream(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, session_id: Optional[Union[str, Session]] = None, stream_events: bool = False, images: Optional[List[str]] = None, **kwargs) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """
        Execute an asynchronous streaming completion with automatic tool calling.
        If stream_events=True, yields structured dictionaries instead of strings.
        """
        _persist_history = kwargs.pop("_persist_history", True)
        actual_session_id = session_id.id if isinstance(session_id, Session) else (session_id or str(uuid.uuid4()))
        _override_messages = kwargs.pop("_override_messages", None)
        messages = _override_messages if _override_messages is not None else await self._aprepare_messages(prompt, actual_session_id=actual_session_id, images=images)
        
        # Inject Vector Context (Async)
        if prompt and self.vector_store:
            context_str = await self._retrieve_context(prompt)
            if context_str:
                messages.insert(1, {"role": "system", "content": context_str})
                
        tools = tools or self.tools
        new_turns = []  # type: ignore
        
        while True:
            # RESUME LOGIC
            last_msg = messages[-1]
            is_resume = (not prompt and len(new_turns) == 0 and 
                        last_msg.get("role") == "assistant" and 
                        last_msg.get("tool_calls"))
            
            if is_resume:
                adk_logger.info("Resuming from pending tool calls (astream)...")
                tool_calls = last_msg.get("tool_calls", [])
                full_content = last_msg.get("content") or ""
            else:
                response = await self._aget_completion(messages=messages, tools=tools, stream=True, **kwargs)
                
                full_content = ""
                tool_calls_by_index = {}  # type: ignore
                notified_tools = set()

                async for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_content += delta.content
                        if stream_events:
                            yield {"type": "content", "delta": delta.content}
                        else:
                            yield delta.content
                    
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_by_index:
                                tool_calls_by_index[idx] = []
                            
                            last_tc = tool_calls_by_index[idx][-1] if tool_calls_by_index[idx] else None
                            start_new = False
                            if last_tc is None:
                                start_new = True
                            else:
                                if tc_delta.function and tc_delta.function.name and last_tc.function.name:
                                    start_new = True
                                elif tc_delta.id and last_tc.id and tc_delta.id != last_tc.id:
                                    start_new = True
                            
                            if start_new:
                                new_tc = SimpleNamespace(
                                    id=tc_delta.id,
                                    function=SimpleNamespace(
                                        name=tc_delta.function.name if tc_delta.function else None,
                                        arguments=tc_delta.function.arguments if tc_delta.function else ""
                                    )
                                )
                                tool_calls_by_index[idx].append(new_tc)
                            else:
                                if tc_delta.id:
                                    last_tc.id = tc_delta.id  # type: ignore
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        last_tc.function.name = (last_tc.function.name or "") + tc_delta.function.name  # type: ignore
                                    if tc_delta.function.arguments:
                                        if last_tc.function.arguments is None:  # type: ignore
                                            last_tc.function.arguments = ""  # type: ignore
                                        last_tc.function.arguments += tc_delta.function.arguments  # type: ignore
                            
                            # Yield "Thinking" event as soon as name is known
                            current_tc = tool_calls_by_index[idx][-1]
                            if current_tc.function.name and idx not in notified_tools:
                                if stream_events:
                                    yield {"type": "tool_start", "name": current_tc.function.name, "index": idx}
                                notified_tools.add(idx)

                tool_calls = []
                for idx in sorted(tool_calls_by_index.keys()):
                    for tc_obj in tool_calls_by_index[idx]:
                        if tc_obj.function.name:
                            tool_calls.append({
                                "id": tc_obj.id,
                                "type": "function",
                                "function": {
                                    "name": tc_obj.function.name,
                                    "arguments": tc_obj.function.arguments
                                }
                            })
      
            if tool_calls:
                # HITL APPROVAL CHECK
                pending_requests = []
                for tc in tool_calls:
                    t_name = self._get_tc_val(tc, "function", "name")
                    t_id = self._get_tc_val(tc, "id")
                    t_args = self._parse_arguments(self._get_tc_val(tc, "function", "arguments"))
                    
                    request = self.approval_manager.get_request(t_id)
                    if not request:
                        if self._should_require_approval(t_name, t_args):
                            request = self.approval_manager.create_request(t_id, actual_session_id, t_name, t_args)
                    
                    if request and request.status == ApprovalStatus.PENDING:
                        pending_requests.append(request)

                if pending_requests:
                    # Persist assistant msg so we can resume later
                    assistant_msg = self._sanitize_message({"role": "assistant", "tool_calls": tool_calls, "content": full_content})
                    if assistant_msg not in messages:
                        messages.append(assistant_msg)
                        new_turns.append(assistant_msg)
                    if _persist_history:
                        await self._aupdate_history(new_turns, actual_session_id=actual_session_id)
                    
                    yield {
                        "type": "requires_approval",
                        "pending_approvals": [r.model_dump(mode='json') for r in pending_requests],
                        "session_id": actual_session_id
                    }
                    return

                if self._should_handle_sequentially():
                    tool_calls = [tool_calls[0]]
  
                assistant_msg = self._sanitize_message({"role": "assistant", "tool_calls": tool_calls, "content": full_content})
                messages.append(assistant_msg)
                new_turns.append(assistant_msg)
                
                if self._should_handle_sequentially():
                    for tool_call in tool_calls:
                        t_name = tool_call["function"]["name"]
                        t_id = tool_call["id"]
                        try:
                            result = await self._aexecute_tool(tool_call)
                        except HandoffAgent as handoff:
                            target_agent = self.sub_agents[handoff.target_agent_name]
                            result = None
                            async for chunk in self._adispatch_to_subagent_streaming(
                                target_agent=target_agent,
                                parent_messages=messages,
                                instructions=handoff.kwargs.get("instructions"),
                                tool_call_id=t_id,
                                session_id=actual_session_id,
                                stream_events=stream_events,
                                **kwargs
                            ):
                                sentinel = chunk.get("_tool_result") if isinstance(chunk, dict) else None
                                if sentinel is not None:
                                    result = sentinel
                                else:
                                    yield chunk
                        
                        if stream_events:
                             yield {"type": "tool_end", "name": t_name, "result": str(result.get("content", "") if isinstance(result, dict) else result)}

                        messages.append(result)
                        new_turns.append(result)
                else:
                    # Parallel Execution — YIELD AS THEY FINISH
                    async def exec_tool(tc):
                        t_name_inner = tc["function"]["name"]
                        t_id_inner = tc["id"]
                        try:
                            res = await self._aexecute_tool(tc)
                            res["_t_name"] = t_name_inner
                            return res
                        except HandoffAgent as handoff:
                            target_agent = self.sub_agents[handoff.target_agent_name]
                            res = await self._adispatch_to_subagent(
                                target_agent=target_agent,
                                parent_messages=messages,
                                instructions=handoff.kwargs.get("instructions"),
                                tool_call_id=t_id_inner,
                                session_id=actual_session_id,
                                **kwargs
                            )
                            res["_t_name"] = t_name_inner
                            return res

                    pending = [exec_tool(tc) for tc in tool_calls]
                    results_to_append = []
                    
                    for coro in asyncio.as_completed(pending):
                        res = await coro
                        t_name = res.pop("_t_name", "tool")
                        if stream_events:
                            yield {"type": "tool_end", "name": t_name, "result": str(res["content"])}
                        results_to_append.append(res)
                    
                    for res in results_to_append:
                        messages.append(res)
                        new_turns.append(res)

                # Continue turn after tool results
                continue
            
            final_msg = self._sanitize_message({"role": "assistant", "content": full_content})
            messages.append(final_msg)
            new_turns.append(final_msg)
            if _persist_history:
                await self._aupdate_history(new_turns, actual_session_id=actual_session_id)
            return

    async def check_health(self) -> Dict[str, Any]:
        """
        Production health check for monitoring.
        Verifies connectivity to memory and vector store.
        """
        health = {"status": "healthy", "components": {}}
        
        # Memory Check
        try:
            await self.memory.get_messages("health_check_session")
            health["components"]["memory"] = "ok"  # type: ignore
        except Exception as e:
            health["status"] = "unhealthy"
            health["components"]["memory"] = str(e)  # type: ignore
            
        # Vector Store Check
        if self.vector_store:
            try:
                await self.vector_store.search("health check", k=1)
                health["components"]["vector_store"] = "ok"  # type: ignore
            except Exception as e:
                health["status"] = "unhealthy"
                health["components"]["vector_store"] = str(e)  # type: ignore
        
        return health
