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

    @staticmethod
    def truncate_history(
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int,
        reserve_tokens: int = 500,
    ) -> List[Dict[str, Any]]:
        """Truncate history to fit within max_tokens, always preserving the system prompt

        and ensuring atomic sequences (tool calls and results) are never split.
        """
        if not messages:
            return []

        # 1. Separate System Prompt
        system_prompt = None
        if messages[0].get("role") == "system":
            system_prompt = messages[0]
            other_messages = messages[1:]
        else:
            other_messages = messages

        # 2. Calculate Budget
        actual_reserve = min(reserve_tokens, int(max_tokens * 0.2)) if max_tokens > 0 else 0
        allowed_tokens = max_tokens - actual_reserve

        if system_prompt:
            allowed_tokens -= ContextManager.count_tokens([system_prompt], model)

        # 3. Quick Check: Is truncation even needed?
        if ContextManager.count_tokens(other_messages, model) <= allowed_tokens:
            return messages

        # 4. Group into Atomic Blocks
        blocks: List[List[Dict[str, Any]]] = []
        current_block: List[Dict[str, Any]] = []

        for msg in other_messages:
            role = msg.get("role")

            if role == "tool":
                # A tool message always belongs to the preceding assistant block
                current_block.append(msg)
            elif role == "assistant" and msg.get("tool_calls"):
                # Start a new block that will include this and subsequent tool messages
                if current_block:
                    blocks.append(current_block)
                current_block = [msg]
            else:
                # Regular user or simple assistant message
                if current_block:
                    blocks.append(current_block)
                current_block = [msg]

        if current_block:
            blocks.append(current_block)

        # 5. Truncate by block (Keeping the LATEST blocks)
        truncated_blocks: List[List[Dict[str, Any]]] = []
        current_tokens = 0

        if blocks:
            # Always keep the very last block to ensure the model has something to respond to
            last_block = blocks[-1]
            truncated_blocks.append(last_block)
            current_tokens += ContextManager.count_tokens(last_block, model)

            for block in reversed(blocks[:-1]):
                block_tokens = ContextManager.count_tokens(block, model)
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

        # 2. Augment system prompt with extra context blocks if present
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
        if retrieved_documents:
            extra_sections.append("### Retrieved Reference Context:\n" + "\n\n".join(retrieved_documents))

        if extra_sections:
            resolved_system = f"{resolved_system}\n\n" + "\n\n".join(extra_sections)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": resolved_system}]

        # 3. Add conversation history
        messages.extend([dict(m) for m in conversation_history])

        # 4. Add current prompt if provided and not already in conversation history
        if current_prompt:
            if not (conversation_history and conversation_history[-1].get("role") == "user" and conversation_history[-1].get("content") == current_prompt):
                messages.append({"role": "user", "content": current_prompt})

        # 5. Apply context token limits if configured
        max_tokens = self.policy.max_tokens
        if max_tokens:
            messages = self.truncate_history(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                reserve_tokens=self.policy.reserve_tokens,
            )

        return messages
