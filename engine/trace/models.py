"""
Trace data structures.

The trace is the actual execution log of the engine — not an LLM
explanation. Every price is fully explained by its trace.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, List, Optional


@dataclass
class TraceStep:
    step: str
    rule_id: Optional[str]
    stage: Optional[str]
    before: Optional[Decimal]
    after: Decimal
    action: Optional[str] = None
    description: Optional[str] = None
    fired: bool = True  # False if condition not met (skipped rule)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "rule_id": self.rule_id,
            "stage": self.stage,
            "before": float(self.before) if self.before is not None else None,
            "after": float(self.after),
            "action": self.action,
            "description": self.description,
            "fired": self.fired,
        }


@dataclass
class PriceTrace:
    steps: List[TraceStep] = field(default_factory=list)

    def append(self, step: TraceStep) -> None:
        self.steps.append(step)

    def to_list(self) -> List[dict]:
        return [s.to_dict() for s in self.steps]
