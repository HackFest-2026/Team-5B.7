"""
Property-based tests using Hypothesis.

Tests:
  1. floor <= price <= ceiling always (hotel, banking, ecommerce)
  2. same input + same pack → same output (determinism)
  3. rule file ordering does not change result for independent rules
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.schema.pack import DomainPack
from engine.runtime import compute_price

HOTEL_PACK_FILE  = ROOT / "packs" / "hospitality.json"
BANK_PACK_FILE   = ROOT / "packs" / "banking.json"
ECOMM_PACK_FILE  = ROOT / "packs" / "ecommerce.json"


@pytest.fixture(scope="module")
def hotel_pack():
    return DomainPack.model_validate(json.loads(HOTEL_PACK_FILE.read_text()))


@pytest.fixture(scope="module")
def bank_pack():
    return DomainPack.model_validate(json.loads(BANK_PACK_FILE.read_text()))


@pytest.fixture(scope="module")
def ecomm_pack():
    return DomainPack.model_validate(json.loads(ECOMM_PACK_FILE.read_text()))


# ---------------------------------------------------------------------------
# Property 1: floor <= price <= ceiling
# ---------------------------------------------------------------------------

@given(
    occupancy=st.floats(min_value=0, max_value=100),
    room_type=st.sampled_from(["standard", "deluxe", "suite"]),
    loyalty=st.sampled_from(["none", "silver", "gold"]),
    dow=st.sampled_from(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]),
)
@settings(max_examples=200)
def test_hotel_price_within_constraints(hotel_pack, occupancy, room_type, loyalty, dow):
    """Hotel price must always be within floor and ceiling."""
    signals = {
        "room_type": room_type,
        "occupancy_pct": occupancy,
        "loyalty_tier": loyalty,
        "stay_date_dow": dow,
    }
    result = compute_price(hotel_pack, signals)
    from engine.evaluate.formula import evaluate_formula
    floor_val = float(evaluate_formula("base * 0.70", {"base": float(result.base)}))
    ceiling_val = float(evaluate_formula("base * 2.50", {"base": float(result.base)}))
    price = float(result.price)
    assert price >= floor_val - 0.01, f"Price {price} < floor {floor_val}"
    assert price <= ceiling_val + 0.01, f"Price {price} > ceiling {ceiling_val}"


@given(
    credit=st.integers(min_value=300, max_value=900),
    loan_type=st.sampled_from(["personal", "home", "auto", "education"]),
    amount=st.floats(min_value=10000, max_value=10000000),
    term=st.integers(min_value=6, max_value=360),
)
@settings(max_examples=200)
def test_bank_rate_within_constraints(bank_pack, credit, loan_type, amount, term):
    """Banking rate must always be within floor (6.5) and ceiling (24.0)."""
    signals = {
        "loan_type": loan_type,
        "credit_score": credit,
        "loan_amount": amount,
        "loan_term_months": term,
    }
    result = compute_price(bank_pack, signals)
    price = float(result.price)
    assert price >= 6.5 - 0.01, f"Rate {price} < floor 6.5"
    assert price <= 24.0 + 0.01, f"Rate {price} > ceiling 24.0"


# ---------------------------------------------------------------------------
# Property 2: Determinism
# ---------------------------------------------------------------------------

@given(
    occupancy=st.floats(min_value=0, max_value=100),
    room_type=st.sampled_from(["standard", "deluxe", "suite"]),
)
@settings(max_examples=100)
def test_hotel_determinism(hotel_pack, occupancy, room_type):
    """Same input → identical fingerprint every time."""
    signals = {"room_type": room_type, "occupancy_pct": occupancy}
    r1 = compute_price(hotel_pack, signals)
    r2 = compute_price(hotel_pack, signals)
    assert r1.fingerprint == r2.fingerprint
    assert r1.price == r2.price


# ---------------------------------------------------------------------------
# Property 3: Rule ordering independence
# ---------------------------------------------------------------------------

def test_rule_order_independence_hotel(hotel_pack):
    """
    For stages with stacking=all, shuffling the order of semantically
    independent rules must not change the final price.
    
    The weekend rule is independent of the demand rules (different signals).
    We verify that reversing the rule list order doesn't change the result.
    """
    import copy
    pack_reversed = copy.deepcopy(hotel_pack)
    pack_reversed.rules = list(reversed(pack_reversed.rules))

    signals = {
        "room_type": "deluxe",
        "occupancy_pct": 90,
        "stay_date_dow": "sat",
        "loyalty_tier": "gold",
    }

    r_original = compute_price(hotel_pack, signals)
    r_reversed = compute_price(pack_reversed, signals)

    # Prices should be identical — priority determines order within a stage
    assert r_original.price == r_reversed.price


# ---------------------------------------------------------------------------
# E-commerce property tests
# ---------------------------------------------------------------------------

@given(
    mrp=st.floats(min_value=100, max_value=100000),
    inventory=st.floats(min_value=0, max_value=100),
    demand=st.floats(min_value=0, max_value=100),
    category=st.sampled_from(["electronics", "fashion", "grocery", "home_appliances", "beauty"]),
)
@settings(max_examples=200)
def test_ecomm_price_within_constraints(ecomm_pack, mrp, inventory, demand, category):
    """Ecommerce price must always be within floor (40% MRP) and ceiling (100% MRP)."""
    signals = {
        "category": category,
        "mrp": mrp,
        "inventory_pct": inventory,
        "demand_score": demand,
    }
    result = compute_price(ecomm_pack, signals)
    price = float(result.price)
    floor_val = mrp * 0.40 - 0.01
    ceiling_val = mrp * 1.00 + 0.01
    assert price >= floor_val, f"Price {price} < floor {floor_val} (mrp={mrp})"
    assert price <= ceiling_val, f"Price {price} > ceiling {ceiling_val} (mrp={mrp})"


@given(
    mrp=st.floats(min_value=100, max_value=50000),
    inventory=st.floats(min_value=0, max_value=100),
    demand=st.floats(min_value=0, max_value=100),
)
@settings(max_examples=100)
def test_ecomm_determinism(ecomm_pack, mrp, inventory, demand):
    """Same ecommerce input → identical fingerprint every time."""
    signals = {
        "category": "electronics",
        "mrp": mrp,
        "inventory_pct": inventory,
        "demand_score": demand,
    }
    r1 = compute_price(ecomm_pack, signals)
    r2 = compute_price(ecomm_pack, signals)
    assert r1.fingerprint == r2.fingerprint
    assert r1.price == r2.price


def test_ecomm_rule_order_independence(ecomm_pack):
    """
    Reversing the rule list should not change results for ecommerce,
    since priority ordering within each stage is deterministic.
    """
    import copy
    pack_reversed = copy.deepcopy(ecomm_pack)
    pack_reversed.rules = list(reversed(pack_reversed.rules))

    signals = {
        "category": "electronics",
        "mrp": 10000,
        "inventory_pct": 20,
        "demand_score": 70,
        "customer_tier": "prime",
    }
    r_original = compute_price(ecomm_pack, signals)
    r_reversed = compute_price(pack_reversed, signals)
    assert r_original.price == r_reversed.price
