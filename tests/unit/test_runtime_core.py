import json
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from api.main import app
from api.routes import pricing as pricing_routes
from cli import main
from engine.runtime import PricingError, compute_price
from engine.schema.pack import DomainPack


def _pack(name: str) -> DomainPack:
    return DomainPack.model_validate(json.loads((ROOT / "packs" / f"{name}.json").read_text()))


def _minimal_pack(**overrides) -> DomainPack:
    data = {
        "pack_id": "runtime-test",
        "signals": [{"key": "x", "type": "number", "min": 0, "max": 1000, "required": True}],
        "base": {"type": "formula", "expr": "x"},
        "stages": [],
        "rules": [],
        "constraints": [
            {"id": "floor", "type": "floor", "expr": "base * 0.40"},
            {"id": "ceiling", "type": "ceiling", "expr": "base"},
        ],
        "rounding": {"mode": "nearest", "step": 1},
    }
    data.update(overrides)
    return DomainPack.model_validate(data)


def test_rounding_cannot_push_ecommerce_price_above_mrp_cap():
    result = compute_price(
        _pack("ecommerce"),
        {
            "category": "electronics",
            "mrp": 100.5,
            "inventory_pct": 0.0,
            "demand_score": 80.0,
        },
    )

    assert result.price == Decimal("100.5")
    assert result.trace.to_list()[-1]["step"] == "post_rounding_constraints"


@pytest.mark.parametrize("mrp", [100, 100.49, 100.5, 100.51, 101])
def test_ecommerce_fractional_caps_are_final_guardrails(mrp):
    result = compute_price(
        _pack("ecommerce"),
        {
            "category": "electronics",
            "mrp": mrp,
            "inventory_pct": 0,
            "demand_score": 80,
        },
    )

    assert result.price <= Decimal(str(mrp))
    assert result.price >= Decimal(str(mrp)) * Decimal("0.40")


def test_post_rounding_floor_guardrail_is_enforced():
    pack = _minimal_pack(
        rules=[
            {
                "id": "discount",
                "stage": "main",
                "then": {"op": "multiply", "value": 0.40},
            }
        ],
        stages=[{"id": "main", "stacking": "all"}],
        constraints=[{"id": "floor", "type": "floor", "expr": "40.5"}],
        rounding={"mode": "down", "step": 1},
    )

    result = compute_price(pack, {"x": 101.25})

    assert result.price == Decimal("40.5")
    assert result.trace.to_list()[-1]["action"] == "enforce_final_constraints"


def test_conflicting_constraints_raise_pricing_error():
    pack = _minimal_pack(
        constraints=[
            {"id": "floor", "type": "floor", "expr": "80"},
            {"id": "ceiling", "type": "ceiling", "expr": "50"},
        ]
    )

    with pytest.raises(PricingError, match="Conflicting constraints"):
        compute_price(pack, {"x": 100})


@pytest.mark.parametrize(
    ("signals", "message"),
    [
        ({}, "Missing required signal 'category'"),
        ({"category": "electronics", "mrp": 100, "inventory_pct": 50, "demand_score": 30, "extra": 1}, "Unknown signal"),
        ({"category": "electronics", "mrp": True, "inventory_pct": 50, "demand_score": 30}, "mrp"),
        ({"category": "electronics", "mrp": 100, "inventory_pct": float("nan"), "demand_score": 30}, "inventory_pct"),
        ({"category": "electronics", "mrp": 100, "inventory_pct": 50, "demand_score": 101}, "demand_score"),
        ({"category": "unknown", "mrp": 100, "inventory_pct": 50, "demand_score": 30}, "category"),
        ({"category": "electronics", "mrp": 100, "inventory_pct": 50, "demand_score": 30, "is_flash_sale": "yes"}, "is_flash_sale"),
        ({"category": "electronics", "mrp": 100, "inventory_pct": 50, "demand_score": 30, "quantity": 1.0}, "quantity"),
    ],
)
def test_runtime_signal_validation_rejects_invalid_inputs(signals, message):
    with pytest.raises(PricingError, match=message):
        compute_price(_pack("ecommerce"), signals)


def test_rule_priority_ties_are_ordered_by_rule_id():
    pack = _minimal_pack(
        stages=[{"id": "main", "stacking": "first"}],
        rules=[
            {"id": "b-rule", "stage": "main", "priority": 10, "then": {"op": "set", "value": 200}},
            {"id": "a-rule", "stage": "main", "priority": 10, "then": {"op": "set", "value": 150}},
        ],
        constraints=[],
        rounding={"mode": "none", "step": 1},
    )
    reversed_pack = deepcopy(pack)
    reversed_pack.rules = list(reversed(reversed_pack.rules))

    assert compute_price(pack, {"x": 10}).price == Decimal("150")
    assert compute_price(reversed_pack, {"x": 10}).price == Decimal("150")


def test_cli_reports_pricing_errors_without_traceback(capsys, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "price",
            "--pack",
            str(ROOT / "packs" / "ecommerce.json"),
            "--context",
            json.dumps({"category": "electronics", "mrp": True, "inventory_pct": 50, "demand_score": 30}),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "Pricing Error:" in captured.err
    assert "Traceback" not in captured.err


def test_api_uses_same_runtime_validation(monkeypatch):
    pack = _pack("ecommerce")
    monkeypatch.setattr(
        pricing_routes,
        "get_published_pack",
        lambda domain: {"pack_data": pack.model_dump(mode="json")} if domain == "ecommerce" else None,
    )
    client = TestClient(app)

    response = client.post(
        "/v1/price",
        json={
            "domain": "ecommerce",
            "signals": {"category": "electronics", "mrp": True, "inventory_pct": 50, "demand_score": 30},
        },
    )

    assert response.status_code == 422
    assert "mrp" in response.json()["detail"]
