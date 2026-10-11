from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.storage.db import init_db, publish_pack, upsert_pack
from engine.runtime import compute_price
from engine.schema.pack import DomainPack
from engine.validate import validate_pack


ROOT = Path(__file__).parent.parent.parent
PACK_FILE = ROOT / "packs" / "airline.json"
SCENARIO_FILE = ROOT / "tests" / "fixtures_airline_scenarios.json"


def _airline_pack() -> DomainPack:
    return DomainPack.model_validate(json.loads(PACK_FILE.read_text(encoding="utf-8")))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_isolated_airline_pack(monkeypatch, tmp_path):
    db_path = tmp_path / "airline_context.db"
    monkeypatch.setattr("api.storage.db.DB_PATH", db_path)
    init_db()
    pack_data = json.loads(PACK_FILE.read_text(encoding="utf-8"))
    upsert_pack("airline", "1.0.0", pack_data, status="draft", actor="test")
    publish_pack("airline", "1.0.0", actor="test")
    return TestClient(app)


def test_airline_pack_validates_without_engine_domain_branch():
    pack = _airline_pack()
    result = validate_pack(pack)

    assert result.valid is True
    assert pack.pack_id == "airline"
    assert not any("airline" in path.read_text(encoding="utf-8") for path in (ROOT / "engine").rglob("*.py"))


def test_ten_synthetic_airline_scenarios_match_expected_prices():
    pack = _airline_pack()
    scenarios = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))

    assert len(scenarios) >= 10
    for scenario in scenarios:
        result = compute_price(pack, scenario["signals"])
        assert result.price == Decimal(str(scenario["expected_price"])), scenario["id"]
        assert result.fingerprint
        assert result.trace.to_list()


def test_context_update_changes_following_price_and_trace(monkeypatch, tmp_path):
    client = _seed_isolated_airline_pack(monkeypatch, tmp_path)
    base_signals = {
        "cabin_class": "economy",
        "base_fare": 150,
        "distance_km": 1200,
        "total_seats": 300,
        "days_to_departure": 10,
        "checked_bags": 0,
    }

    normal_context = {
        "signals": {"demand_index": 50, "available_seats": 200},
        "observed_at": _now(),
        "max_age_seconds": 300,
        "source": "synthetic-test",
    }
    response = client.put("/v1/context/airline", json=normal_context)
    assert response.status_code == 200

    normal = client.post("/v1/price", json={"domain": "airline", "signals": base_signals})
    assert normal.status_code == 200
    assert normal.json()["price"] == 245.0

    surge_context = {
        "signals": {"demand_index": 95, "available_seats": 5},
        "observed_at": _now(),
        "max_age_seconds": 300,
        "source": "synthetic-test",
    }
    response = client.put("/v1/context/airline", json=surge_context)
    assert response.status_code == 200

    surge = client.post("/v1/price", json={"domain": "airline", "signals": base_signals})
    assert surge.status_code == 200
    surge_body = surge.json()
    assert surge_body["price"] == 370.0
    assert any(step["rule_id"] == "R-DEMAND-HIGH" and step["fired"] for step in surge_body["trace"])
    assert surge_body["fingerprint"] != normal.json()["fingerprint"]


def test_identical_context_and_request_are_deterministic(monkeypatch, tmp_path):
    client = _seed_isolated_airline_pack(monkeypatch, tmp_path)
    response = client.put(
        "/v1/context/airline",
        json={
            "signals": {"demand_index": 70, "available_seats": 20},
            "observed_at": _now(),
            "max_age_seconds": 300,
            "source": "synthetic-test",
        },
    )
    assert response.status_code == 200

    request = {
        "domain": "airline",
        "signals": {
            "cabin_class": "premium",
            "base_fare": 120,
            "distance_km": 800,
            "total_seats": 300,
            "days_to_departure": 10,
            "checked_bags": 1,
        },
    }
    first = client.post("/v1/price", json=request)
    second = client.post("/v1/price", json=request)

    assert first.status_code == second.status_code == 200
    assert first.json()["price"] == second.json()["price"]
    assert first.json()["fingerprint"] == second.json()["fingerprint"]
    assert first.json()["trace"] == second.json()["trace"]


@pytest.mark.parametrize(
    ("signals", "message"),
    [
        ({"demand_index": 101}, "must be <= 100"),
        ({"available_seats": 1.5}, "must be an integer"),
        ({"unknown_signal": 1}, "Unknown context signal"),
        ({}, "non-empty"),
    ],
)
def test_context_update_rejects_invalid_values(monkeypatch, tmp_path, signals, message):
    client = _seed_isolated_airline_pack(monkeypatch, tmp_path)
    response = client.put(
        "/v1/context/airline",
        json={"signals": signals, "observed_at": _now(), "max_age_seconds": 300},
    )

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_context_update_rejects_stale_timestamp(monkeypatch, tmp_path):
    client = _seed_isolated_airline_pack(monkeypatch, tmp_path)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    response = client.put(
        "/v1/context/airline",
        json={
            "signals": {"demand_index": 50},
            "observed_at": stale,
            "max_age_seconds": 60,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Context snapshot is stale."
