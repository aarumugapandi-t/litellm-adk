"""Structured output parser with JSON extraction and repair prompt generation."""

import json
import re
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

from ..exceptions import OutputValidationError

T = TypeVar("T", bound=BaseModel)


class OutputParser:
    """Parses and validates LLM outputs into Pydantic models or structured dictionaries."""

    @staticmethod
    def _clean_json_syntax(s: str) -> str:
        """Fixes common LLM JSON syntax issues like trailing commas before closing braces/brackets."""
        return re.sub(r",\s*(\}|\])", r"\1", s)

    @classmethod
    def get_schema_instruction(cls, model_cls: Type[BaseModel]) -> str:
        """Generates a clear schema instruction to guide the LLM to output conforming JSON."""
        schema_dict = model_cls.model_json_schema() if hasattr(model_cls, "model_json_schema") else model_cls.schema()
        schema_str = json.dumps(schema_dict, indent=2)
        return (
            f"You must respond ONLY with a valid JSON object strictly conforming to this JSON Schema:\n"
            f"```json\n{schema_str}\n```\n"
            f"Do not include any introductory remarks, markdown prose outside the JSON code block, or commentary."
        )

    @classmethod
    def extract_json_string(cls, text: str) -> str:
        """Extracts JSON substring from markdown code fences or raw JSON braces."""
        text = text.strip()

        # 1. Look for explicit ```json ... ``` code fence first
        json_matches = re.findall(r"```json\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        for block in json_matches:
            cleaned = block.strip()
            if (cleaned.startswith("{") and cleaned.endswith("}")) or (cleaned.startswith("[") and cleaned.endswith("]")):
                return cleaned

        # 2. Look for generic ``` ... ``` code fence containing JSON
        generic_matches = re.findall(r"```(?:\w+)?\s*([\s\S]*?)\s*```", text)
        for block in generic_matches:
            cleaned = block.strip()
            if (cleaned.startswith("{") and cleaned.endswith("}")) or (cleaned.startswith("[") and cleaned.endswith("]")):
                return cleaned

        # 3. Look for outer JSON braces { ... }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace : last_brace + 1].strip()

        # 4. Look for outer JSON brackets [ ... ]
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            return text[first_bracket : last_bracket + 1].strip()

        return text

    @classmethod
    def parse_as_model(cls, text: str, model_cls: Type[T]) -> T:
        """Parses LLM text output into an instance of model_cls.

        Raises OutputValidationError if parsing or validation fails.
        """
        json_str = cls.extract_json_string(text)
        try:
            data = json.loads(json_str)
            return model_cls.model_validate(data)
        except Exception:
            try:
                cleaned_str = cls._clean_json_syntax(json_str)
                data = json.loads(cleaned_str)
                return model_cls.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as e:
                raise OutputValidationError(
                    message=f"Failed to validate output against {model_cls.__name__}: {e}",
                    raw_output=text,
                    validation_errors=e,
                ) from e

    @classmethod
    def build_repair_prompt(cls, raw_output: str, error: Exception, model_cls: Type[BaseModel]) -> str:
        """Constructs a repair prompt feeding validation errors back to the LLM."""
        schema_dict = model_cls.model_json_schema() if hasattr(model_cls, "model_json_schema") else model_cls.schema()
        schema_str = json.dumps(schema_dict, indent=2)
        return (
            f"Your previous output failed validation against the expected schema.\n\n"
            f"Validation Error:\n{str(error)}\n\n"
            f"Expected JSON Schema:\n{schema_str}\n\n"
            f"Your Previous Output:\n{raw_output}\n\n"
            f"Please output ONLY valid JSON adhering strictly to the above schema without additional explanation."
        )
