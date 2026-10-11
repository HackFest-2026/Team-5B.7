"""
Condition evaluator — pure deterministic logic.

No randomness. No external calls. All values are resolved from the
signal input dict.
"""
from __future__ import annotations

from typing import Any, Dict

from ..schema.pack import (
    Condition,
    SimpleCondition,
    AllCondition,
    AnyCondition,
    NotCondition,
)


def evaluate_condition(cond: Condition, signals: Dict[str, Any]) -> bool:
    """Return True if the condition is satisfied given the signal values."""
    if isinstance(cond, AllCondition):
        return all(evaluate_condition(c, signals) for c in cond.all)

    if isinstance(cond, AnyCondition):
        return any(evaluate_condition(c, signals) for c in cond.any)

    if isinstance(cond, NotCondition):
        return not evaluate_condition(cond.not_, signals)

    if isinstance(cond, SimpleCondition):
        return _eval_simple(cond, signals)

    raise ValueError(f"Unknown condition type: {type(cond)}")


def _eval_simple(cond: SimpleCondition, signals: Dict[str, Any]) -> bool:
    """Evaluate a single comparison."""
    key = cond.signal
    op = cond.op
    threshold = cond.value

    if key not in signals:
        return False

    actual = signals[key]

    if op == "eq":
        return actual == threshold
    if op == "neq":
        return actual != threshold
    if op == "gt":
        return _numeric(actual) > _numeric(threshold)
    if op == "gte":
        return _numeric(actual) >= _numeric(threshold)
    if op == "lt":
        return _numeric(actual) < _numeric(threshold)
    if op == "lte":
        return _numeric(actual) <= _numeric(threshold)
    if op == "in":
        if not isinstance(threshold, (list, tuple)):
            threshold = [threshold]
        return actual in threshold
    if op == "between":
        lo, hi = threshold[0], threshold[1]
        return _numeric(lo) <= _numeric(actual) <= _numeric(hi)

    raise ValueError(f"Unknown operator: {op}")


def _numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Cannot compare non-numeric value: {value!r}")
