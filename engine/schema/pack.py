"""
Domain pack Pydantic models — the contract between the engine and every domain.

The engine knows only these primitives. Domain knowledge lives entirely in
the JSON pack file. No domain-specific code exists in the engine.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

class Unit(BaseModel):
    kind: Literal["currency", "rate", "unit"] = "currency"
    code: str = "INR"
    decimals: int = 2


class EntityAttribute(BaseModel):
    key: str
    type: Literal["enum", "number", "integer", "string", "boolean"]
    values: Optional[List[Any]] = None
    min: Optional[float] = None
    max: Optional[float] = None

    @model_validator(mode="after")
    def validate_metadata(self) -> "EntityAttribute":
        if self.type == "enum" and not self.values:
            raise ValueError(f"Enum attribute '{self.key}' must define allowed values.")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"Attribute '{self.key}' min cannot exceed max.")
        return self


class Entity(BaseModel):
    name: str
    attributes: List[EntityAttribute] = Field(default_factory=list)


class Signal(BaseModel):
    key: str
    type: Literal["enum", "number", "integer", "string", "boolean"]
    values: Optional[List[Any]] = None      # for enum
    min: Optional[float] = None
    max: Optional[float] = None
    required: bool = False

    @model_validator(mode="after")
    def validate_metadata(self) -> "Signal":
        if self.type == "enum" and not self.values:
            raise ValueError(f"Enum signal '{self.key}' must define allowed values.")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"Signal '{self.key}' min cannot exceed max.")
        return self


# ---------------------------------------------------------------------------
# Base price
# ---------------------------------------------------------------------------

class BaseFixed(BaseModel):
    type: Literal["fixed"]
    value: float

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Fixed base value must be finite.")
        return value


class BaseTable(BaseModel):
    type: Literal["table"]
    by: str
    values: Dict[str, float]

    @field_validator("values")
    @classmethod
    def values_must_be_finite(cls, values: Dict[str, float]) -> Dict[str, float]:
        if not values:
            raise ValueError("Base table must define at least one value.")
        for key, value in values.items():
            if not math.isfinite(value):
                raise ValueError(f"Base table value for '{key}' must be finite.")
        return values


class BaseFormula(BaseModel):
    type: Literal["formula"]
    expr: str


Base = Union[BaseFixed, BaseTable, BaseFormula]


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

class SimpleCondition(BaseModel):
    signal: str
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "between"]
    value: Any


class AllCondition(BaseModel):
    all: List["Condition"]


class AnyCondition(BaseModel):
    any: List["Condition"]


class NotCondition(BaseModel):
    not_: "Condition" = Field(alias="not")

    model_config = {"populate_by_name": True}


Condition = Union[AllCondition, AnyCondition, NotCondition, SimpleCondition]

AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

class ActionMultiply(BaseModel):
    op: Literal["multiply"]
    value: float

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Action value must be finite.")
        return value


class ActionAdd(BaseModel):
    op: Literal["add"]
    value: float

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Action value must be finite.")
        return value


class ActionSubtract(BaseModel):
    op: Literal["subtract"]
    value: float

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Action value must be finite.")
        return value


class ActionSet(BaseModel):
    op: Literal["set"]
    value: float

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Action value must be finite.")
        return value


class ActionLookup(BaseModel):
    op: Literal["lookup"]
    by: str
    table: Dict[str, float]

    @field_validator("table")
    @classmethod
    def table_values_must_be_finite(cls, table: Dict[str, float]) -> Dict[str, float]:
        if not table:
            raise ValueError("Lookup table must define at least one value.")
        for key, value in table.items():
            if not math.isfinite(value):
                raise ValueError(f"Lookup table value for '{key}' must be finite.")
        return table


class ActionFormula(BaseModel):
    op: Literal["formula"]
    expr: str


Action = Union[
    ActionMultiply,
    ActionAdd,
    ActionSubtract,
    ActionSet,
    ActionLookup,
    ActionFormula,
]


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class Rule(BaseModel):
    id: str
    stage: str
    priority: int = 0
    when: Optional[Condition] = None    # None = always applies
    then: Action
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

StackingMode = Literal["first", "all", "max_discount", "min_discount", "sum"]


class Stage(BaseModel):
    id: str
    stacking: StackingMode = "all"
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

class ConstraintFloor(BaseModel):
    id: str
    type: Literal["floor"]
    expr: str           # e.g. "base * 0.70"  or a literal like "3000"


class ConstraintCeiling(BaseModel):
    id: str
    type: Literal["ceiling"]
    expr: str


class ConstraintMaxChangePct(BaseModel):
    id: str
    type: Literal["max_change_pct"]
    value: float        # e.g. 50.0 means ±50% from base

    @field_validator("value")
    @classmethod
    def value_must_be_non_negative_and_finite(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("max_change_pct value must be a non-negative finite number.")
        return value


Constraint = Union[ConstraintFloor, ConstraintCeiling, ConstraintMaxChangePct]


# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------

class Rounding(BaseModel):
    mode: Literal["nearest", "up", "down", "none"] = "nearest"
    step: float = 1.0

    @field_validator("step")
    @classmethod
    def step_must_be_positive_and_finite(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Rounding step must be a positive finite number.")
        return value


import re

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def is_valid_semver(version: str) -> bool:
    """Return True if version string adheres to Semantic Versioning 2.0.0."""
    if not isinstance(version, str):
        return False
    return bool(SEMVER_REGEX.match(version.strip()))


# ---------------------------------------------------------------------------
# Domain pack (top-level)
# ---------------------------------------------------------------------------

class DomainPack(BaseModel):
    pack_id: str
    version: str = "1.0.0"
    description: Optional[str] = None

    @field_validator("version")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        if not is_valid_semver(value):
            raise ValueError(
                f"Version '{value}' is not valid Semantic Versioning. Expected X.Y.Z (e.g. '1.0.0')."
            )
        return value.strip()


    unit: Unit = Field(default_factory=Unit)
    entity: Optional[Entity] = None
    signals: List[Signal] = Field(default_factory=list)

    base: Base
    stages: List[Stage] = Field(default_factory=list)
    rules: List[Rule] = Field(default_factory=list)
    constraints: List[Constraint] = Field(default_factory=list)
    rounding: Rounding = Field(default_factory=Rounding)

    @model_validator(mode="after")
    def validate_rule_stages(self) -> "DomainPack":
        stage_ids = {s.id for s in self.stages}
        for rule in self.rules:
            if rule.stage not in stage_ids:
                raise ValueError(
                    f"Rule '{rule.id}' references unknown stage '{rule.stage}'. "
                    f"Known stages: {sorted(stage_ids)}"
                )
        return self
