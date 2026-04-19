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
        new_turns = []
        accumulated_content = []
        executed_tool_calls = []
        
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
                        self.memory.add_message(actual_session_id, sanitized_msg)
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
                self._update_history(new_turns, actual_session_id=actual_session_id)
            
            return AgentResponse(
                content=final_msg.get("content") or "",
                accumulated_content="\n".join(accumulated_content),
                tool_calls=executed_tool_calls,
                session_id=actual_session_id
            )
