"""
Validation layer — runs before publish.

Checks:
  C1 — unknown signal
  C2 — invalid operator
  C3 — invalid value range
  C4 — invalid action
  C5 — overlapping rules in same stage
  C6 — missing ceiling/floor warning
  C7 — unsupported formula function
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..schema.pack import (
    DomainPack,
    Rule,
    Condition,
    SimpleCondition,
    AllCondition,
    AnyCondition,
    NotCondition,
    ActionFormula,
    ConstraintCeiling,
    ConstraintFloor,
)
from ..evaluate.formula import SUPPORTED_FORMULA_FUNCTIONS, validate_formula


ALLOWED_FORMULA_FUNCTIONS = set(SUPPORTED_FORMULA_FUNCTIONS)
VALID_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "between"}


@dataclass
class ValidationError:
    code: str
    message: str
    rule_ids: List[str] = field(default_factory=list)
    severity: str = "error"  # "error" | "warning"


@dataclass
class ValidationResult:
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [
                {
                    "code": e.code,
                    "message": e.message,
                    "rule_ids": e.rule_ids,
                    "severity": e.severity,
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "code": w.code,
                    "message": w.message,
                    "rule_ids": w.rule_ids,
                    "severity": w.severity,
                }
                for w in self.warnings
            ],
        }


def _collect_signals_from_condition(cond: Condition) -> List[str]:
    """Recursively collect all signal keys referenced in a condition."""
    if isinstance(cond, SimpleCondition):
        return [cond.signal]
    elif isinstance(cond, AllCondition):
        signals = []
        for c in cond.all:
            signals.extend(_collect_signals_from_condition(c))
        return signals
    elif isinstance(cond, AnyCondition):
        signals = []
        for c in cond.any:
            signals.extend(_collect_signals_from_condition(c))
        return signals
    elif isinstance(cond, NotCondition):
        return _collect_signals_from_condition(cond.not_)
    return []


def _collect_ops_from_condition(cond: Condition) -> List[tuple]:
    """Recursively collect (signal, op, value) from a condition."""
    if isinstance(cond, SimpleCondition):
        return [(cond.signal, cond.op, cond.value)]
    elif isinstance(cond, AllCondition):
        items = []
        for c in cond.all:
            items.extend(_collect_ops_from_condition(c))
        return items
    elif isinstance(cond, AnyCondition):
        items = []
        for c in cond.any:
            items.extend(_collect_ops_from_condition(c))
        return items
    elif isinstance(cond, NotCondition):
        return _collect_ops_from_condition(cond.not_)
    return []


def _check_formula(expr: str, allowed_names: set[str]) -> Optional[str]:
    """Return a shared grammar error for an invalid formula."""
    return validate_formula(expr, allowed_names)


def _numeric_formula_names(pack: DomainPack) -> set[str]:
    """Return signal and entity names that can safely be formula variables."""
    names = {signal.key for signal in pack.signals if signal.type in {"number", "integer"}}
    if pack.entity:
        names.update(
            attribute.key
            for attribute in pack.entity.attributes
            if attribute.type in {"number", "integer"}
        )
    return names


def _rules_overlap(r1: Rule, r2: Rule) -> bool:
    """
    Heuristic overlap detection: two numeric threshold rules overlap when
    they reference the same signal with overlapping ranges.
    """
    if r1.when is None or r2.when is None:
        return False

    ops1 = _collect_ops_from_condition(r1.when)
    ops2 = _collect_ops_from_condition(r2.when)

    # Build a per-signal numeric range map
    def to_range(ops):
        ranges = {}
        for sig, op, val in ops:
            if op in ("gt", "gte"):
                ranges.setdefault(sig, {})["low"] = float(val)
            elif op in ("lt", "lte"):
                ranges.setdefault(sig, {})["high"] = float(val)
            elif op == "between":
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    ranges.setdefault(sig, {})["low"] = float(val[0])
                    ranges[sig]["high"] = float(val[1])
        return ranges

    range1 = to_range(ops1)
    range2 = to_range(ops2)

    for sig in range1:
        if sig not in range2:
            continue
        lo1 = range1[sig].get("low", float("-inf"))
        hi1 = range1[sig].get("high", float("inf"))
        lo2 = range2[sig].get("low", float("-inf"))
        hi2 = range2[sig].get("high", float("inf"))
        # Ranges overlap if lo1 < hi2 and lo2 < hi1
        if lo1 < hi2 and lo2 < hi1:
            return True
    return False


def validate_pack(pack: DomainPack) -> ValidationResult:
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []

    # --- Safety Limits: rule count, stage count, signal count, constraint count ---
    MAX_RULES_PER_PACK = 500
    MAX_STAGES_PER_PACK = 50
    MAX_SIGNALS_PER_PACK = 100
    MAX_CONSTRAINTS_PER_PACK = 50

    if len(pack.rules) > MAX_RULES_PER_PACK:
        errors.append(
            ValidationError(
                code="C-LIMIT",
                message=f"Rule count ({len(pack.rules)}) exceeds maximum allowed ({MAX_RULES_PER_PACK}).",
            )
        )
    if len(pack.stages) > MAX_STAGES_PER_PACK:
        errors.append(
            ValidationError(
                code="C-LIMIT",
                message=f"Stage count ({len(pack.stages)}) exceeds maximum allowed ({MAX_STAGES_PER_PACK}).",
            )
        )
    if len(pack.signals) > MAX_SIGNALS_PER_PACK:
        errors.append(
            ValidationError(
                code="C-LIMIT",
                message=f"Signal count ({len(pack.signals)}) exceeds maximum allowed ({MAX_SIGNALS_PER_PACK}).",
            )
        )
    if len(pack.constraints) > MAX_CONSTRAINTS_PER_PACK:
        errors.append(
            ValidationError(
                code="C-LIMIT",
                message=f"Constraint count ({len(pack.constraints)}) exceeds maximum allowed ({MAX_CONSTRAINTS_PER_PACK}).",
            )
        )

    known_signals = {s.key for s in pack.signals}
    # Also allow entity attributes as signals
    if pack.entity:
        for attr in pack.entity.attributes:
            known_signals.add(attr.key)

    # --- C1: Unknown signals in rule conditions ---
    for rule in pack.rules:
        if rule.when is None:
            continue
        refs = _collect_signals_from_condition(rule.when)
        for sig in refs:
            if sig not in known_signals:
                errors.append(
                    ValidationError(
                        code="C1",
                        message=f"Rule '{rule.id}' references unknown signal '{sig}'.",
                        rule_ids=[rule.id],
                    )
                )

    # --- C1b: lookup action 'by' must reference a known signal ---
    for rule in pack.rules:
        from ..schema.pack import ActionLookup
        if isinstance(rule.then, ActionLookup):
            if rule.then.by not in known_signals:
                errors.append(
                    ValidationError(
                        code="C1",
                        message=f"Rule '{rule.id}' lookup references unknown signal '{rule.then.by}'.",
                        rule_ids=[rule.id],
                    )
                )

    # --- C2: Invalid operator (already enforced by Pydantic, but double-check) ---
    for rule in pack.rules:
        if rule.when is None:
            continue
        ops = _collect_ops_from_condition(rule.when)
        for sig, op, val in ops:
            if op not in VALID_OPS:
                errors.append(
                    ValidationError(
                        code="C2",
                        message=f"Rule '{rule.id}' uses invalid operator '{op}'.",
                        rule_ids=[rule.id],
                    )
                )

    # --- C3: Numeric signal range validation ---
    signal_meta = {s.key: s for s in pack.signals}
    for rule in pack.rules:
        if rule.when is None:
            continue
        ops = _collect_ops_from_condition(rule.when)
        for sig, op, val in ops:
            if sig not in signal_meta:
                continue
            smeta = signal_meta[sig]
            vals_to_check = val if isinstance(val, list) else [val]
            for v in vals_to_check:
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if smeta.min is not None and fv < smeta.min:
                    errors.append(
                        ValidationError(
                            code="C3",
                            message=(
                                f"Rule '{rule.id}': signal '{sig}' value {fv} is below "
                                f"declared min {smeta.min}."
                            ),
                            rule_ids=[rule.id],
                        )
                    )
                if smeta.max is not None and fv > smeta.max:
                    errors.append(
                        ValidationError(
                            code="C3",
                            message=(
                                f"Rule '{rule.id}': signal '{sig}' value {fv} exceeds "
                                f"declared max {smeta.max}."
                            ),
                            rule_ids=[rule.id],
                        )
                    )

    # --- C4: Formula actions use only numeric names and allowed functions ---
    numeric_formula_names = _numeric_formula_names(pack)
    formula_names = numeric_formula_names | {"base", "current"}
    for rule in pack.rules:
        if isinstance(rule.then, ActionFormula):
            err = _check_formula(rule.then.expr, formula_names)
            if err:
                errors.append(
                    ValidationError(
                        code="C7",
                        message=f"Rule '{rule.id}': {err}",
                        rule_ids=[rule.id],
                    )
                )
    from ..schema.pack import BaseFormula
    if isinstance(pack.base, BaseFormula):
        err = _check_formula(pack.base.expr, numeric_formula_names)
        if err:
            errors.append(
                ValidationError(
                    code="C7",
                    message=f"Base formula: {err}",
                )
            )

    # --- C7: Constraint formulas use the same grammar as runtime evaluation ---
    for constraint in pack.constraints:
        if not isinstance(constraint, (ConstraintFloor, ConstraintCeiling)):
            continue
        err = _check_formula(
            constraint.expr,
            numeric_formula_names | {"base", "current"},
        )
        if err:
            errors.append(
                ValidationError(
                    code="C7",
                    message=f"Constraint '{constraint.id}': {err}",
                )
            )

    # --- C5: Overlapping rules in same stage ---
    stage_rules: Dict[str, List[Rule]] = {}
    for rule in pack.rules:
        stage_rules.setdefault(rule.stage, []).append(rule)

    for stage_id, rules in stage_rules.items():
        # Find the stacking mode for this stage
        stacking = "all"
        for s in pack.stages:
            if s.id == stage_id:
                stacking = s.stacking
                break

        if stacking in ("first",):
            # Only the highest-priority rule fires — ordering matters.
            # Warn if two rules have the same priority AND could both match.
            by_priority: Dict[int, List[Rule]] = {}
            for r in rules:
                by_priority.setdefault(r.priority, []).append(r)
            for prio, same_prio_rules in by_priority.items():
                if len(same_prio_rules) < 2:
                    continue
                for i in range(len(same_prio_rules)):
                    for j in range(i + 1, len(same_prio_rules)):
                        if _rules_overlap(same_prio_rules[i], same_prio_rules[j]):
                            errors.append(
                                ValidationError(
                                    code="C5",
                                    message=(
                                        f"Rules '{same_prio_rules[i].id}' and "
                                        f"'{same_prio_rules[j].id}' in stage '{stage_id}' "
                                        f"(stacking=first) have equal priority {prio} and "
                                        f"overlapping conditions. Add explicit ordering."
                                    ),
                                    rule_ids=[same_prio_rules[i].id, same_prio_rules[j].id],
                                )
                            )
        else:
            # For 'all' stacking, overlapping numeric ranges are a warning not an error.
            for i in range(len(rules)):
                for j in range(i + 1, len(rules)):
                    if _rules_overlap(rules[i], rules[j]):
                        warnings.append(
                            ValidationError(
                                code="C5",
                                message=(
                                    f"Rules '{rules[i].id}' and '{rules[j].id}' in stage "
                                    f"'{stage_id}' have overlapping conditions. Both will "
                                    f"fire under stacking='{stacking}'."
                                ),
                                rule_ids=[rules[i].id, rules[j].id],
                                severity="warning",
                            )
                        )

    # --- C6: Missing floor or ceiling warning ---
    constraint_types = {c.type for c in pack.constraints}
    if "floor" not in constraint_types:
        warnings.append(
            ValidationError(
                code="C6",
                message="No floor constraint defined. Price may fall arbitrarily low.",
                severity="warning",
            )
        )
    if "ceiling" not in constraint_types:
        warnings.append(
            ValidationError(
                code="C6",
                message="No ceiling constraint defined. Price may rise without bound.",
                severity="warning",
            )
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
