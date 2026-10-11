import json
from decimal import Decimal
from pathlib import Path

import pytest

from engine.evaluate.formula import (
    FormulaError,
    _numeric_value,
    evaluate_formula,
    validate_formula,
)
from engine.schema.pack import DomainPack
from engine.validate import validate_pack


ROOT = Path(__file__).parent.parent.parent


def test_supported_arithmetic_and_functions():
    context = {"base": 100, "current": 80, "discount": 15}

    assert evaluate_formula("base + current * 2 - discount / 5", context) == Decimal("257.0")
    assert evaluate_formula("min(base, current, discount)", context) == Decimal("15.0")
    assert evaluate_formula("max(base, current, discount)", context) == Decimal("100.0")
    assert evaluate_formula("clamp(base - current, 0, discount)", context) == Decimal("15.0")
    assert evaluate_formula("-(base - current)", context) == Decimal("-20.0")


@pytest.mark.parametrize("value", [True, False, object(), float("nan"), float("inf"), float("-inf")])
def test_numeric_value_rejects_unsupported_values(value):
    with pytest.raises(FormulaError):
        _numeric_value(value)


def test_numeric_value_rejects_custom_numeric_subclasses():
    class CustomFloat(float):
        pass

    class CustomDecimal(Decimal):
        pass

    with pytest.raises(FormulaError):
        _numeric_value(CustomFloat(1.0))
    with pytest.raises(FormulaError):
        _numeric_value(CustomDecimal("1.0"))


@pytest.mark.parametrize("value", [1, 1.25, Decimal("1.25")])
def test_numeric_value_accepts_supported_numeric_types(value):
    assert _numeric_value(value) == float(value)


def test_numeric_context_rejects_custom_numeric_subclasses():
    class CustomInt(int):
        pass

    with pytest.raises(FormulaError):
        evaluate_formula("value", {"value": CustomInt(1)})


@pytest.mark.parametrize(
    "expression",
    [
        "unknown + 1",
        "pow(base, 2)",
        "abs(base)",
        "round(base)",
        "math.sqrt(base)",
        "base.__class__",
        "base[0]",
        "lambda: base",
        "[value for value in base]",
        "__import__('os')",
    ],
)
def test_unsupported_formula_syntax_is_rejected_before_execution(expression):
    with pytest.raises(FormulaError):
        evaluate_formula(expression, {"base": 100})


@pytest.mark.parametrize("expression", ["1 / 0", "1e309", "base * 1e309"])
def test_invalid_numeric_results_are_rejected(expression):
    with pytest.raises(FormulaError):
        evaluate_formula(expression, {"base": 100})


@pytest.mark.parametrize(
    "expression",
    [
        "min(base)",
        "max(base)",
        "clamp(base, 0)",
        "clamp(value=base, low=0, high=10)",
    ],
)
def test_invalid_function_arguments_are_rejected(expression):
    with pytest.raises(FormulaError):
        evaluate_formula(expression, {"base": 100})


def test_formula_length_node_and_depth_limits_are_enforced():
    too_long = "1" + " + 1" * 130
    too_many_nodes = " + ".join(["1"] * 40)
    too_deep = "1"
    for _ in range(20):
        too_deep = f"-({too_deep})"

    for expression in [too_long, too_many_nodes, too_deep]:
        with pytest.raises(FormulaError):
            evaluate_formula(expression, {})


def test_validator_and_runtime_share_formula_policy():
    valid = {"op": "formula", "expr": "min(base, current) + clamp(discount, 0, 10)"}
    invalid = {"op": "formula", "expr": "abs(current)"}
    pack_data = {
        "pack_id": "formula-test",
        "signals": [
            {"key": "discount", "type": "number", "min": 0, "max": 100},
        ],
        "base": {"type": "fixed", "value": 100},
        "stages": [{"id": "main", "stacking": "all"}],
        "rules": [
            {"id": "valid", "stage": "main", "then": valid},
            {"id": "invalid", "stage": "main", "then": invalid},
        ],
        "constraints": [],
    }
    pack = DomainPack.model_validate(pack_data)
    result = validate_pack(pack)

    assert validate_formula(valid["expr"], {"base", "current", "discount"}) is None
    assert validate_formula(invalid["expr"], {"base", "current", "discount"}) is not None
    assert any(error.rule_ids == ["invalid"] for error in result.errors)
    assert evaluate_formula(valid["expr"], {"base": 100, "current": 80, "discount": 15}) == Decimal("90.0")
    with pytest.raises(FormulaError):
        evaluate_formula(invalid["expr"], {"base": 100, "current": 80, "discount": 15})


@pytest.mark.parametrize("signal_type", ["enum", "string", "boolean"])
def test_validator_rejects_nonnumeric_formula_signals(signal_type):
    pack_data = {
        "pack_id": f"{signal_type}-formula-test",
        "signals": [
            {"key": "value", "type": signal_type, "values": ["a", "b"]}
            if signal_type == "enum"
            else {"key": "value", "type": signal_type},
        ],
        "base": {"type": "fixed", "value": 100},
        "stages": [{"id": "main", "stacking": "all"}],
        "rules": [
            {
                "id": "formula",
                "stage": "main",
                "then": {"op": "formula", "expr": "value + 1"},
            }
        ],
        "constraints": [],
    }

    result = validate_pack(DomainPack.model_validate(pack_data))

    assert result.valid is False
    assert any(error.code == "C7" for error in result.errors)


def test_validator_accepts_numeric_signals_and_base_price_names():
    pack_data = {
        "pack_id": "numeric-formula-test",
        "signals": [{"key": "value", "type": "number"}],
        "base": {"type": "fixed", "value": 100},
        "stages": [{"id": "main", "stacking": "all"}],
        "rules": [
            {
                "id": "formula",
                "stage": "main",
                "then": {"op": "formula", "expr": "base + current + value"},
            }
        ],
        "constraints": [
            {"id": "floor", "type": "floor", "expr": "base * 0.5"},
            {"id": "ceiling", "type": "ceiling", "expr": "current + value"},
        ],
    }

    result = validate_pack(DomainPack.model_validate(pack_data))

    assert result.valid is True


def test_validator_rejects_unknown_formula_names():
    pack_data = {
        "pack_id": "unknown-formula-test",
        "signals": [{"key": "value", "type": "number"}],
        "base": {"type": "fixed", "value": 100},
        "stages": [{"id": "main", "stacking": "all"}],
        "rules": [
            {
                "id": "formula",
                "stage": "main",
                "then": {"op": "formula", "expr": "missing + value"},
            }
        ],
        "constraints": [],
    }

    result = validate_pack(DomainPack.model_validate(pack_data))

    assert result.valid is False
    assert any("missing" in error.message for error in result.errors)


@pytest.mark.parametrize("expression", ["abs(base)", "base[0]", "base +"])
def test_validator_rejects_invalid_constraint_formulas(expression):
    pack_data = {
        "pack_id": "constraint-formula-test",
        "base": {"type": "fixed", "value": 100},
        "stages": [],
        "rules": [],
        "constraints": [{"id": "floor", "type": "floor", "expr": expression}],
    }

    result = validate_pack(DomainPack.model_validate(pack_data))

    assert result.valid is False
    assert any(error.code == "C7" and "Constraint 'floor'" in error.message for error in result.errors)


def test_validator_accepts_valid_constraint_formula():
    pack_data = {
        "pack_id": "valid-constraint-formula-test",
        "base": {"type": "fixed", "value": 100},
        "stages": [],
        "rules": [],
        "constraints": [
            {"id": "floor", "type": "floor", "expr": "base * 0.5"},
            {"id": "ceiling", "type": "ceiling", "expr": "base * 2"},
        ],
    }

    result = validate_pack(DomainPack.model_validate(pack_data))

    assert result.valid is True


def test_existing_pack_formulas_remain_compatible():
    expected = {
        "ecommerce": [("mrp", {"mrp": 1000}, Decimal("1000.0"))],
        "hospitality": [
            ("base * 0.70", {"base": 4500}, Decimal("3150.0")),
            ("base * 2.50", {"base": 4500}, Decimal("11250.0")),
        ],
    }

    for pack_id, formulas in expected.items():
        pack = json.loads((ROOT / "packs" / f"{pack_id}.json").read_text(encoding="utf-8"))
        if pack_id == "ecommerce":
            expression = pack["base"]["expr"]
            assert evaluate_formula(expression, formulas[0][1]) == formulas[0][2]
        else:
            for expression, context, expected_value in formulas:
                assert evaluate_formula(expression, context) == expected_value


def test_all_shipped_pack_formulas_are_supported():
    contexts = {
        "banking": {},
        "ecommerce": {"mrp": 1000, "base": 1000},
        "ev_charging": {},
        "hospitality": {"base": 4500},
        "airline": {"base_fare": 100, "distance_km": 500, "base": 140},
    }

    for pack_file in (ROOT / "packs").glob("*.json"):
        pack = json.loads(pack_file.read_text(encoding="utf-8"))
        formulas = []
        if pack["base"]["type"] == "formula":
            formulas.append(pack["base"]["expr"])
        formulas.extend(constraint["expr"] for constraint in pack["constraints"] if "expr" in constraint)

        for expression in formulas:
            assert validate_formula(expression, contexts[pack["pack_id"]].keys()) is None
            evaluate_formula(expression, contexts[pack["pack_id"]])
