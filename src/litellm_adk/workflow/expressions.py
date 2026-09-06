"""Safe template expression evaluator for workflow parameter resolution."""

import re
from typing import Any, Dict, Optional


EXPR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
DISALLOWED_SUBSTRINGS = ("__", "import", "exec", "eval", "globals", "locals")


def _get_nested_value(data: Any, path: str) -> Any:
    """Traverses nested dicts or attributes safely according to a dotted path."""
    parts = path.split(".")
    current = data

    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
    return current


def resolve_expression(expr: str, context: Dict[str, Any]) -> Any:
    """Resolves a single expression string without enclosing braces."""
    expr = expr.strip()
    for bad in DISALLOWED_SUBSTRINGS:
        if bad in expr:
            return None

    # Supported root prefixes: trigger, variables, execution, session, or node_id
    return _get_nested_value(context, expr)


def evaluate_template(value: Any, context: Dict[str, Any]) -> Any:
    """
    Evaluates templates recursively across strings, dictionaries, and lists.
    
    If a string exactly matches `{{ path }}`, the underlying value (e.g. dict, list)
    is returned preserving its original type.
    If multiple expressions or surrounding text exist, values are string-interpolated.
    """
    if isinstance(value, str):
        trimmed = value.strip()
        single_match = re.fullmatch(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}", trimmed)
        if single_match:
            resolved = resolve_expression(single_match.group(1), context)
            return resolved

        def _replace_match(match: re.Match) -> str:
            resolved = resolve_expression(match.group(1), context)
            if resolved is None:
                return ""
            return str(resolved)

        return EXPR_PATTERN.sub(_replace_match, value)

    elif isinstance(value, dict):
        return {k: evaluate_template(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [evaluate_template(item, context) for item in value]
    return value
