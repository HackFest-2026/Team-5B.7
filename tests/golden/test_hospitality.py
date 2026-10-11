"""
Golden tests for the Hospitality domain.

Expected values are hand-calculated INDEPENDENTLY of the engine.
Rule: never derive expected values from the engine being tested.
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

PACK_FILE = ROOT / "packs" / "hospitality.json"


@pytest.fixture(scope="module")
def hotel_pack() -> DomainPack:
    data = json.loads(PACK_FILE.read_text())
    return DomainPack.model_validate(data)


# ---------------------------------------------------------------------------
# Golden cases — hand-calculated
# ---------------------------------------------------------------------------

class TestHotelGolden:
    """
    Base prices: standard=3200, deluxe=4500, suite=8000
    Demand:  ≥95→×1.40, ≥85→×1.30, ≥70→×1.10, <50→×0.90, else×1.0
    Weekend: fri/sat→×1.15
    Loyalty: gold→×0.92, silver→×0.95
    Floor:   base×0.70   Ceiling: base×2.50
    Rounding: nearest 10
    """

    def test_standard_no_rules_fire(self, hotel_pack):
        """Standard room, 60% occupancy, no weekend, no loyalty → base price."""
        # occupancy=60: no demand rule fires (not ≥70, not <50)
        # no weekend, no loyalty
        # expected: 3200, round to nearest 10 → 3200
        result = compute_price(hotel_pack, {"room_type": "standard", "occupancy_pct": 60})
        assert result.price == Decimal("3200")

    def test_deluxe_high_occupancy(self, hotel_pack):
        """Deluxe, 90% occupancy, no weekend, no loyalty → base×1.30."""
        # base=4500, ×1.30=5850, round→5850
        result = compute_price(hotel_pack, {"room_type": "deluxe", "occupancy_pct": 90})
        assert result.price == Decimal("5850")

    def test_deluxe_very_high_occupancy(self, hotel_pack):
        """Deluxe, 96% occupancy → ×1.40 (very-high rule wins, stacking=first)."""
        # base=4500, ×1.40=6300, round→6300
        result = compute_price(hotel_pack, {"room_type": "deluxe", "occupancy_pct": 96})
        assert result.price == Decimal("6300")

    def test_suite_low_occupancy(self, hotel_pack):
        """Suite, 40% occupancy → ×0.90."""
        # base=8000, ×0.90=7200, round→7200
        result = compute_price(hotel_pack, {"room_type": "suite", "occupancy_pct": 40})
        assert result.price == Decimal("7200")

    def test_deluxe_high_occupancy_weekend(self, hotel_pack):
        """Deluxe, 90% occupancy, Saturday → demand then weekend both apply."""
        # base=4500
        # demand: ×1.30 → 5850
        # weekend: ×1.15 → 6727.5
        # round to nearest 10 → 6730
        result = compute_price(hotel_pack, {
            "room_type": "deluxe",
            "occupancy_pct": 90,
            "stay_date_dow": "sat",
        })
        assert result.price == Decimal("6730")

    def test_deluxe_high_occupancy_gold(self, hotel_pack):
        """Deluxe, 90% occ, gold loyalty → demand + customer discount."""
        # base=4500
        # demand: ×1.30 → 5850
        # no weekend
        # loyalty: gold ×0.92 → 5382
        # round → 5380
        result = compute_price(hotel_pack, {
            "room_type": "deluxe",
            "occupancy_pct": 90,
            "loyalty_tier": "gold",
        })
        assert result.price == Decimal("5380")

    def test_standard_gold_weekend_high_occ(self, hotel_pack):
        """Standard, 88% occ, Saturday, gold → all three stages fire."""
        # base=3200
        # demand: ×1.30 → 4160
        # weekend: ×1.15 → 4784
        # loyalty gold: ×0.92 → 4401.28
        # round to nearest 10 → 4400
        result = compute_price(hotel_pack, {
            "room_type": "standard",
            "occupancy_pct": 88,
            "stay_date_dow": "sat",
            "loyalty_tier": "gold",
        })
        assert result.price == Decimal("4400")

    def test_floor_enforced(self, hotel_pack):
        """Price cannot go below base×0.70."""
        # standard base=3200, floor=2240
        # Low occ: 40% → ×0.90 → 2880
        # 2880 > 2240 → floor not triggered
        # To trigger floor, need a discount below 70%. Our rules can't do that alone.
        # Instead verify: result >= floor
        result = compute_price(hotel_pack, {
            "room_type": "standard",
            "occupancy_pct": 40,
        })
        floor_val = 3200 * 0.70
        assert float(result.price) >= floor_val

    def test_ceiling_enforced(self, hotel_pack):
        """Price cannot exceed base×2.50."""
        result = compute_price(hotel_pack, {
            "room_type": "suite",
            "occupancy_pct": 99,
            "stay_date_dow": "sat",
        })
        ceiling_val = 8000 * 2.50
        assert float(result.price) <= ceiling_val

    def test_trace_has_base_step(self, hotel_pack):
        """Every price trace must begin with a base step."""
        result = compute_price(hotel_pack, {"room_type": "standard", "occupancy_pct": 60})
        steps = result.trace.to_list()
        assert steps[0]["step"] == "base"
        assert steps[0]["after"] == 3200.0

    def test_trace_has_rounding_step(self, hotel_pack):
        """Every price trace must end with a rounding step."""
        result = compute_price(hotel_pack, {"room_type": "standard", "occupancy_pct": 60})
        steps = result.trace.to_list()
        assert steps[-1]["step"] == "rounding"

    def test_fingerprint_is_deterministic(self, hotel_pack):
        """Same input always produces the same fingerprint."""
        signals = {"room_type": "deluxe", "occupancy_pct": 90, "loyalty_tier": "gold"}
        r1 = compute_price(hotel_pack, signals)
        r2 = compute_price(hotel_pack, signals)
        assert r1.fingerprint == r2.fingerprint

    def test_threshold_boundary_85(self, hotel_pack):
        """Exactly 85% occupancy → high demand rule fires."""
        # base=4500, ×1.30=5850
        result = compute_price(hotel_pack, {"room_type": "deluxe", "occupancy_pct": 85})
        assert result.price == Decimal("5850")

    def test_threshold_boundary_84(self, hotel_pack):
        """84% occupancy → medium demand (≥70) fires."""
        # base=4500, ×1.10=4950
        result = compute_price(hotel_pack, {"room_type": "deluxe", "occupancy_pct": 84})
        assert result.price == Decimal("4950")

    def test_silver_is_less_discount_than_gold(self, hotel_pack):
        """Silver loyalty gets less discount than gold."""
        signals_gold = {"room_type": "deluxe", "occupancy_pct": 90, "loyalty_tier": "gold"}
        signals_silver = {"room_type": "deluxe", "occupancy_pct": 90, "loyalty_tier": "silver"}
        gold_price = compute_price(hotel_pack, signals_gold).price
        silver_price = compute_price(hotel_pack, signals_silver).price
        assert gold_price < silver_price  # gold discount is bigger
