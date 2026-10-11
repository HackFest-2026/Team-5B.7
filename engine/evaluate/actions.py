"""
Action executor — applies a single rule's action to the current price.

Returns the new price as a Decimal. All arithmetic uses Decimal for
monetary correctness.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from ..schema.pack import (
    Action,
    ActionMultiply,
    ActionAdd,
    ActionSubtract,
    ActionSet,
    ActionLookup,
    ActionFormula,
)
from .formula import evaluate_formula


def apply_action(
    action: Action,
    current: Decimal,
    base: Decimal,
    signals: Dict[str, Any],
) -> Decimal:
    """Apply an action to the current price. Returns new price."""
    if isinstance(action, ActionMultiply):
        return current * Decimal(str(action.value))

    if isinstance(action, ActionAdd):
        return current + Decimal(str(action.value))

    if isinstance(action, ActionSubtract):
        return current - Decimal(str(action.value))

    if isinstance(action, ActionSet):
        return Decimal(str(action.value))

    if isinstance(action, ActionLookup):
        key_val = signals.get(action.by)
        if key_val is None:
            return current
        lookup_val = action.table.get(str(key_val))
        if lookup_val is None:
            return current
        return current + Decimal(str(lookup_val))

    if isinstance(action, ActionFormula):
        context = dict(signals)
        context["base"] = float(base)
        context["current"] = float(current)
        result = evaluate_formula(action.expr, context)
        return result

    raise ValueError(f"Unknown action type: {type(action)}")
