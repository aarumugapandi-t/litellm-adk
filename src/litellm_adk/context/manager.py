"""Context manager responsible for assembling LLM payloads and enforcing token budgets."""

from typing import Any, Callable, Dict, List, Optional, Union
import litellm

from ..observability.logger import adk_logger
from .policy import ContextPolicy, ContextStrategy


class ContextManager:
    """Handles token estimation, atomic history truncation, and complete prompt context assembly."""

    def __init__(self, policy: Optional[ContextPolicy] = None):
        self.policy = policy or ContextPolicy()

    @staticmethod
    def count_tokens(messages: List[Dict[str, Any]], model: str = "gpt-4") -> int:
        """Calculate the number of tokens in a list of messages.

        Uses cached 'token_count' if available, otherwise LiteLLM's token_counter.
        """
        if len(messages) == 1 and "token_count" in messages[0]:
            return messages[0]["token_count"]

        clean_messages = [{k: v for k, v in m.items() if k != "token_count"} for m in messages]
        try:
            return litellm.token_counter(model=model, messages=clean_messages)
        except Exception as e:
            adk_logger.warning(f"Token counting failed for model {model}: {e}. Falling back to estimate.")
            total_chars = sum(len(str(m.get("content", ""))) for m in clean_messages)
            return max(1, total_chars // 4)

    @classmethod
    def truncate_history(
        cls,
        messages: List[Dict[str, Any]],
        model: str = "gpt-4",
        max_tokens: Optional[int] = None,
        reserve_tokens: int = 500,
        preserve_system_prompt: bool = True,
        preserve_last_n_messages: int = 4,
    ) -> List[Dict[str, Any]]:
        """Truncate history to fit within max_tokens, always preserving the system prompt
        and ensuring atomic sequences (tool calls and results) are never split.
        """
        if not messages or not max_tokens:
            return list(messages) if messages else []

        # 1. Separate System Prompt
        system_prompt = None
        if preserve_system_prompt and messages[0].get("role") == "system":
            system_prompt = messages[0]
            other_messages = messages[1:]
        else:
            other_messages = messages

        # 2. Calculate Budget
        actual_reserve = min(reserve_tokens, int(max_tokens * 0.2)) if max_tokens > 0 else 0
        allowed_tokens = max_tokens - actual_reserve

        if system_prompt:
            allowed_tokens -= cls.count_tokens([system_prompt], model)

        # 3. Quick Check: Is truncation even needed?
        if cls.count_tokens(other_messages, model) <= allowed_tokens:
            return messages

        # 4. Group into Atomic Blocks
        blocks: List[List[Dict[str, Any]]] = []
        current_block: List[Dict[str, Any]] = []

        for msg in other_messages:
            role = msg.get("role")

            if role == "tool":
                current_block.append(msg)
            elif role == "assistant" and msg.get("tool_calls"):
                if current_block:
                    blocks.append(current_block)
                current_block = [msg]
            else:
                if current_block:
                    blocks.append(current_block)
                current_block = [msg]

        if current_block:
            blocks.append(current_block)

        # 5. Truncate by block (Keeping the LATEST blocks that fit within allowed_tokens)
        truncated_blocks: List[List[Dict[str, Any]]] = []
        current_tokens = 0

        if blocks:
            # Always keep the very last block to ensure the model has something to respond to
            last_block = blocks[-1]
            truncated_blocks.append(last_block)
            current_tokens += cls.count_tokens(last_block, model)

            for block in reversed(blocks[:-1]):
                block_tokens = cls.count_tokens(block, model)
                if current_tokens + block_tokens > allowed_tokens:
                    break
                truncated_blocks.insert(0, block)
                current_tokens += block_tokens

        # 6. Reconstruct
        result: List[Dict[str, Any]] = []
        if system_prompt:
            result.append(system_prompt)
        for block in truncated_blocks:
            result.extend(block)

        return result

    @classmethod
    def semantic_truncate_history(
        cls,
        messages: List[Dict[str, Any]],
        model: str = "gpt-4",
        max_tokens: Optional[int] = None,
        reserve_tokens: int = 500,
        preserve_system_prompt: bool = True,
        preserve_last_n_messages: int = 4,
    ) -> List[Dict[str, Any]]:
        """Semantic truncation: strips intermediate tool-calling traces from older conversation turns

        while keeping the assistant's final answers, then applies windowed truncation if still over budget.
        """
        if not messages or not max_tokens:
            return list(messages) if messages else []

        actual_reserve = min(reserve_tokens, int(max_tokens * 0.2)) if max_tokens > 0 else 0
        allowed_tokens = max_tokens - actual_reserve

        if cls.count_tokens(messages, model) <= allowed_tokens:
            return messages

        # Separate system prompt
        sys_msg = None
        convo = messages
        if preserve_system_prompt and messages[0].get("role") == "system":
            sys_msg = messages[0]
            convo = messages[1:]

        # Split into older turns and protected recent turns
        if len(convo) > preserve_last_n_messages:
            older_turns = convo[:-preserve_last_n_messages]
            recent_turns = convo[-preserve_last_n_messages:]
        else:
            older_turns = []
            recent_turns = convo

        # Strip intermediate tool execution messages from older turns
        cleaned_older: List[Dict[str, Any]] = []
        for msg in older_turns:
            role = msg.get("role")
            if role == "tool":
                continue
            elif role == "assistant" and msg.get("tool_calls"):
                content = msg.get("content")
                if content:
                    cleaned_older.append({"role": "assistant", "content": content})
            else:
                cleaned_older.append(msg)

        rebuilt: List[Dict[str, Any]] = []
        if sys_msg:
            rebuilt.append(sys_msg)
        rebuilt.extend(cleaned_older)
        rebuilt.extend(recent_turns)

        return cls.truncate_history(
            messages=rebuilt,
            model=model,
            max_tokens=max_tokens,
            reserve_tokens=reserve_tokens,
            preserve_system_prompt=preserve_system_prompt,
            preserve_last_n_messages=preserve_last_n_messages,
        )

    @classmethod
    def summarize_history(
        cls,
        messages: List[Dict[str, Any]],
        model: str = "gpt-4",
        max_tokens: Optional[int] = None,
        reserve_tokens: int = 500,
        preserve_system_prompt: bool = True,
        preserve_last_n_messages: int = 4,
        summarize_model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Summarization strategy: condenses older conversation turns outside preserve_last_n_messages

        into a compact conversation summary block.
        """
        if not messages or not max_tokens:
            return list(messages) if messages else []

        actual_reserve = min(reserve_tokens, int(max_tokens * 0.2)) if max_tokens > 0 else 0
        allowed_tokens = max_tokens - actual_reserve

        if cls.count_tokens(messages, model) <= allowed_tokens:
            return messages

        sys_msg = None
        convo = messages
        if preserve_system_prompt and messages[0].get("role") == "system":
            sys_msg = messages[0]
            convo = messages[1:]

        if len(convo) <= preserve_last_n_messages:
            return messages

        older_turns = convo[:-preserve_last_n_messages]
        recent_turns = convo[-preserve_last_n_messages:]

        summary_lines = []
        for m in older_turns:
            r = m.get("role", "unknown").capitalize()
            c = str(m.get("content", "")).strip()
            if c:
                snippet = (c[:50] + "...") if len(c) > 50 else c
                summary_lines.append(f"- {r}: {snippet}")

        summary_text = "### Previous Conversation Summary:\n" + "\n".join(summary_lines)
        summary_msg = {"role": "system", "content": summary_text}

        result: List[Dict[str, Any]] = []
        if sys_msg:
            combined_sys = dict(sys_msg)
            combined_sys["content"] = str(sys_msg.get("content", "")) + "\n\n" + summary_text
            result.append(combined_sys)
        else:
            result.append(summary_msg)
        result.extend(recent_turns)

        return cls.truncate_history(
            messages=result,
            model=model,
            max_tokens=max_tokens,
            reserve_tokens=reserve_tokens,
            preserve_system_prompt=preserve_system_prompt,
            preserve_last_n_messages=preserve_last_n_messages,
        )

    def apply_compaction(self, messages: List[Dict[str, Any]], model: str = "gpt-4") -> List[Dict[str, Any]]:
        """Applies configured compaction strategy to messages based on policy."""
        if not self.policy.max_tokens:
            return messages

        strategy = self.policy.strategy
        if strategy == ContextStrategy.SEMANTIC_TRUNCATION:
            return self.semantic_truncate_history(
                messages=messages,
                model=model,
                max_tokens=self.policy.max_tokens,
                reserve_tokens=self.policy.reserve_tokens,
                preserve_system_prompt=self.policy.preserve_system_prompt,
                preserve_last_n_messages=self.policy.preserve_last_n_messages,
            )
        elif strategy in (ContextStrategy.SUMMARIZATION, ContextStrategy.SUMMARIZE):
            return self.summarize_history(
                messages=messages,
                model=model,
                max_tokens=self.policy.max_tokens,
                reserve_tokens=self.policy.reserve_tokens,
                preserve_system_prompt=self.policy.preserve_system_prompt,
                preserve_last_n_messages=self.policy.preserve_last_n_messages,
                summarize_model=self.policy.summarize_model,
            )
        else:
            return self.truncate_history(
                messages=messages,
                model=model,
                max_tokens=self.policy.max_tokens,
                reserve_tokens=self.policy.reserve_tokens,
                preserve_system_prompt=self.policy.preserve_system_prompt,
                preserve_last_n_messages=self.policy.preserve_last_n_messages,
            )

    def assemble_messages(
        self,
        system_prompt: Union[str, Callable[[Any], str]],
        conversation_history: List[Dict[str, Any]],
        current_prompt: Optional[str] = None,
        developer_prompt: Optional[str] = None,
        working_memory_notes: Optional[List[str]] = None,
        long_term_memories: Optional[List[str]] = None,
        retrieved_documents: Optional[List[str]] = None,
        response_model: Optional[Any] = None,
        model: str = "gpt-4",
        context_obj: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Builds complete input message payload incorporating instructions, memories, RAG docs, and history."""
        # 1. Resolve system prompt
        if callable(system_prompt):
            resolved_system = system_prompt(context_obj)
        else:
            resolved_system = str(system_prompt)

        # 2. Augment system prompt with extra persistent context blocks if present
        extra_sections = []
        if developer_prompt:
            extra_sections.append(f"### Developer Instructions:\n{developer_prompt}")
        if response_model:
            from ..agent.output_parser import OutputParser
            extra_sections.append(f"### Output Format Requirement:\n{OutputParser.get_schema_instruction(response_model)}")
        if working_memory_notes:
            extra_sections.append("### Working Memory / Current Plan:\n" + "\n".join(f"- {n}" for n in working_memory_notes))
        if long_term_memories:
            extra_sections.append("### Long-Term Memory / Known Facts:\n" + "\n".join(f"- {m}" for m in long_term_memories))

        # Check placement strategy for ephemeral RAG context
        placement = getattr(self.policy, "context_placement", "user_turn")
        augmented_prompt = current_prompt

        if retrieved_documents:
            if placement == "system_prompt":
                extra_sections.append("### Retrieved Reference Context:\n" + "\n\n".join(retrieved_documents))
            else:
                # Default: Ephemeral User Turn Context
                context_block = "<context>\n" + "\n\n".join(retrieved_documents) + "\n</context>"
                if current_prompt:
                    augmented_prompt = f"{context_block}\n\n{current_prompt}"
                else:
                    augmented_prompt = context_block

        if extra_sections:
            resolved_system = f"{resolved_system}\n\n" + "\n\n".join(extra_sections)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": resolved_system}]

        # 3. Add conversation history
        messages.extend([dict(m) for m in conversation_history])

        # 4. Add current prompt if provided and not already in conversation history
        if augmented_prompt:
            if not (conversation_history and conversation_history[-1].get("role") == "user" and conversation_history[-1].get("content") in (current_prompt, augmented_prompt)):
                messages.append({"role": "user", "content": augmented_prompt})

        # 5. Apply context token limits and compaction policy if configured
        if self.policy.max_tokens:
            messages = self.apply_compaction(messages=messages, model=model)

        return messages
