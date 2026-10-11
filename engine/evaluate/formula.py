"""Restricted, deterministic evaluator for numeric pricing formulas."""
from __future__ import annotations

import ast
import math
import operator
from decimal import Decimal
from typing import Any, Dict, Iterable, Mapping


class FormulaError(ValueError):
    """Raised when a formula is invalid or cannot be evaluated safely."""


MAX_FORMULA_LENGTH = 256
MAX_AST_NODES = 64
MAX_AST_DEPTH = 16

SUPPORTED_FORMULA_FUNCTIONS = frozenset({"min", "max", "clamp"})
SUPPORTED_NUMERIC_TYPES = (int, float, Decimal)
_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _numeric_value(value: Any) -> float:
    if type(value) not in SUPPORTED_NUMERIC_TYPES:
        raise FormulaError("Formula values must be finite numbers.")
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        raise FormulaError("Formula values must be finite numbers.") from None
    if not math.isfinite(numeric):
        raise FormulaError("Formula values must be finite numbers.")
    return numeric


def _validate_node(node: ast.AST, allowed_names: set[str], depth: int = 0) -> None:
    if depth > MAX_AST_DEPTH:
        raise FormulaError("Formula expression is too deeply nested.")

    if isinstance(node, ast.Constant):
        _numeric_value(node.value)
        return

    if isinstance(node, ast.Name):
        if node.id not in allowed_names:
            raise FormulaError(f"Unknown formula name '{node.id}'.")
        return

    if isinstance(node, ast.BinOp):
        if type(node.op) not in _BINARY_OPERATORS:
            raise FormulaError("Formula operator is not supported.")
        _validate_node(node.left, allowed_names, depth + 1)
        _validate_node(node.right, allowed_names, depth + 1)
        return

    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARY_OPERATORS:
            raise FormulaError("Formula unary operator is not supported.")
        _validate_node(node.operand, allowed_names, depth + 1)
        return

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in SUPPORTED_FORMULA_FUNCTIONS:
            raise FormulaError("Formula function is not supported.")
        if node.keywords:
            raise FormulaError("Formula functions do not accept keyword arguments.")
        if node.func.id == "clamp" and len(node.args) != 3:
            raise FormulaError("clamp() requires exactly three arguments.")
        if node.func.id in {"min", "max"} and len(node.args) < 2:
            raise FormulaError(f"{node.func.id}() requires at least two arguments.")
        for argument in node.args:
            _validate_node(argument, allowed_names, depth + 1)
        return

    raise FormulaError("Formula syntax is not supported.")


def _parse_formula(expr: str, allowed_names: Iterable[str]) -> ast.AST:
    if not isinstance(expr, str) or not expr.strip():
        raise FormulaError("Formula must be a non-empty expression.")
    if len(expr) > MAX_FORMULA_LENGTH:
        raise FormulaError("Formula expression is too long.")

    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError, TypeError):
        raise FormulaError("Formula syntax is invalid.") from None

    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise FormulaError("Formula expression is too complex.")

    allowed = set(allowed_names)
    _validate_node(tree.body, allowed)
    return tree.body


def validate_formula(expr: str, allowed_names: Iterable[str]) -> str | None:
    """Return a controlled validation error, or ``None`` for a valid formula."""
    try:
        _parse_formula(expr, allowed_names)
    except FormulaError as exc:
        return str(exc)
    return None


def _evaluate_node(node: ast.AST, context: Mapping[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return _numeric_value(node.value)

    if isinstance(node, ast.Name):
        return context[node.id]

    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left, context)
        right = _evaluate_node(node.right, context)
        try:
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        except (ArithmeticError, KeyError):
            raise FormulaError("Formula arithmetic failed.") from None
        return _numeric_value(result)

    if isinstance(node, ast.UnaryOp):
        try:
            result = _UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand, context))
        except (ArithmeticError, KeyError):
            raise FormulaError("Formula arithmetic failed.") from None
        return _numeric_value(result)

    if isinstance(node, ast.Call):
        arguments = [_evaluate_node(argument, context) for argument in node.args]
        function_name = node.func.id
        if function_name == "min":
            result = min(arguments)
        elif function_name == "max":
            result = max(arguments)
        else:
            result = max(arguments[1], min(arguments[0], arguments[2]))
        return _numeric_value(result)

    raise FormulaError("Formula syntax is not supported.")


def evaluate_formula(expr: str, context: Dict[str, Any]) -> Decimal:
    """Evaluate a validated numeric formula and return a ``Decimal`` result."""
    numeric_context = {
        name: _numeric_value(value)
        for name, value in context.items()
        if type(value) in SUPPORTED_NUMERIC_TYPES
    }
    tree = _parse_formula(expr, numeric_context.keys())
    return Decimal(str(_evaluate_node(tree, numeric_context)))
