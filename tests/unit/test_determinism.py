"""
Determinism test — runs the same pricing request 1000 times
and verifies all fingerprints are identical.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.schema.pack import DomainPack
from engine.runtime import compute_price


def _load(name: str) -> DomainPack:
    data = json.loads((ROOT / "packs" / f"{name}.json").read_text())
    return DomainPack.model_validate(data)


def test_hospitality_1000_runs():
    pack = _load("hospitality")
    signals = {"room_type": "deluxe", "occupancy_pct": 90, "stay_date_dow": "sat", "loyalty_tier": "gold"}
    results = [compute_price(pack, signals) for _ in range(1000)]
    fingerprints = {r.fingerprint for r in results}
    prices = {r.price for r in results}
    assert len(fingerprints) == 1, f"Got {len(fingerprints)} different fingerprints!"
    assert len(prices) == 1, f"Got {len(prices)} different prices!"


def test_ecommerce_1000_runs():
    pack = _load("ecommerce")
    signals = {"category": "electronics", "mrp": 10000, "inventory_pct": 20, "demand_score": 70}
    results = [compute_price(pack, signals) for _ in range(1000)]
    fingerprints = {r.fingerprint for r in results}
    assert len(fingerprints) == 1, f"Got {len(fingerprints)} different fingerprints!"


def test_banking_1000_runs():
    pack = _load("banking")
    signals = {"loan_type": "personal", "credit_score": 750, "loan_amount": 200000, "loan_term_months": 60}
    results = [compute_price(pack, signals) for _ in range(1000)]
    fingerprints = {r.fingerprint for r in results}
    assert len(fingerprints) == 1, f"Got {len(fingerprints)} different fingerprints!"


def test_ev_charging_1000_runs():
    pack = _load("ev_charging")
    signals = {"charger_type": "fast", "time_of_day": "peak", "membership": "basic"}
    results = [compute_price(pack, signals) for _ in range(1000)]
    fingerprints = {r.fingerprint for r in results}
    assert len(fingerprints) == 1, f"Got {len(fingerprints)} different fingerprints!"
