"""
Deterministic Pricing Engine — core runtime.

Pipeline:
  1. Resolve base price
  2. Evaluate stages (conditions → stacking → actions)
  3. Apply constraints (floor, ceiling, max_change_pct)
  4. Round
  5. Generate trace
  6. Generate fingerprint

No network calls. No randomness. No side effects.
"""
from __future__ import annotations

import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Any, Dict, List, Optional

from .schema.pack import (
    Base,
    BaseFixed,
    BaseFormula,
    BaseTable,
    ConstraintCeiling,
    ConstraintFloor,
    ConstraintMaxChangePct,
    DomainPack,
    Rule,
    Rounding,
    Stage,
)
from .evaluate.conditions import evaluate_condition
from .evaluate.actions import apply_action
from .evaluate.formula import FormulaError, evaluate_formula
from .trace.models import PriceTrace, TraceStep
from .fingerprint import generate_fingerprint


class PricingError(Exception):
    """Raised when the engine cannot compute a price."""


def _as_finite_decimal(value: Any, field_name: str) -> Decimal:
    """Convert an exact numeric input to Decimal and reject bool/NaN/infinity."""
    if type(value) not in (int, float, Decimal):
        raise PricingError(f"Signal '{field_name}' must be a finite number.")
    try:
        numeric = Decimal(str(value))
    except Exception:
        raise PricingError(f"Signal '{field_name}' must be a finite number.") from None
    if not numeric.is_finite():
        raise PricingError(f"Signal '{field_name}' must be a finite number.")
    return numeric


def _validate_signals(pack: DomainPack, signals: Dict[str, Any]) -> None:
    """Validate request signals against pack metadata before pricing starts."""
    if not isinstance(signals, dict):
        raise PricingError("Signals must be a JSON object.")

    signal_meta = {signal.key: signal for signal in pack.signals}
    known_keys = set(signal_meta)
    entity_meta = {}
    if pack.entity:
        entity_meta = {attribute.key: attribute for attribute in pack.entity.attributes}
        known_keys.update(entity_meta)

    unknown = sorted(set(signals) - known_keys)
    if unknown:
        raise PricingError(f"Unknown signal(s): {', '.join(unknown)}.")

    for signal in pack.signals:
        if signal.required and (signal.key not in signals or signals[signal.key] is None):
            raise PricingError(f"Missing required signal '{signal.key}'.")

    for key, value in signals.items():
        if value is None:
            raise PricingError(f"Signal '{key}' cannot be null.")
        meta = signal_meta.get(key) or entity_meta.get(key)
        if meta is None:
            continue

        if meta.type == "number":
            numeric = _as_finite_decimal(value, key)
            if meta.min is not None and numeric < Decimal(str(meta.min)):
                raise PricingError(f"Signal '{key}' must be >= {meta.min}.")
            if meta.max is not None and numeric > Decimal(str(meta.max)):
                raise PricingError(f"Signal '{key}' must be <= {meta.max}.")
        elif meta.type == "integer":
            if type(value) is not int:
                raise PricingError(f"Signal '{key}' must be an integer.")
            numeric = Decimal(value)
            if meta.min is not None and numeric < Decimal(str(meta.min)):
                raise PricingError(f"Signal '{key}' must be >= {meta.min}.")
            if meta.max is not None and numeric > Decimal(str(meta.max)):
                raise PricingError(f"Signal '{key}' must be <= {meta.max}.")
        elif meta.type == "boolean":
            if type(value) is not bool:
                raise PricingError(f"Signal '{key}' must be a boolean.")
        elif meta.type == "enum":
            allowed = meta.values or []
            if value not in allowed:
                raise PricingError(
                    f"Signal '{key}' must be one of: {', '.join(map(str, allowed))}."
                )
        elif meta.type == "string":
            if type(value) is not str:
                raise PricingError(f"Signal '{key}' must be a string.")


def _resolve_base(base: Base, signals: Dict[str, Any]) -> Decimal:
    """Resolve the base price from the pack configuration."""
    if isinstance(base, BaseFixed):
        return Decimal(str(base.value))

    if isinstance(base, BaseTable):
        key_val = signals.get(base.by)
        if key_val is None:
            raise PricingError(
                f"Base table key '{base.by}' not found in request signals."
            )
        table_val = base.values.get(str(key_val))
        if table_val is None:
            raise PricingError(
                f"Base table has no entry for '{base.by}={key_val}'. "
                f"Valid keys: {list(base.values.keys())}"
            )
        return Decimal(str(table_val))

    if isinstance(base, BaseFormula):
        context = dict(signals)
        try:
            return evaluate_formula(base.expr, context)
        except FormulaError as exc:
            raise PricingError(f"Base formula failed: {exc}") from None

    raise PricingError(f"Unknown base type: {type(base)}")


def _apply_stacking(
    stage: Stage,
    rules: List[Rule],
    current: Decimal,
    base: Decimal,
    signals: Dict[str, Any],
    trace: PriceTrace,
) -> Decimal:
    """
    Evaluate rules for a stage using the stage's stacking mode.

    Stacking modes:
      all          — apply every matching rule in priority order
      first        — apply the highest-priority matching rule only
      max_discount — apply only the rule that gives the largest discount
      min_discount — apply only the rule that gives the smallest discount
      sum          — sum all adjustments (additive only)
    """
    # Sort rules by priority descending, then id, so ties are deterministic.
    sorted_rules = sorted(rules, key=lambda r: (-r.priority, r.id))

    stacking = stage.stacking

    if stacking == "first":
        for rule in sorted_rules:
            if rule.when is None or evaluate_condition(rule.when, signals):
                before = current
                current = apply_action(rule.then, current, base, signals)
                trace.append(
                    TraceStep(
                        step=rule.id,
                        rule_id=rule.id,
                        stage=stage.id,
                        before=before,
                        after=current,
                        action=str(rule.then.op),
                        description=rule.description,
                        fired=True,
                    )
                )
                return current  # stop after first matching rule
            else:
                trace.append(
                    TraceStep(
                        step=rule.id,
                        rule_id=rule.id,
                        stage=stage.id,
                        before=current,
                        after=current,
                        action=str(rule.then.op),
                        description=rule.description,
                        fired=False,
                    )
                )
        return current

    if stacking == "all":
        for rule in sorted_rules:
            fired = rule.when is None or evaluate_condition(rule.when, signals)
            before = current
            if fired:
                current = apply_action(rule.then, current, base, signals)
            trace.append(
                TraceStep(
                    step=rule.id,
                    rule_id=rule.id,
                    stage=stage.id,
                    before=before,
                    after=current,
                    action=str(rule.then.op),
                    description=rule.description,
                    fired=fired,
                )
            )
        return current

    if stacking in ("max_discount", "min_discount"):
        candidates: List[tuple] = []  # (delta, rule, new_price)
        for rule in sorted_rules:
            if rule.when is None or evaluate_condition(rule.when, signals):
                new_price = apply_action(rule.then, current, base, signals)
                delta = new_price - current
                candidates.append((delta, rule, new_price))
            else:
                trace.append(
                    TraceStep(
                        step=rule.id,
                        rule_id=rule.id,
                        stage=stage.id,
                        before=current,
                        after=current,
                        action=str(rule.then.op),
                        description=rule.description,
                        fired=False,
                    )
                )

        if not candidates:
            return current

        if stacking == "max_discount":
            # Pick the rule with the most negative delta (largest discount)
            chosen_delta, chosen_rule, chosen_price = min(candidates, key=lambda x: x[0])
        else:
            # Pick the rule with the least negative (or most positive) delta
            chosen_delta, chosen_rule, chosen_price = max(candidates, key=lambda x: x[0])

        for delta, rule, new_price in candidates:
            fired = rule.id == chosen_rule.id
            trace.append(
                TraceStep(
                    step=rule.id,
                    rule_id=rule.id,
                    stage=stage.id,
                    before=current,
                    after=chosen_price if fired else current,
                    action=str(rule.then.op),
                    description=rule.description,
                    fired=fired,
                )
            )
        return chosen_price

    if stacking == "sum":
        total_adjustment = Decimal("0")
        for rule in sorted_rules:
            fired = rule.when is None or evaluate_condition(rule.when, signals)
            if fired:
                new_price = apply_action(rule.then, current, base, signals)
                adjustment = new_price - current
                total_adjustment += adjustment
                trace.append(
                    TraceStep(
                        step=rule.id,
                        rule_id=rule.id,
                        stage=stage.id,
                        before=current,
                        after=current + adjustment,
                        action=str(rule.then.op),
                        description=rule.description,
                        fired=True,
                    )
                )
            else:
                trace.append(
                    TraceStep(
                        step=rule.id,
                        rule_id=rule.id,
                        stage=stage.id,
                        before=current,
                        after=current,
                        action=str(rule.then.op),
                        description=rule.description,
                        fired=False,
                    )
                )
        return current + total_adjustment

    raise PricingError(f"Unknown stacking mode: {stacking}")


def _apply_constraints(
    pack: DomainPack,
    price: Decimal,
    base: Decimal,
    signals: Dict[str, Any],
    trace: PriceTrace,
) -> Decimal:
    """Apply floor, ceiling, and rate constraints."""
    _check_constraint_bounds(pack, price, base, signals)
    for constraint in pack.constraints:
        before = price

        if isinstance(constraint, ConstraintFloor):
            context = dict(signals)
            context["base"] = float(base)
            context["current"] = float(price)
            try:
                floor_val = evaluate_formula(constraint.expr, context)
            except FormulaError as exc:
                raise PricingError(f"Constraint '{constraint.id}' failed: {exc}") from None
            if price < floor_val:
                price = floor_val
            trace.append(
                TraceStep(
                    step=f"constraint:{constraint.id}",
                    rule_id=constraint.id,
                    stage="constraints",
                    before=before,
                    after=price,
                    action="floor",
                    description=f"Floor: {constraint.expr}",
                    fired=price != before,
                )
            )

        elif isinstance(constraint, ConstraintCeiling):
            context = dict(signals)
            context["base"] = float(base)
            context["current"] = float(price)
            try:
                ceiling_val = evaluate_formula(constraint.expr, context)
            except FormulaError as exc:
                raise PricingError(f"Constraint '{constraint.id}' failed: {exc}") from None
            if price > ceiling_val:
                price = ceiling_val
            trace.append(
                TraceStep(
                    step=f"constraint:{constraint.id}",
                    rule_id=constraint.id,
                    stage="constraints",
                    before=before,
                    after=price,
                    action="ceiling",
                    description=f"Ceiling: {constraint.expr}",
                    fired=price != before,
                )
            )

        elif isinstance(constraint, ConstraintMaxChangePct):
            max_pct = Decimal(str(constraint.value)) / Decimal("100")
            min_allowed = base * (1 - max_pct)
            max_allowed = base * (1 + max_pct)
            price = max(min_allowed, min(price, max_allowed))
            trace.append(
                TraceStep(
                    step=f"constraint:{constraint.id}",
                    rule_id=constraint.id,
                    stage="constraints",
                    before=before,
                    after=price,
                    action="max_change_pct",
                    description=f"Max change ±{constraint.value}%",
                    fired=price != before,
                )
            )

    return price


def _constraint_bounds(
    pack: DomainPack,
    price: Decimal,
    base: Decimal,
    signals: Dict[str, Any],
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    lower: Optional[Decimal] = None
    upper: Optional[Decimal] = None
    for constraint in pack.constraints:
        if isinstance(constraint, ConstraintFloor):
            context = dict(signals)
            context["base"] = float(base)
            context["current"] = float(price)
            try:
                value = evaluate_formula(constraint.expr, context)
            except FormulaError as exc:
                raise PricingError(f"Constraint '{constraint.id}' failed: {exc}") from None
            lower = value if lower is None else max(lower, value)
        elif isinstance(constraint, ConstraintCeiling):
            context = dict(signals)
            context["base"] = float(base)
            context["current"] = float(price)
            try:
                value = evaluate_formula(constraint.expr, context)
            except FormulaError as exc:
                raise PricingError(f"Constraint '{constraint.id}' failed: {exc}") from None
            upper = value if upper is None else min(upper, value)
        elif isinstance(constraint, ConstraintMaxChangePct):
            max_pct = Decimal(str(constraint.value)) / Decimal("100")
            min_allowed = base * (1 - max_pct)
            max_allowed = base * (1 + max_pct)
            lower = min_allowed if lower is None else max(lower, min_allowed)
            upper = max_allowed if upper is None else min(upper, max_allowed)
    return lower, upper


def _check_constraint_bounds(
    pack: DomainPack,
    price: Decimal,
    base: Decimal,
    signals: Dict[str, Any],
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    lower, upper = _constraint_bounds(pack, price, base, signals)
    if lower is not None and upper is not None and lower > upper:
        raise PricingError(
            f"Conflicting constraints: effective floor {lower} exceeds effective ceiling {upper}."
        )
    return lower, upper


def _enforce_post_rounding_constraints(
    pack: DomainPack,
    price: Decimal,
    base: Decimal,
    signals: Dict[str, Any],
    trace: PriceTrace,
) -> Decimal:
    """Re-clamp after rounding so final output cannot violate guardrails."""
    lower, upper = _check_constraint_bounds(pack, price, base, signals)
    before = price
    if lower is not None and price < lower:
        price = lower
    if upper is not None and price > upper:
        price = upper
    if price != before:
        trace.append(
            TraceStep(
                step="post_rounding_constraints",
                rule_id=None,
                stage="constraints",
                before=before,
                after=price,
                action="enforce_final_constraints",
                description="Final constraints enforced after rounding",
                fired=True,
            )
        )
    return price


def _apply_rounding(rounding: Rounding, price: Decimal) -> Decimal:
    """Apply rounding to the final price."""
    step = Decimal(str(rounding.step))
    if rounding.mode == "none":
        return price
    if rounding.mode == "nearest":
        return (price / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
    if rounding.mode == "up":
        return (price / step).quantize(Decimal("1"), rounding=ROUND_UP) * step
    if rounding.mode == "down":
        return (price / step).quantize(Decimal("1"), rounding=ROUND_DOWN) * step
    raise PricingError(f"Unknown rounding mode: {rounding.mode}")


class PriceResult:
    """The output of the engine for a single pricing request."""

    def __init__(
        self,
        price: Decimal,
        base: Decimal,
        trace: PriceTrace,
        fingerprint: str,
        pack_id: str,
        pack_version: str,
    ):
        self.price = price
        self.base = base
        self.trace = trace
        self.fingerprint = fingerprint
        self.pack_id = pack_id
        self.pack_version = pack_version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": float(self.price),
            "base": float(self.base),
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "fingerprint": self.fingerprint,
            "trace": self.trace.to_list(),
        }


def compute_price(pack: DomainPack, signals: Dict[str, Any]) -> PriceResult:
    """
    Main engine entry point — fully deterministic.

    Args:
        pack:    A validated, published DomainPack.
        signals: Input signal values from the pricing request.

    Returns:
        PriceResult with price, trace, and fingerprint.
    """
    trace = PriceTrace()
    _validate_signals(pack, signals)

    # 1. Resolve base price
    base = _resolve_base(pack.base, signals)
    trace.append(
        TraceStep(
            step="base",
            rule_id=None,
            stage="base",
            before=None,
            after=base,
            action="resolve_base",
            description="Base price resolved",
            fired=True,
        )
    )

    current = base

    # 2. Evaluate stages in order
    for stage in pack.stages:
        # Collect rules belonging to this stage
        stage_rules = [r for r in pack.rules if r.stage == stage.id]
        if not stage_rules:
            continue
        try:
            current = _apply_stacking(stage, stage_rules, current, base, signals, trace)
        except (FormulaError, ValueError) as exc:
            raise PricingError(f"Rule evaluation failed: {exc}") from None

    # 3. Apply constraints before rounding
    current = _apply_constraints(pack, current, base, signals, trace)

    # 4. Round, then re-enforce constraints so rounding cannot break caps/floors
    before_round = current
    current = _apply_rounding(pack.rounding, current)
    trace.append(
        TraceStep(
            step="rounding",
            rule_id=None,
            stage="rounding",
            before=before_round,
            after=current,
            action=f"round({pack.rounding.mode}, step={pack.rounding.step})",
            description="Final rounding applied",
            fired=True,
        )
    )
    current = _enforce_post_rounding_constraints(pack, current, base, signals, trace)

    # 5. Generate fingerprint
    fingerprint = generate_fingerprint(
        pack_id=pack.pack_id,
        pack_version=pack.version,
        input_signals=signals,
        price=current,
        trace_steps=trace.to_list(),
    )

    return PriceResult(
        price=current,
        base=base,
        trace=trace,
        fingerprint=fingerprint,
        pack_id=pack.pack_id,
        pack_version=pack.version,
    )
