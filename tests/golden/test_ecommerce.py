"""
Golden tests for the E-commerce domain.

Signals:
  category      — electronics / fashion / grocery / home_appliances / beauty
  mrp           — Maximum Retail Price (base anchor)
  inventory_pct — % remaining stock
  demand_score  — demand index 0–100
  customer_tier — guest / regular / prime / elite
  quantity      — units being ordered
  is_flash_sale — boolean
  days_since_listed — listing age in days

Key rules (hand-calculated):
  base = mrp (formula)
  Category discount: electronics×0.85, fashion×0.70, grocery×0.95, home×0.80, beauty×0.75
  Inventory: scarce(≤10%)×1.12, low(11–30%)×1.05, excess(>80%)×0.92
  Demand: viral(≥80)×1.08, high(60–79)×1.04
  Clearance: old(>180d)×0.80, aging(90–180d)×0.90
  Flash sale: ×0.85
  Customer (max_discount wins): elite×0.90, bulk≥10×0.88, prime×0.93, bulk5–9×0.94, regular×0.97
  Floor: base×0.40    Ceiling: base×1.00 (never exceed MRP)
  Rounding: nearest 1
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.schema.pack import DomainPack
from engine.runtime import compute_price

PACK_FILE = ROOT / "packs" / "ecommerce.json"


@pytest.fixture(scope="module")
def ecomm_pack() -> DomainPack:
    data = json.loads(PACK_FILE.read_text())
    return DomainPack.model_validate(data)


class TestEcommerceGolden:

    # ------------------------------------------------------------------
    # Basic category discount
    # ------------------------------------------------------------------

    def test_electronics_standard(self, ecomm_pack):
        """Electronics, normal inventory, normal demand → 15% off MRP."""
        # base=10000, cat: ×0.85=8500
        # inventory: 50% → no rule fires (31–80 range, no rule)
        # demand: 30 → no rule fires
        # no clearance, no flash, no customer
        # floor=4000, ceiling=10000 → 8500 in range
        # round→8500
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
        })
        assert result.price == Decimal("8500")

    def test_fashion_standard(self, ecomm_pack):
        """Fashion, normal inventory, normal demand → 30% off MRP."""
        # base=2000, cat: ×0.70=1400
        result = compute_price(ecomm_pack, {
            "category": "fashion",
            "mrp": 2000,
            "inventory_pct": 50,
            "demand_score": 30,
        })
        assert result.price == Decimal("1400")

    def test_grocery_tight_margin(self, ecomm_pack):
        """Grocery: only 5% discount."""
        # base=500, cat: ×0.95=475
        result = compute_price(ecomm_pack, {
            "category": "grocery",
            "mrp": 500,
            "inventory_pct": 50,
            "demand_score": 30,
        })
        assert result.price == Decimal("475")

    # ------------------------------------------------------------------
    # Inventory rules
    # ------------------------------------------------------------------

    def test_scarce_inventory_premium(self, ecomm_pack):
        """Inventory ≤10%: scarcity premium ×1.12 on top of category discount."""
        # base=10000, cat electronics ×0.85=8500, inv scarce ×1.12=9520
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 5,
            "demand_score": 30,
        })
        assert result.price == Decimal("9520")

    def test_low_inventory_premium(self, ecomm_pack):
        """Inventory 11–30%: mild premium ×1.05."""
        # base=10000, cat ×0.85=8500, inv low ×1.05=8925
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 20,
            "demand_score": 30,
        })
        assert result.price == Decimal("8925")

    def test_excess_inventory_markdown(self, ecomm_pack):
        """Inventory >80%: excess markdown ×0.92."""
        # base=10000, cat ×0.85=8500, inv excess ×0.92=7820
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 90,
            "demand_score": 30,
        })
        assert result.price == Decimal("7820")

    # ------------------------------------------------------------------
    # Demand recovery
    # ------------------------------------------------------------------

    def test_viral_demand_recovery(self, ecomm_pack):
        """Viral demand score ≥80 recovers 8%."""
        # base=10000, cat ×0.85=8500, inv normal, demand viral ×1.08=9180
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 85,
        })
        assert result.price == Decimal("9180")

    def test_high_demand_recovery(self, ecomm_pack):
        """High demand score 60–79 recovers 4%."""
        # base=10000, cat ×0.85=8500, demand high ×1.04=8840
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 65,
        })
        assert result.price == Decimal("8840")

    def test_scarce_stock_viral_demand(self, ecomm_pack):
        """Scarce inventory + viral demand: both stack (stacking=all on demand)."""
        # base=10000, cat ×0.85=8500
        # inv scarce (stacking=first) ×1.12=9520
        # demand viral (stacking=all) ×1.08=10281.6 → but ceiling=base=10000
        # → ceiling kicks in → 10000
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 5,
            "demand_score": 85,
        })
        assert result.price == Decimal("10000")

    # ------------------------------------------------------------------
    # Clearance
    # ------------------------------------------------------------------

    def test_old_listing_clearance(self, ecomm_pack):
        """Listing >180 days old: clearance markdown ×0.80."""
        # base=2000, fashion ×0.70=1400, clearance ×0.80=1120
        result = compute_price(ecomm_pack, {
            "category": "fashion",
            "mrp": 2000,
            "inventory_pct": 50,
            "demand_score": 30,
            "days_since_listed": 200,
        })
        assert result.price == Decimal("1120")

    def test_aging_listing_clearance(self, ecomm_pack):
        """Listing 90–180 days: mild clearance ×0.90."""
        # base=2000, fashion ×0.70=1400, clearance aging ×0.90=1260
        result = compute_price(ecomm_pack, {
            "category": "fashion",
            "mrp": 2000,
            "inventory_pct": 50,
            "demand_score": 30,
            "days_since_listed": 120,
        })
        assert result.price == Decimal("1260")

    # ------------------------------------------------------------------
    # Flash sale
    # ------------------------------------------------------------------

    def test_flash_sale(self, ecomm_pack):
        """Flash sale active: additional -15%."""
        # base=10000, cat ×0.85=8500, flash ×0.85=7225
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
            "is_flash_sale": True,
        })
        assert result.price == Decimal("7225")

    # ------------------------------------------------------------------
    # Customer tiers (max_discount: only best discount applies)
    # ------------------------------------------------------------------

    def test_elite_tier_discount(self, ecomm_pack):
        """Elite member gets -10% off current price."""
        # base=10000, cat ×0.85=8500, elite ×0.90=7650
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
            "customer_tier": "elite",
        })
        assert result.price == Decimal("7650")

    def test_bulk_10_wins_over_prime(self, ecomm_pack):
        """Bulk ≥10 (×0.88) beats prime (×0.93): max_discount picks bulk."""
        # base=10000, cat ×0.85=8500
        # customer stage max_discount: bulk10 gives 8500×0.88=7480, prime gives 8500×0.93=7905
        # 7480 < 7905 so max_discount picks bulk → 7480
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
            "customer_tier": "prime",
            "quantity": 15,
        })
        assert result.price == Decimal("7480")

    def test_prime_tier_no_bulk(self, ecomm_pack):
        """Prime member, quantity=1: gets -7%."""
        # base=10000, cat ×0.85=8500, prime ×0.93=7905
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
            "customer_tier": "prime",
            "quantity": 1,
        })
        assert result.price == Decimal("7905")

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def test_ceiling_never_exceeds_mrp(self, ecomm_pack):
        """Price can never exceed MRP (ceiling = base × 1.0)."""
        result = compute_price(ecomm_pack, {
            "category": "grocery",
            "mrp": 500,
            "inventory_pct": 5,     # scarce +12%
            "demand_score": 90,     # viral +8%
        })
        assert float(result.price) <= 500

    def test_floor_never_below_40pct_mrp(self, ecomm_pack):
        """Price never falls below 40% of MRP."""
        result = compute_price(ecomm_pack, {
            "category": "fashion",
            "mrp": 2000,
            "inventory_pct": 90,        # excess -8%
            "demand_score": 10,
            "days_since_listed": 250,   # old clearance -20%
            "is_flash_sale": True,      # flash -15%
            "customer_tier": "elite",   # elite -10%
        })
        floor = 2000 * 0.40  # 800
        assert float(result.price) >= floor

    # ------------------------------------------------------------------
    # Determinism
    # ------------------------------------------------------------------

    def test_determinism(self, ecomm_pack):
        """Same input produces identical fingerprint every time."""
        signals = {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 20,
            "demand_score": 70,
            "customer_tier": "prime",
        }
        r1 = compute_price(ecomm_pack, signals)
        r2 = compute_price(ecomm_pack, signals)
        assert r1.fingerprint == r2.fingerprint
        assert r1.price == r2.price

    # ------------------------------------------------------------------
    # Trace quality
    # ------------------------------------------------------------------

    def test_trace_starts_with_base(self, ecomm_pack):
        """Trace must begin with 'base' step showing MRP."""
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
        })
        steps = result.trace.to_list()
        assert steps[0]["step"] == "base"
        assert steps[0]["after"] == 10000.0

    def test_trace_ends_with_rounding(self, ecomm_pack):
        """Trace must end with 'rounding' step."""
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
        })
        steps = result.trace.to_list()
        assert steps[-1]["step"] == "rounding"

    def test_unfired_rules_appear_in_trace(self, ecomm_pack):
        """Rules that did not fire must be in the trace with fired=False."""
        result = compute_price(ecomm_pack, {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 50,
            "demand_score": 30,
        })
        steps = result.trace.to_list()
        unfired = [s for s in steps if not s["fired"]]
        # At least some rules didn't fire (e.g., flash sale, customer tiers)
        assert len(unfired) > 0
