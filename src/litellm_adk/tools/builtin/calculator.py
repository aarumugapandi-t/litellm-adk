"""Built-in Safe Calculator Tool for mathematical reasoning and evaluation."""

import ast
import math
import operator
from typing import Any
from ..base import Tool
from ..permissions import ToolPermission

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_ALLOWED_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
}

_ALLOWED_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONSTANTS:
            return _ALLOWED_CONSTANTS[node.id]
        raise ValueError(f"Unknown variable or constant: {node.id}")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op_type = type(node.op)
        if op_type in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type}")

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        op_type = type(node.op)
        if op_type in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCTIONS:
            args = [_eval_node(arg) for arg in node.args]
            return _ALLOWED_FUNCTIONS[node.func.id](*args)
        raise ValueError(f"Disallowed function call: {getattr(node.func, 'id', node.func)}")

    raise ValueError(f"Unsupported expression construct: {type(node)}")


def calculate(expression: str) -> str:
    """Safely evaluates a mathematical expression without security risks.

    Args:
        expression: The mathematical expression string (e.g., '15 * 4 + sqrt(144)').

    Returns:
        The evaluated numerical result as a string, or an error message.
    """
    if not expression or not expression.strip():
        return "Error: Empty expression provided."

    clean_expr = expression.strip().replace("^", "**")
    try:
        parsed = ast.parse(clean_expr, mode="eval")
        result = _eval_node(parsed.body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return str(result)
    except Exception as e:
        return f"Calculation Error: {str(e)}"


def create_calculator_tool() -> Tool:
    """Instantiates a first-class Tool wrapping the safe calculator function."""
    return Tool(
        func=calculate,
        name="calculator",
        description="Performs safe mathematical calculations, arithmetic, percentages, and scientific formulas.",
        permissions={ToolPermission.READ},
        timeout=5.0,
    )
