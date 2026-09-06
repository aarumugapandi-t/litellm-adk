"""Agent execution loop implementing the Observe-Decide-Act cycle."""

import asyncio
import time
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Type, Union
import uuid
from pydantic import BaseModel

from ..context.manager import ContextManager
from ..events.bus import EventBus
from ..events.types import (
    AgentErrorEvent,
    AgentFinished,
    AgentStarted,
    Event,
    HumanApprovalRequired,
    TextDelta,
    ToolCallCompleted,
    ToolCallFailed,
    ToolCallStarted,
)
from ..exceptions import (
    AgentError,
    ExecutionTimeoutError,
    HumanInterventionError,
    MaxIterationsError,
    OutputValidationError,
)
from ..models import ApprovalStatus
from ..human.base import HumanInTheLoop
from ..middleware.base import MiddlewarePipeline
from ..models.base import Model, ModelResponse, ModelUsage
from ..observability.logger import adk_logger
from ..tools.executor import ToolExecutor
from .config import ExecutionConfig
from .output_parser import OutputParser
from .result import AgentResult, ToolCallRecord
from .state import AgentLifecycleState, AgentState


class AgentLoop:
    """Orchestrates the Observe-Decide-Act-Observe-Finish agent reasoning cycle."""

    def __init__(
        self,
        model: Model,
        tool_executor: ToolExecutor,
        context_manager: ContextManager,
        event_bus: EventBus,
        middleware: MiddlewarePipeline,
        execution_config: Optional[ExecutionConfig] = None,
        human_in_the_loop: Optional[HumanInTheLoop] = None,
        agent: Optional[Any] = None,
    ):
        self.model = model
        self.tool_executor = tool_executor
        self.context_manager = context_manager
        self.event_bus = event_bus
        self.middleware = middleware
        self.config = execution_config or ExecutionConfig()
        self.human_in_the_loop = human_in_the_loop
        self.agent = agent

    async def run(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session_id: str,
        system_prompt: Union[str, Callable[[Any], str]],
        conversation_history: List[Dict[str, Any]],
        images: Optional[List[str]] = None,
        developer_prompt: Optional[str] = None,
        working_memory_notes: Optional[List[str]] = None,
        long_term_memories: Optional[List[str]] = None,
        retrieved_documents: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        agent_name: str = "Agent",
        stream: bool = False,
    ) -> AgentResult:
        """Executes the loop synchronously until completion or terminal condition."""
        run_id = str(uuid.uuid4())
        state = AgentState(run_id=run_id, session_id=session_id)
        state.transition(AgentLifecycleState.RUNNING)

        tool_records: List[ToolCallRecord] = []
        accumulated_usage = ModelUsage()
        local_messages = list(conversation_history)

        # Check if resuming from pending tool calls (HITL second pass)
        is_resuming = (
            not prompt
            and bool(local_messages)
            and local_messages[-1].get("role") == "assistant"
            and bool(local_messages[-1].get("tool_calls"))
        )

        prompt_summary = " ".join(str(m.get("content", "")) for m in prompt if isinstance(m, dict)) if isinstance(prompt, list) else str(prompt or "")

        middleware_context: Dict[str, Any] = {
            "run_id": run_id,
            "session_id": session_id,
            "agent_name": agent_name,
            "prompt": prompt_summary,
            "system_prompt": system_prompt,
            "messages": local_messages,
        }

        await self.middleware.run_before(middleware_context)
        await self.event_bus.publish(AgentStarted(run_id=run_id, agent_id=agent_name, prompt=prompt_summary))

        # Add initial user message or messages list if prompt is present and not resuming
        if not is_resuming:
            if isinstance(prompt, list):
                for msg in prompt:
                    if isinstance(msg, dict) and "role" in msg:
                        local_messages.append(dict(msg))
                if images:
                    user_msg_idx = next((i for i in reversed(range(len(local_messages))) if local_messages[i].get("role") == "user"), None)
                    img_parts = [{"type": "image_url", "image_url": {"url": img}} for img in images]
                    if user_msg_idx is not None:
                        curr_content = local_messages[user_msg_idx].get("content", "")
                        if isinstance(curr_content, str):
                            local_messages[user_msg_idx]["content"] = [{"type": "text", "text": curr_content}] + img_parts
                        elif isinstance(curr_content, list):
                            local_messages[user_msg_idx]["content"] = curr_content + img_parts
                    else:
                        local_messages.append({"role": "user", "content": img_parts})
            elif prompt or images:
                if images:
                    content_parts: List[Dict[str, Any]] = []
                    if prompt:
                        content_parts.append({"type": "text", "text": prompt})
                    for img in images:
                        content_parts.append({"type": "image_url", "image_url": {"url": img}})
                    initial_user_content: Union[str, List[Dict[str, Any]]] = content_parts
                else:
                    initial_user_content = prompt

                if not (local_messages and local_messages[-1].get("role") == "user" and local_messages[-1].get("content") == initial_user_content):
                    local_messages.append({"role": "user", "content": initial_user_content})

        repair_attempts = 0

        try:
            while state.iteration < self.config.max_iterations:
                state.iteration += 1

                # Check execution timeout
                if self.config.max_execution_time and state.duration > self.config.max_execution_time:
                    state.transition(AgentLifecycleState.TIMEOUT)
                    raise ExecutionTimeoutError(
                        f"Execution exceeded max execution time of {self.config.max_execution_time}s",
                        timeout=self.config.max_execution_time,
                    )

                # 1. OBSERVE & ASSEMBLE CONTEXT
                assembled_messages = self.context_manager.assemble_messages(
                    system_prompt=system_prompt,
                    conversation_history=local_messages,
                    developer_prompt=developer_prompt,
                    working_memory_notes=working_memory_notes,
                    long_term_memories=long_term_memories,
                    retrieved_documents=retrieved_documents,
                    response_model=response_model,
                    model=self.model.model_name,
                )

                # 2. DECIDE (Call Model with streaming if requested, or resume from pending tool calls)
                if is_resuming and state.iteration == 1:
                    last_asst = local_messages[-1]
                    response = ModelResponse(
                        role="assistant",
                        tool_calls=last_asst.get("tool_calls", []),
                        content=last_asst.get("content", ""),
                    )
                elif stream:
                    accumulated_content: List[str] = []
                    tool_calls_by_index: Dict[int, Dict[str, Any]] = {}
                    chunk_usage = None
                    last_finish_reason = None

                    async for chunk in self.model.stream(
                        messages=assembled_messages,
                        tools=tools,
                    ):
                        if chunk.content_delta:
                            accumulated_content.append(chunk.content_delta)
                            await self.event_bus.publish(
                                TextDelta(
                                    run_id=run_id,
                                    agent_id=agent_name,
                                    delta=chunk.content_delta,
                                )
                            )
                        if chunk.tool_call_deltas:
                            for tc_delta in chunk.tool_call_deltas:
                                idx = tc_delta.get("index", 0)
                                if idx not in tool_calls_by_index:
                                    tool_calls_by_index[idx] = {
                                        "id": tc_delta.get("id") or "",
                                        "type": tc_delta.get("type") or "function",
                                        "function": {
                                            "name": tc_delta.get("function", {}).get("name", ""),
                                            "arguments": tc_delta.get("function", {}).get("arguments", ""),
                                        },
                                    }
                                else:
                                    if tc_delta.get("id"):
                                        tool_calls_by_index[idx]["id"] = tc_delta["id"]
                                    fn = tc_delta.get("function", {})
                                    if fn.get("name"):
                                        tool_calls_by_index[idx]["function"]["name"] += fn["name"]
                                    if fn.get("arguments"):
                                        tool_calls_by_index[idx]["function"]["arguments"] += fn["arguments"]
                        if chunk.usage:
                            chunk_usage = chunk.usage
                        if chunk.finish_reason:
                            last_finish_reason = chunk.finish_reason

                    raw_tool_calls = [
                        v for k, v in sorted(tool_calls_by_index.items()) if v.get("function", {}).get("name")
                    ]
                    sanitized_tool_calls = [self.model._sanitize_tool_call(tc) for tc in raw_tool_calls]
                    full_content = "".join(accumulated_content) or None

                    response = ModelResponse(
                        content=full_content,
                        tool_calls=sanitized_tool_calls,
                        usage=chunk_usage or ModelUsage(),
                        finish_reason=last_finish_reason,
                    )
                else:
                    response = await self.model.generate(
                        messages=assembled_messages,
                        tools=tools,
                    )

                # Accumulate usage
                accumulated_usage.prompt_tokens += response.usage.prompt_tokens
                accumulated_usage.completion_tokens += response.usage.completion_tokens
                accumulated_usage.total_tokens += response.usage.total_tokens

                # 3. ACT (Check for Tool Calls)
                if response.tool_calls:
                    if not (is_resuming and state.iteration == 1):
                        # Append assistant message with tool calls to local history
                        assistant_msg: Dict[str, Any] = {"role": "assistant", "tool_calls": response.tool_calls}
                        if response.content:
                            assistant_msg["content"] = response.content
                        local_messages.append(assistant_msg)

                        # Pre-check if any tool call requires approval before running
                        pending_requests = []
                        for tc in response.tool_calls:
                            tc_id = tc.get("id", str(uuid.uuid4()))
                            fn = tc.get("function", {})
                            tc_name = fn.get("name", "")
                            tc_raw_args = fn.get("arguments", {})
                            parsed_args = self.tool_executor.parse_arguments(tc_raw_args)

                            req = None
                            if self.human_in_the_loop and hasattr(self.human_in_the_loop, "get_request"):
                                req = self.human_in_the_loop.get_request(tc_id)

                            needs_approval = False
                            if req is None:
                                tool_obj = self.tool_executor.registry.get_tool(tc_name)
                                if tool_obj and tool_obj.check_approval_required(parsed_args):
                                    needs_approval = True
                                elif self.agent and hasattr(self.agent, "_should_require_approval"):
                                    try:
                                        needs_approval = self.agent._should_require_approval(tc_name, parsed_args)
                                    except Exception:
                                        pass
                                elif self.agent and getattr(self.agent, "policy_engine", None):
                                    pe = getattr(self.agent, "policy_engine")
                                    if hasattr(pe, "evaluate"):
                                        eval_res = pe.evaluate(tc_name, parsed_args)
                                        needs_approval = getattr(eval_res, "requires_approval", False)

                                if needs_approval and self.human_in_the_loop and hasattr(self.human_in_the_loop, "create_request"):
                                    req = self.human_in_the_loop.create_request(tc_id, session_id, tc_name, parsed_args)

                            if req and getattr(req, "status", None) == ApprovalStatus.PENDING:
                                pending_requests.append(req)

                        if pending_requests:
                            state.transition(AgentLifecycleState.WAITING_FOR_HUMAN)
                            for preq in pending_requests:
                                await self.event_bus.publish(
                                    HumanApprovalRequired(
                                        run_id=run_id,
                                        agent_id=agent_name,
                                        tool_name=preq.tool_name,
                                        tool_call_id=preq.id,
                                        arguments=preq.original_args,
                                    )
                                )
                            pending_list = [
                                r.model_dump(mode="json") if hasattr(r, "model_dump") else dict(r)
                                for r in pending_requests
                            ]
                            conversation_history.clear()
                            conversation_history.extend(local_messages)
                            return AgentResult(
                                text="",
                                status="requires_approval",
                                pending_approvals=pending_list,
                                run_id=run_id,
                                session_id=session_id,
                                usage=accumulated_usage,
                                duration=state.duration,
                                metadata={"requires_approval": True, "pending_approvals": pending_list},
                            )

                    # Approval hook helper
                    async def _approval_hook(t_name: str, t_id: str, t_args: Dict[str, Any]) -> Dict[str, Any]:
                        await self.event_bus.publish(
                            HumanApprovalRequired(
                                run_id=run_id,
                                agent_id=agent_name,
                                tool_name=t_name,
                                tool_call_id=t_id,
                                arguments=t_args,
                            )
                        )
                        if self.human_in_the_loop:
                            state.transition(AgentLifecycleState.WAITING_FOR_HUMAN)
                            res = await self.human_in_the_loop.request_approval(t_name, t_id, t_args)
                            state.transition(AgentLifecycleState.RUNNING)
                            return res
                        return t_args

                    # Execute tool call(s)
                    async def _exec_single(tc: Dict[str, Any]) -> Dict[str, Any]:
                        tc_id = tc.get("id", str(uuid.uuid4()))
                        fn = tc.get("function", {})
                        tc_name = fn.get("name", "")
                        tc_raw_args = fn.get("arguments", {})
                        parsed_args = self.tool_executor.parse_arguments(tc_raw_args)

                        # Check if this request was previously reviewed
                        req = None
                        if self.human_in_the_loop and hasattr(self.human_in_the_loop, "get_request"):
                            req = self.human_in_the_loop.get_request(tc_id)

                        if req and getattr(req, "status", None) == ApprovalStatus.REJECTED:
                            rej_msg = f"Tool call rejected: {req.reason or 'User rejected'}"
                            tool_records.append(
                                ToolCallRecord(
                                    id=tc_id,
                                    name=tc_name,
                                    arguments=parsed_args,
                                    result=rej_msg,
                                    error=rej_msg,
                                    approved=False,
                                )
                            )
                            await self.event_bus.publish(
                                ToolCallCompleted(
                                    run_id=run_id,
                                    agent_id=agent_name,
                                    tool_name=tc_name,
                                    tool_call_id=tc_id,
                                    result=rej_msg,
                                )
                            )
                            return {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": tc_name,
                                "content": rej_msg,
                            }

                        if req and getattr(req, "status", None) == ApprovalStatus.MODIFIED:
                            parsed_args = req.modified_args or parsed_args

                        await self.event_bus.publish(
                            ToolCallStarted(
                                run_id=run_id,
                                agent_id=agent_name,
                                tool_name=tc_name,
                                tool_call_id=tc_id,
                                arguments=parsed_args,
                            )
                        )

                        t_start = time.time()
                        try:
                            tool_msg = await self.tool_executor.execute_tool_call(
                                tool_name=tc_name,
                                tool_call_id=tc_id,
                                arguments=parsed_args,
                                on_approval_check=_approval_hook,
                            )
                            t_dur = time.time() - t_start
                            tool_records.append(
                                ToolCallRecord(
                                    id=tc_id,
                                    name=tc_name,
                                    arguments=parsed_args,
                                    result=tool_msg.get("content"),
                                    duration=t_dur,
                                    approved=True,
                                )
                            )
                            await self.event_bus.publish(
                                ToolCallCompleted(
                                    run_id=run_id,
                                    agent_id=agent_name,
                                    tool_name=tc_name,
                                    tool_call_id=tc_id,
                                    result=tool_msg.get("content"),
                                    duration=t_dur,
                                )
                            )
                            return tool_msg
                        except Exception as e:
                            t_dur = time.time() - t_start
                            tool_records.append(
                                ToolCallRecord(
                                    id=tc_id,
                                    name=tc_name,
                                    arguments=parsed_args,
                                    error=str(e),
                                    duration=t_dur,
                                    approved=False,
                                )
                            )
                            await self.event_bus.publish(
                                ToolCallFailed(
                                    run_id=run_id,
                                    agent_id=agent_name,
                                    tool_name=tc_name,
                                    tool_call_id=tc_id,
                                    error=str(e),
                                )
                            )
                            raise e

                    if self.config.parallel_tool_calls and len(response.tool_calls) > 1:
                        tool_messages = await asyncio.gather(*[_exec_single(tc) for tc in response.tool_calls])
                    else:
                        tool_messages = []
                        for tc in response.tool_calls:
                            tool_messages.append(await _exec_single(tc))

                    # Append tool result messages to conversation
                    local_messages.extend(tool_messages)
                    state.tool_call_count += len(tool_messages)
                    is_resuming = False
                    continue

                # 4. FINISH (No tool calls; model returned final answer)
                final_text = response.content or ""
                structured_data = None

                # Handle structured output validation if requested
                if response_model:
                    try:
                        structured_data = OutputParser.parse_as_model(final_text, response_model)
                    except OutputValidationError as val_err:
                        if repair_attempts >= 2:
                            state.transition(AgentLifecycleState.FAILED, error=str(val_err))
                            raise val_err
                        repair_attempts += 1
                        adk_logger.warning(
                            f"Structured output failed validation: {val_err}. Triggering repair prompt (attempt {repair_attempts}/2)."
                        )
                        repair_prompt = OutputParser.build_repair_prompt(final_text, val_err, response_model)
                        local_messages.append({"role": "assistant", "content": final_text})
                        local_messages.append({"role": "user", "content": repair_prompt})
                        continue

                state.transition(AgentLifecycleState.COMPLETED)
                result = AgentResult(
                    text=final_text,
                    structured=structured_data,
                    run_id=run_id,
                    session_id=session_id,
                    usage=accumulated_usage,
                    tool_calls=tool_records,
                    iterations=state.iteration,
                    duration=state.duration,
                )

                await self.event_bus.publish(
                    AgentFinished(run_id=run_id, agent_id=agent_name, output=final_text, duration=state.duration)
                )
                await self.middleware.run_after(middleware_context, result)

                # Append final assistant message to conversation history
                conversation_history.clear()
                conversation_history.extend(local_messages)
                conversation_history.append({"role": "assistant", "content": final_text})

                return result

            # If loop finished due to max iterations
            state.transition(AgentLifecycleState.MAX_ITERATIONS)
            raise MaxIterationsError(
                f"Agent exceeded max iterations limit ({self.config.max_iterations})",
                iterations=state.iteration,
                max_iterations=self.config.max_iterations,
            )

        except Exception as e:
            state.transition(AgentLifecycleState.FAILED, error=str(e))
            await self.event_bus.publish(AgentErrorEvent(run_id=run_id, agent_id=agent_name, error=str(e)))
            await self.middleware.run_on_error(middleware_context, e)
            raise e

    async def stream(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        session_id: str,
        system_prompt: Union[str, Callable[[Any], str]],
        conversation_history: List[Dict[str, Any]],
        images: Optional[List[str]] = None,
        developer_prompt: Optional[str] = None,
        working_memory_notes: Optional[List[str]] = None,
        long_term_memories: Optional[List[str]] = None,
        retrieved_documents: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        agent_name: str = "Agent",
    ) -> AsyncIterator[Event]:
        """Runs the agent and yields live events as they occur."""
        q = self.event_bus.create_stream_queue()

        # Run loop in background task with stream=True
        task = asyncio.create_task(
            self.run(
                prompt=prompt,
                session_id=session_id,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                images=images,
                developer_prompt=developer_prompt,
                working_memory_notes=working_memory_notes,
                long_term_memories=long_term_memories,
                retrieved_documents=retrieved_documents,
                response_model=response_model,
                tools=tools,
                agent_name=agent_name,
                stream=True,
            )
        )

        try:
            while not task.done() or not q.empty():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=0.1)
                    if event is not None:
                        yield event
                except asyncio.TimeoutError:
                    continue

            # Check if task raised an error
            if task.done() and task.exception():
                raise task.exception()

        finally:
            self.event_bus.remove_stream_queue(q)
            await asyncio.sleep(0)
