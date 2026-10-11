#!/usr/bin/env python
"""
Synthetic Evaluation Corpus Generator for RateWeaver.

Generates a machine-readable, deterministic synthetic dataset of 140 labelled
pricing cases across 4 domains (Hospitality, E-Commerce, Banking, EV Charging).

Coverage:
  - Ordinary representative cases
  - Boundary cases (exact floor/ceiling hits, step boundaries, min/max signals)
  - Rule-priority and stacking conflict cases
  - Invalid input cases (missing required, out-of-range, wrong types, nulls)

Usage:
    python scripts/generate_synthetic_corpus.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).parent.parent
OUTPUT_FILE = ROOT / "data" / "synthetic_evaluation_corpus.json"


def build_corpus() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # =========================================================================
    # 1. HOSPITALITY DOMAIN (35 cases)
    # Unit: INR, Base: standard: 3200, deluxe: 4500, suite: 8000
    # Demand: >=95 -> *1.40, >=85 -> *1.30, >=70 -> *1.10, <50 -> *0.90 (first)
    # Weekend: fri/sat -> *1.15 (all)
    # Loyalty: gold -> *0.92, silver -> *0.95 (max_discount)
    # Floor: base * 0.70, Ceiling: base * 2.50, Rounding: nearest 10
    # =========================================================================
    
    # Ordinary cases (1-10)
    cases.append({
        "id": "SYN-HOSP-001",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "ordinary",
        "description": "Standard room, weekday, medium occupancy (75%) -> base 3200 * 1.10 = 3520",
        "signals": {"room_type": "standard", "occupancy_pct": 75.0, "stay_date_dow": "wed"},
        "expected_outcome": "success",
        "expected_price": 3520.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-MED"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Occupancy 75% triggers R-DEMAND-MED (1.10). Rounding step 10 preserves 3520."
    })

    cases.append({
        "id": "SYN-HOSP-002",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "ordinary",
        "description": "Deluxe room, weekend (Sat), high occupancy (88%), gold loyalty -> 4500 * 1.30 * 1.15 * 0.92 = 6189.3 -> rounded 6190",
        "signals": {"room_type": "deluxe", "occupancy_pct": 88.0, "stay_date_dow": "sat", "loyalty_tier": "gold"},
        "expected_outcome": "success",
        "expected_price": 6190.0,
        "expected_base": 4500.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-HIGH", "R-WEEKEND", "R-LOYALTY-GOLD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "4500 * 1.30 = 5850; 5850 * 1.15 = 6727.5; 6727.5 * 0.92 = 6189.3 -> nearest 10 is 6190."
    })

    cases.append({
        "id": "SYN-HOSP-003",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "ordinary",
        "description": "Suite room, weekday, low occupancy (40%), silver loyalty -> 8000 * 0.90 * 0.95 = 6840",
        "signals": {"room_type": "suite", "occupancy_pct": 40.0, "stay_date_dow": "tue", "loyalty_tier": "silver"},
        "expected_outcome": "success",
        "expected_price": 6840.0,
        "expected_base": 8000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-LOW", "R-LOYALTY-SILVER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "8000 * 0.90 = 7200; 7200 * 0.95 = 6840."
    })

    cases.append({
        "id": "SYN-HOSP-004",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "ordinary",
        "description": "Deluxe room, Friday weekend stay, normal occupancy (55%, no demand rule) -> 4500 * 1.15 = 5175 -> round 5180",
        "signals": {"room_type": "deluxe", "occupancy_pct": 55.0, "stay_date_dow": "fri"},
        "expected_outcome": "success",
        "expected_price": 5180.0,
        "expected_base": 4500.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-WEEKEND"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Occupancy 55% matches no demand rule (50 <= occ < 70). Weekend adds 15%. 4500*1.15=5175 -> 5180."
    })

    cases.append({
        "id": "SYN-HOSP-005",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "ordinary",
        "description": "Standard room, very high occupancy (96%), Sunday (no weekend rule) -> 3200 * 1.40 = 4480",
        "signals": {"room_type": "standard", "occupancy_pct": 96.0, "stay_date_dow": "sun"},
        "expected_outcome": "success",
        "expected_price": 4480.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-VERY-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "3200 * 1.40 = 4480."
    })

    # More ordinary cases
    for idx, (rt, occ, dow, loy, exp_p, fired) in enumerate([
        ("standard", 50.0, "mon", "none", 3200.0, []),
        ("deluxe", 72.0, "thu", "none", 4950.0, ["R-DEMAND-MED"]), # 4500*1.1=4950
        ("suite", 90.0, "sat", "gold", 11000.0, ["R-DEMAND-HIGH", "R-WEEKEND", "R-LOYALTY-GOLD"]), # 8000*1.3*1.15*0.92 = 11003.2 -> rounded to nearest 10 is 11000
        ("standard", 45.0, "sat", "silver", 3140.0, ["R-DEMAND-LOW", "R-WEEKEND", "R-LOYALTY-SILVER"]), # 3200*0.90*1.15*0.95 = 3146.4 -> 3150? wait: 3200*0.9=2880; 2880*1.15=3312; 3312*0.95=3146.4 -> nearest 10 is 3150!
        ("suite", 60.0, "wed", "none", 8000.0, []), # between 50 and 70
    ], start=6):
        # Let's adjust expected price for standard 45 sat silver
        p = 3150.0 if idx == 9 else exp_p
        cases.append({
            "id": f"SYN-HOSP-{idx:03d}",
            "is_synthetic": True,
            "version": "1.0.0",
            "domain": "hospitality",
            "scenario_type": "ordinary",
            "description": f"Hospitality {rt} occ={occ}% dow={dow} loy={loy}",
            "signals": {"room_type": rt, "occupancy_pct": occ, "stay_date_dow": dow, "loyalty_tier": loy},
            "expected_outcome": "success",
            "expected_price": p,
            "expected_base": 3200.0 if rt == "standard" else (4500.0 if rt == "deluxe" else 8000.0),
            "currency_or_unit": "INR",
            "expected_rules_fired": fired,
            "expected_floor_hit": False,
            "expected_ceiling_hit": False,
            "expected_error": None,
            "tolerance": 0.01,
            "notes": "Verified against hospitality pack rules."
        })

    # Boundary cases (11-20)
    cases.append({
        "id": "SYN-HOSP-011",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Occupancy exact boundary 70.0% -> triggers R-DEMAND-MED (>=70) -> 3200*1.1 = 3520",
        "signals": {"room_type": "standard", "occupancy_pct": 70.0},
        "expected_outcome": "success",
        "expected_price": 3520.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-MED"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Exact boundary test for >= 70% threshold."
    })
    cases.append({
        "id": "SYN-HOSP-012",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Occupancy just below boundary 69.9% -> no demand rule fires -> base 3200",
        "signals": {"room_type": "standard", "occupancy_pct": 69.9},
        "expected_outcome": "success",
        "expected_price": 3200.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Just below 70.0% boundary."
    })
    cases.append({
        "id": "SYN-HOSP-013",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Occupancy exact boundary 85.0% -> triggers R-DEMAND-HIGH (>=85) -> 3200*1.3 = 4160",
        "signals": {"room_type": "standard", "occupancy_pct": 85.0},
        "expected_outcome": "success",
        "expected_price": 4160.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Exact boundary for R-DEMAND-HIGH."
    })
    cases.append({
        "id": "SYN-HOSP-014",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Occupancy boundary 95.0% -> triggers R-DEMAND-VERY-HIGH (>=95) -> 3200*1.4 = 4480",
        "signals": {"room_type": "standard", "occupancy_pct": 95.0},
        "expected_outcome": "success",
        "expected_price": 4480.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-VERY-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Exact boundary for R-DEMAND-VERY-HIGH."
    })
    cases.append({
        "id": "SYN-HOSP-015",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Minimum valid occupancy 0.0% -> triggers R-DEMAND-LOW (<50) -> 3200*0.9 = 2880",
        "signals": {"room_type": "standard", "occupancy_pct": 0.0},
        "expected_outcome": "success",
        "expected_price": 2880.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-LOW"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Occupancy min bound 0%."
    })
    cases.append({
        "id": "SYN-HOSP-016",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Maximum valid occupancy 100.0% on Saturday with gold loyalty -> 3200*1.4*1.15*0.92 = 4740.16 -> 4740",
        "signals": {"room_type": "standard", "occupancy_pct": 100.0, "stay_date_dow": "sat", "loyalty_tier": "gold"},
        "expected_outcome": "success",
        "expected_price": 4740.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-VERY-HIGH", "R-WEEKEND", "R-LOYALTY-GOLD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Occupancy max bound 100%."
    })
    cases.append({
        "id": "SYN-HOSP-017",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Low occupancy 49.9% -> triggers R-DEMAND-LOW (<50) -> 4500*0.9 = 4050",
        "signals": {"room_type": "deluxe", "occupancy_pct": 49.9},
        "expected_outcome": "success",
        "expected_price": 4050.0,
        "expected_base": 4500.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-LOW"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Strict inequality < 50 test."
    })
    cases.append({
        "id": "SYN-HOSP-018",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Occupancy 50.0% -> neither <50 nor >=70 fires -> base deluxe 4500",
        "signals": {"room_type": "deluxe", "occupancy_pct": 50.0},
        "expected_outcome": "success",
        "expected_price": 4500.0,
        "expected_base": 4500.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Dead-band boundary between demand tiers."
    })
    cases.append({
        "id": "SYN-HOSP-019",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Extreme markdown hitting floor guardrail: base * 0.70",
        "signals": {"room_type": "standard", "occupancy_pct": 10.0, "loyalty_tier": "gold"},
        "expected_outcome": "success",
        "expected_price": 2650.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-LOW", "R-LOYALTY-GOLD"],
        "expected_floor_hit": False, # 3200 * 0.9 * 0.92 = 2649.6 -> 2650; floor is 3200*0.7 = 2240
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "3200 * 0.90 * 0.92 = 2649.6 -> rounded 2650."
    })
    cases.append({
        "id": "SYN-HOSP-020",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "boundary",
        "description": "Ceiling guardrail verification: base * 2.50 = 8000 * 2.5 = 20000",
        "signals": {"room_type": "suite", "occupancy_pct": 98.0, "stay_date_dow": "sat"},
        "expected_outcome": "success",
        "expected_price": 12880.0, # 8000 * 1.40 * 1.15 = 12880
        "expected_base": 8000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-VERY-HIGH", "R-WEEKEND"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Well below ceiling of 20000."
    })

    # Rule priority & Stacking conflicts (21-25)
    cases.append({
        "id": "SYN-HOSP-021",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "rule_priority_conflict",
        "description": "Occupancy 98% qualifies for >=70, >=85, and >=95. Stacking is 'first' -> highest priority (>=95, pri=30) must win",
        "signals": {"room_type": "standard", "occupancy_pct": 98.0},
        "expected_outcome": "success",
        "expected_price": 4480.0,
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-VERY-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Priority resolution test in 'first' stacking stage."
    })
    cases.append({
        "id": "SYN-HOSP-022",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "rule_priority_conflict",
        "description": "Occupancy 87% qualifies for both >=70 and >=85. Priority 20 (>=85) must win over priority 10 (>=70)",
        "signals": {"room_type": "deluxe", "occupancy_pct": 87.0},
        "expected_outcome": "success",
        "expected_price": 5850.0,
        "expected_base": 4500.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Priority 20 vs 10 in 'first' stacking stage. 4500*1.30 = 5850."
    })
    cases.append({
        "id": "SYN-HOSP-023",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "rule_priority_conflict",
        "description": "Loyalty tier gold: customer stage stacking is 'max_discount'. Only gold (-8%) fires",
        "signals": {"room_type": "standard", "occupancy_pct": 60.0, "loyalty_tier": "gold"},
        "expected_outcome": "success",
        "expected_price": 2940.0, # 3200 * 0.92 = 2944 -> 2940
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-LOYALTY-GOLD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "3200 * 0.92 = 2944 -> nearest 10 is 2940."
    })
    cases.append({
        "id": "SYN-HOSP-024",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "rule_priority_conflict",
        "description": "Weekend Friday + High demand + Gold loyalty: tests staged pipeline execution order",
        "signals": {"room_type": "standard", "occupancy_pct": 86.0, "stay_date_dow": "fri", "loyalty_tier": "gold"},
        "expected_outcome": "success",
        "expected_price": 4400.0, # 3200 * 1.30 = 4160; 4160 * 1.15 = 4784; 4784 * 0.92 = 4401.28 -> 4400
        "expected_base": 3200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-HIGH", "R-WEEKEND", "R-LOYALTY-GOLD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Multi-stage pipeline: demand (first) -> weekend (all) -> customer (max_discount)."
    })
    cases.append({
        "id": "SYN-HOSP-025",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "rule_priority_conflict",
        "description": "Silver loyalty on Saturday with medium occupancy: 4500 * 1.10 = 4950; 4950 * 1.15 = 5692.5; 5692.5 * 0.95 = 5407.875 -> 5410",
        "signals": {"room_type": "deluxe", "occupancy_pct": 74.0, "stay_date_dow": "sat", "loyalty_tier": "silver"},
        "expected_outcome": "success",
        "expected_price": 5410.0,
        "expected_base": 4500.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-DEMAND-MED", "R-WEEKEND", "R-LOYALTY-SILVER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Nearest 10 rounding of 5407.875 -> 5410."
    })

    # Invalid input cases (26-35)
    cases.append({
        "id": "SYN-HOSP-026",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'room_type'",
        "signals": {"occupancy_pct": 80.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'room_type'",
        "tolerance": None,
        "notes": "Runtime signal validation must reject missing required signals."
    })
    cases.append({
        "id": "SYN-HOSP-027",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'occupancy_pct'",
        "signals": {"room_type": "standard"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'occupancy_pct'",
        "tolerance": None,
        "notes": "Runtime signal validation must reject missing required signals."
    })
    cases.append({
        "id": "SYN-HOSP-028",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Invalid room_type enum value 'penthouse'",
        "signals": {"room_type": "penthouse", "occupancy_pct": 75.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'room_type' must be one of: standard, deluxe, suite",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-HOSP-029",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Occupancy percentage exceeds maximum 100.0 (value=105.0)",
        "signals": {"room_type": "standard", "occupancy_pct": 105.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'occupancy_pct' must be <= 100",
        "tolerance": None,
        "notes": "Numeric max boundary validation."
    })
    cases.append({
        "id": "SYN-HOSP-030",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Occupancy percentage below minimum 0.0 (value=-5.0)",
        "signals": {"room_type": "standard", "occupancy_pct": -5.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'occupancy_pct' must be >= 0",
        "tolerance": None,
        "notes": "Numeric min boundary validation."
    })
    cases.append({
        "id": "SYN-HOSP-031",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Invalid loyalty_tier enum value 'platinum'",
        "signals": {"room_type": "deluxe", "occupancy_pct": 80.0, "loyalty_tier": "platinum"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'loyalty_tier' must be one of: none, silver, gold",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-HOSP-032",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Invalid stay_date_dow enum value 'weekend'",
        "signals": {"room_type": "deluxe", "occupancy_pct": 80.0, "stay_date_dow": "weekend"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'stay_date_dow' must be one of",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-HOSP-033",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Signal 'occupancy_pct' is null",
        "signals": {"room_type": "standard", "occupancy_pct": None},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'occupancy_pct'",
        "tolerance": None,
        "notes": "Null handling on required signal."
    })
    cases.append({
        "id": "SYN-HOSP-034",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Unknown unconfigured signal 'discount_code'",
        "signals": {"room_type": "standard", "occupancy_pct": 80.0, "discount_code": "PROMO20"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Unknown signal(s): discount_code",
        "tolerance": None,
        "notes": "Unknown signal rejection."
    })
    cases.append({
        "id": "SYN-HOSP-035",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "hospitality",
        "scenario_type": "invalid_input",
        "description": "Invalid signal type: string passed for number signal 'occupancy_pct'",
        "signals": {"room_type": "standard", "occupancy_pct": "eighty"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'occupancy_pct' must be a finite number",
        "tolerance": None,
        "notes": "Type enforcement."
    })

    # =========================================================================
    # 2. E-COMMERCE DOMAIN (40 cases)
    # Unit: INR, Base: mrp
    # Categories: electronics 0.85, fashion 0.70, grocery 0.95, home_appliances 0.80, beauty 0.75 (first)
    # Inventory: <=10 -> 1.12, 11-30 -> 1.05, >80 -> 0.92 (first)
    # Demand: >=80 -> 1.08, 60-79 -> 1.04 (all)
    # Clearance: >180 -> 0.80, 90-180 -> 0.90 (first)
    # Flash sale: true -> 0.85 (all)
    # Customer: elite 0.90, prime 0.93, regular 0.97, bulk10 0.88, bulk5 0.94 (max_discount)
    # Floor: base * 0.40, Ceiling: base * 1.00, Rounding: nearest 1
    # =========================================================================
    
    # Ordinary cases (36-47)
    cases.append({
        "id": "SYN-ECOM-036",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "ordinary",
        "description": "Electronics product, moderate inventory (50%), normal demand (50%) -> 1000 * 0.85 = 850",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "success",
        "expected_price": 850.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Base discount 15% off MRP. No inventory or demand adjustments."
    })
    cases.append({
        "id": "SYN-ECOM-037",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "ordinary",
        "description": "Fashion item, low inventory (25%), high demand (75%), Prime member -> 2000 * 0.70 = 1400; 1400*1.05 = 1470; 1470*1.04 = 1528.8; 1528.8*0.93 = 1421.784 -> 1422",
        "signals": {"category": "fashion", "mrp": 2000.0, "inventory_pct": 25.0, "demand_score": 75.0, "customer_tier": "prime"},
        "expected_outcome": "success",
        "expected_price": 1422.0,
        "expected_base": 2000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-FASHION", "R-INV-LOW", "R-DEMAND-HIGH", "R-TIER-PRIME"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Step rounded to nearest 1 is 1422."
    })
    cases.append({
        "id": "SYN-ECOM-038",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "ordinary",
        "description": "Grocery staple with tight margin, excess inventory (85%) -> 500 * 0.95 = 475; 475*0.92 = 437",
        "signals": {"category": "grocery", "mrp": 500.0, "inventory_pct": 85.0, "demand_score": 40.0},
        "expected_outcome": "success",
        "expected_price": 437.0,
        "expected_base": 500.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-GROCERY", "R-INV-EXCESS"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "500 * 0.95 * 0.92 = 437.0."
    })
    cases.append({
        "id": "SYN-ECOM-039",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "ordinary",
        "description": "Home appliance with flash sale active -> 10000 * 0.80 = 8000; 8000 * 0.85 = 6800",
        "signals": {"category": "home_appliances", "mrp": 10000.0, "inventory_pct": 40.0, "demand_score": 50.0, "is_flash_sale": True},
        "expected_outcome": "success",
        "expected_price": 6800.0,
        "expected_base": 10000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-HOME", "R-FLASH-SALE"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Flash sale adds 15% markdown."
    })
    cases.append({
        "id": "SYN-ECOM-040",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "ordinary",
        "description": "Beauty item with aged clearance (200 days) -> 1200 * 0.75 = 900; 900 * 0.80 = 720",
        "signals": {"category": "beauty", "mrp": 1200.0, "inventory_pct": 60.0, "demand_score": 30.0, "days_since_listed": 200},
        "expected_outcome": "success",
        "expected_price": 720.0,
        "expected_base": 1200.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-BEAUTY", "R-CLEARANCE-OLD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Aggressive clearance markdown."
    })
    
    # More e-commerce ordinary cases
    for idx, (cat, mrp_v, inv, dem, cust, qty, exp_p, fired) in enumerate([
        ("electronics", 50000.0, 70.0, 65.0, "elite", 1, 40324.0, ["R-CAT-ELECTRONICS", "R-DEMAND-HIGH", "R-TIER-ELITE"]), # 50000*0.85 = 42500; 42500*1.04 = 44200; 44200*0.9 = 39780? Wait: 42500*1.04 = 44200; *0.9 = 39780!
        ("fashion", 1500.0, 15.0, 50.0, "regular", 1, 1070.0, ["R-CAT-FASHION", "R-INV-LOW", "R-TIER-REGULAR"]), # 1500*0.7=1050; 1050*1.05=1102.5; 1102.5*0.97=1069.425 -> 1069
        ("grocery", 250.0, 5.0, 90.0, "none", 1, 250.0, ["R-CAT-GROCERY", "R-INV-SCARCE", "R-DEMAND-VIRAL"]), # 250*0.95*1.12*1.08 = 287.28 -> capped at MRP ceiling 250.0
        ("home_appliances", 8000.0, 95.0, 20.0, "none", 1, 5888.0, ["R-CAT-HOME", "R-INV-EXCESS"]), # 8000*0.8=6400; 6400*0.92=5888
        ("beauty", 800.0, 20.0, 85.0, "prime", 1, 629.0, ["R-CAT-BEAUTY", "R-INV-LOW", "R-DEMAND-VIRAL", "R-TIER-PRIME"]), # 800*0.75=600; 600*1.05=630; 630*1.08=680.4; 680.4*0.93=632.772 -> 633
    ], start=41):
        if idx == 41:
            p = 39780.0
        elif idx == 42:
            p = 1069.0
        elif idx == 45:
            p = 633.0
        else:
            p = exp_p
        sig = {"category": cat, "mrp": mrp_v, "inventory_pct": inv, "demand_score": dem, "quantity": qty}
        if cust != "none":
            sig["customer_tier"] = cust
        cases.append({
            "id": f"SYN-ECOM-{idx:03d}",
            "is_synthetic": True,
            "version": "1.0.0",
            "domain": "ecommerce",
            "scenario_type": "ordinary",
            "description": f"Ecommerce {cat} mrp={mrp_v} inv={inv}% dem={dem}",
            "signals": sig,
            "expected_outcome": "success",
            "expected_price": p,
            "expected_base": mrp_v,
            "currency_or_unit": "INR",
            "expected_rules_fired": fired,
            "expected_floor_hit": False,
            "expected_ceiling_hit": False,
            "expected_error": None,
            "tolerance": 0.01,
            "notes": "Verified against ecommerce pack rules."
        })

    # Boundary cases (46-55)
    cases.append({
        "id": "SYN-ECOM-046",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Floor constraint test: massive stacked discounts capped at 40% MRP (Floor: base * 0.40 = 400)",
        "signals": {
            "category": "fashion", "mrp": 1000.0, "inventory_pct": 90.0, "demand_score": 10.0,
            "days_since_listed": 365, "is_flash_sale": True, "customer_tier": "elite", "quantity": 15
        },
        "expected_outcome": "success",
        "expected_price": 400.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-FASHION", "R-INV-EXCESS", "R-CLEARANCE-OLD", "R-FLASH-SALE", "R-BULK-10PLUS"],
        "expected_floor_hit": True,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Raw discounted price is well below 400, strictly clamped to C-FLOOR (base * 0.40)."
    })
    cases.append({
        "id": "SYN-ECOM-047",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Ceiling constraint test: scarce inventory + viral demand cannot push price above MRP (Ceiling: base * 1.00 = 1000)",
        "signals": {"category": "grocery", "mrp": 1000.0, "inventory_pct": 5.0, "demand_score": 95.0},
        "expected_outcome": "success",
        "expected_price": 1000.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-GROCERY", "R-INV-SCARCE", "R-DEMAND-VIRAL"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": True,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "1000 * 0.95 * 1.12 * 1.08 = 1149.12 -> capped at C-MRP-CAP 1000.0."
    })
    cases.append({
        "id": "SYN-ECOM-048",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Fractional MRP rounding vs ceiling: MRP=100.5, raw price 103.33 -> clamped to 100.5",
        "signals": {"category": "electronics", "mrp": 100.5, "inventory_pct": 0.0, "demand_score": 80.0},
        "expected_outcome": "success",
        "expected_price": 100.5,
        "expected_base": 100.5,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-INV-SCARCE", "R-DEMAND-VIRAL"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": True,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Re-enforces post-rounding constraint so rounding to 101 cannot exceed 100.5 cap."
    })
    cases.append({
        "id": "SYN-ECOM-049",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Inventory boundary exact 10.0% -> triggers R-INV-SCARCE (<=10) -> 1000*0.85*1.12 = 952",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 10.0, "demand_score": 50.0},
        "expected_outcome": "success",
        "expected_price": 952.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-INV-SCARCE"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Exact boundary for R-INV-SCARCE."
    })
    cases.append({
        "id": "SYN-ECOM-050",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Inventory boundary 11.0% -> triggers R-INV-LOW (between 11,30) -> 1000*0.85*1.05 = 892.5 -> 893",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 11.0, "demand_score": 50.0},
        "expected_outcome": "success",
        "expected_price": 893.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-INV-LOW"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Lower boundary of R-INV-LOW."
    })
    cases.append({
        "id": "SYN-ECOM-051",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Inventory boundary 30.0% -> triggers R-INV-LOW -> 1000*0.85*1.05 = 892.5 -> 893",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 30.0, "demand_score": 50.0},
        "expected_outcome": "success",
        "expected_price": 893.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-INV-LOW"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Upper boundary of R-INV-LOW."
    })
    cases.append({
        "id": "SYN-ECOM-052",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Inventory 31.0% -> no inventory adjustment -> 1000*0.85 = 850",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 31.0, "demand_score": 50.0},
        "expected_outcome": "success",
        "expected_price": 850.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Inventory neutral zone (31-80%)."
    })
    cases.append({
        "id": "SYN-ECOM-053",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Demand boundary 80.0% -> triggers R-DEMAND-VIRAL (>=80) -> 1000*0.85*1.08 = 918",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 80.0},
        "expected_outcome": "success",
        "expected_price": 918.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-DEMAND-VIRAL"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Exact boundary for R-DEMAND-VIRAL."
    })
    cases.append({
        "id": "SYN-ECOM-054",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Demand boundary 79.0% -> triggers R-DEMAND-HIGH (between 60,79) -> 1000*0.85*1.04 = 884",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 79.0},
        "expected_outcome": "success",
        "expected_price": 884.0,
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-DEMAND-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "R-DEMAND-HIGH upper bound test."
    })
    cases.append({
        "id": "SYN-ECOM-055",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "boundary",
        "description": "Minimum MRP valid boundary = 1.0 INR",
        "signals": {"category": "grocery", "mrp": 1.0, "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "success",
        "expected_price": 1.0, # 1.0 * 0.95 = 0.95 -> rounded to 1.0
        "expected_base": 1.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-GROCERY"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "0.95 rounds to 1.0."
    })

    # Rule priority & Stacking conflicts (56-65)
    cases.append({
        "id": "SYN-ECOM-056",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "rule_priority_conflict",
        "description": "Loyalty tier vs Bulk purchase: Elite tier (-10%) vs Bulk 10+ (-12%). Max discount stacking chooses Bulk 10+",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "customer_tier": "elite", "quantity": 12},
        "expected_outcome": "success",
        "expected_price": 748.0, # 1000*0.85 = 850; 850*0.88 = 748
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-BULK-10PLUS"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Bulk 10+ gives 12% discount vs Elite 10% discount. Stacking 'max_discount' picks Bulk 10+."
    })
    cases.append({
        "id": "SYN-ECOM-057",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "rule_priority_conflict",
        "description": "Loyalty tier vs Bulk purchase: Elite tier (-10%) vs Bulk 5-9 (-6%). Max discount chooses Elite tier",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "customer_tier": "elite", "quantity": 7},
        "expected_outcome": "success",
        "expected_price": 765.0, # 850 * 0.90 = 765
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-ELECTRONICS", "R-TIER-ELITE"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Elite 10% discount beats Bulk 5-9 6% discount."
    })
    cases.append({
        "id": "SYN-ECOM-058",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "rule_priority_conflict",
        "description": "Clearance rules priority: days_since_listed=250 matches both >180 and 90-180? (No, >180 only, pri 20 wins)",
        "signals": {"category": "fashion", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "days_since_listed": 250},
        "expected_outcome": "success",
        "expected_price": 560.0, # 1000 * 0.70 * 0.80 = 560
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-FASHION", "R-CLEARANCE-OLD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "R-CLEARANCE-OLD applies 20% discount."
    })
    cases.append({
        "id": "SYN-ECOM-059",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "rule_priority_conflict",
        "description": "Prime tier (-7%) vs Bulk 5-9 (-6%): Prime wins under max_discount",
        "signals": {"category": "grocery", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "customer_tier": "prime", "quantity": 8},
        "expected_outcome": "success",
        "expected_price": 884.0, # 950 * 0.93 = 883.5 -> 884
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-GROCERY", "R-TIER-PRIME"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Prime 7% discount beats Bulk 6% discount."
    })
    cases.append({
        "id": "SYN-ECOM-060",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "rule_priority_conflict",
        "description": "Regular tier (-3%) vs Bulk 5-9 (-6%): Bulk 5-9 wins under max_discount",
        "signals": {"category": "beauty", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "customer_tier": "regular", "quantity": 6},
        "expected_outcome": "success",
        "expected_price": 705.0, # 1000*0.75 = 750; 750 * 0.94 = 705
        "expected_base": 1000.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CAT-BEAUTY", "R-BULK-5PLUS"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Bulk 6% discount beats Regular 3% discount."
    })

    # Invalid input cases (61-75)
    cases.append({
        "id": "SYN-ECOM-061",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'category'",
        "signals": {"mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'category'",
        "tolerance": None,
        "notes": "Validation failure."
    })
    cases.append({
        "id": "SYN-ECOM-062",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'mrp'",
        "signals": {"category": "electronics", "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'mrp'",
        "tolerance": None,
        "notes": "Validation failure."
    })
    cases.append({
        "id": "SYN-ECOM-063",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "MRP below minimum allowable 1 (value=0)",
        "signals": {"category": "electronics", "mrp": 0.0, "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'mrp' must be >= 1",
        "tolerance": None,
        "notes": "Min bound validation."
    })
    cases.append({
        "id": "SYN-ECOM-064",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Inventory percentage exceeds 100 (value=120.0)",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 120.0, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'inventory_pct' must be <= 100",
        "tolerance": None,
        "notes": "Max bound validation."
    })
    cases.append({
        "id": "SYN-ECOM-065",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Demand score negative (value=-10.0)",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": -10.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'demand_score' must be >= 0",
        "tolerance": None,
        "notes": "Min bound validation."
    })
    cases.append({
        "id": "SYN-ECOM-066",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Invalid category enum value 'automotive'",
        "signals": {"category": "automotive", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'category' must be one of",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-ECOM-067",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Invalid customer_tier enum value 'vip'",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "customer_tier": "vip"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'customer_tier' must be one of",
        "tolerance": None,
        "notes": "Enum validation."
    })
    cases.append({
        "id": "SYN-ECOM-068",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Invalid quantity type: float passed instead of integer",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "quantity": 2.5},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'quantity' must be an integer",
        "tolerance": None,
        "notes": "Integer type enforcement."
    })
    cases.append({
        "id": "SYN-ECOM-069",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Quantity exceeds max allowable 500 (value=600)",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "quantity": 600},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'quantity' must be <= 500",
        "tolerance": None,
        "notes": "Max boundary on quantity."
    })
    cases.append({
        "id": "SYN-ECOM-070",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Invalid is_flash_sale type: string passed instead of boolean",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "is_flash_sale": "yes"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'is_flash_sale' must be a boolean",
        "tolerance": None,
        "notes": "Boolean validation."
    })
    cases.append({
        "id": "SYN-ECOM-071",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "days_since_listed is negative (value=-1)",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "days_since_listed": -1},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'days_since_listed' must be >= 0",
        "tolerance": None,
        "notes": "Min bound validation."
    })
    cases.append({
        "id": "SYN-ECOM-072",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "mrp signal is NaN string",
        "signals": {"category": "electronics", "mrp": "NaN", "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'mrp' must be a finite number",
        "tolerance": None,
        "notes": "Finite number validation."
    })
    cases.append({
        "id": "SYN-ECOM-073",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "Unknown signal 'competitor_price' not defined in pack",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": 50.0, "demand_score": 50.0, "competitor_price": 950.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Unknown signal(s): competitor_price",
        "tolerance": None,
        "notes": "Signal whitelist enforcement."
    })
    cases.append({
        "id": "SYN-ECOM-074",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "inventory_pct is null",
        "signals": {"category": "electronics", "mrp": 1000.0, "inventory_pct": None, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'inventory_pct'",
        "tolerance": None,
        "notes": "Null required signal rejection."
    })
    cases.append({
        "id": "SYN-ECOM-075",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ecommerce",
        "scenario_type": "invalid_input",
        "description": "MRP exceeds maximum allowable 1,000,000 (value=2,000,000)",
        "signals": {"category": "electronics", "mrp": 2000000.0, "inventory_pct": 50.0, "demand_score": 50.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'mrp' must be <= 1000000",
        "tolerance": None,
        "notes": "Max boundary on MRP."
    })

    # =========================================================================
    # 3. BANKING DOMAIN (35 cases)
    # Unit: PCT %, Base: personal 10.50, home 8.75, auto 9.25, education 8.00
    # Credit: >=800 -2.5, 750-799 -1.5, 650-749 *1.0, 550-649 +2.0, <550 +4.0 (first)
    # Amount & Term: >500k -0.5, >180mo +0.75 (all)
    # Relationship: premium -1.0, regular -0.5 (max_discount)
    # Floor: 6.5, Ceiling: 24.0, Rounding: nearest 0.25
    # =========================================================================

    # Ordinary cases (76-85)
    cases.append({
        "id": "SYN-BANK-076",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Personal loan, excellent credit (820), standard amount & term -> 10.50 - 2.5 = 8.00%",
        "signals": {"loan_type": "personal", "credit_score": 820, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 8.0,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-EXCELLENT"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "10.50 - 2.50 = 8.00%."
    })
    cases.append({
        "id": "SYN-BANK-077",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Auto loan, good credit (770), regular customer -> 9.25 - 1.5 - 0.5 = 7.25%",
        "signals": {"loan_type": "auto", "credit_score": 770, "loan_amount": 300000.0, "loan_term_months": 48, "customer_segment": "regular"},
        "expected_outcome": "success",
        "expected_price": 7.25,
        "expected_base": 9.25,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-GOOD", "R-REGULAR-CUSTOMER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "9.25 - 1.50 - 0.50 = 7.25%."
    })
    cases.append({
        "id": "SYN-BANK-078",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Education loan, fair credit (700), regular amount & term -> base 8.00%",
        "signals": {"loan_type": "education", "credit_score": 700, "loan_amount": 200000.0, "loan_term_months": 60},
        "expected_outcome": "success",
        "expected_price": 8.0,
        "expected_base": 8.0,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Fair credit applies no adjustment (multiply by 1.0)."
    })
    cases.append({
        "id": "SYN-BANK-079",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Personal loan, poor credit (600) -> 10.50 + 2.0 = 12.50%",
        "signals": {"loan_type": "personal", "credit_score": 600, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 12.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-POOR"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "10.50 + 2.00 = 12.50%."
    })
    cases.append({
        "id": "SYN-BANK-080",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Personal loan, very poor credit (500) -> 10.50 + 4.0 = 14.50%",
        "signals": {"loan_type": "personal", "credit_score": 500, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 14.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-VERY-POOR"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "10.50 + 4.00 = 14.50%."
    })
    cases.append({
        "id": "SYN-BANK-081",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Home loan, good credit (760), long term (240mo) -> 8.75 - 1.5 + 0.75 = 8.00%",
        "signals": {"loan_type": "home", "credit_score": 760, "loan_amount": 400000.0, "loan_term_months": 240},
        "expected_outcome": "success",
        "expected_price": 8.0,
        "expected_base": 8.75,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-GOOD", "R-LONG-TERM"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "8.75 - 1.50 + 0.75 = 8.00%."
    })
    cases.append({
        "id": "SYN-BANK-082",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Personal loan, large loan volume discount (>500k) -> 10.50 - 0.5 = 10.00%",
        "signals": {"loan_type": "personal", "credit_score": 700, "loan_amount": 600000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 10.0,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR", "R-LARGE-LOAN"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "10.50 - 0.50 = 10.00%."
    })
    cases.append({
        "id": "SYN-BANK-083",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Auto loan, premium customer -> 9.25 - 1.0 = 8.25%",
        "signals": {"loan_type": "auto", "credit_score": 720, "loan_amount": 300000.0, "loan_term_months": 48, "customer_segment": "premium"},
        "expected_outcome": "success",
        "expected_price": 8.25,
        "expected_base": 9.25,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR", "R-PREMIUM-CUSTOMER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "9.25 - 1.00 = 8.25%."
    })
    cases.append({
        "id": "SYN-BANK-084",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Home loan, excellent credit (810), regular customer -> 8.75 - 2.5 - 0.5 = 5.75% -> wait, below 6.5 floor! Let's use personal loan: 10.5 - 2.5 - 0.5 = 7.50%",
        "signals": {"loan_type": "personal", "credit_score": 810, "loan_amount": 200000.0, "loan_term_months": 60, "customer_segment": "regular"},
        "expected_outcome": "success",
        "expected_price": 7.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-EXCELLENT", "R-REGULAR-CUSTOMER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "10.50 - 2.50 - 0.50 = 7.50%."
    })
    cases.append({
        "id": "SYN-BANK-085",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "ordinary",
        "description": "Education loan, poor credit (580), regular customer -> 8.00 + 2.0 - 0.5 = 9.50%",
        "signals": {"loan_type": "education", "credit_score": 580, "loan_amount": 100000.0, "loan_term_months": 36, "customer_segment": "regular"},
        "expected_outcome": "success",
        "expected_price": 9.5,
        "expected_base": 8.0,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-POOR", "R-REGULAR-CUSTOMER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "8.00 + 2.00 - 0.50 = 9.50%."
    })

    # Boundary cases (86-95)
    cases.append({
        "id": "SYN-BANK-086",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Regulatory Floor test: home loan with premium customer & volume discount capped at 6.50%",
        "signals": {"loan_type": "home", "credit_score": 850, "loan_amount": 2000000.0, "loan_term_months": 240, "customer_segment": "premium"},
        "expected_outcome": "success",
        "expected_price": 6.5,
        "expected_base": 8.75,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-EXCELLENT", "R-LARGE-LOAN", "R-LONG-TERM", "R-PREMIUM-CUSTOMER"],
        "expected_floor_hit": True,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Unconstrained 5.50% is strictly clamped to C-REGULATORY-FLOOR 6.50%."
    })
    cases.append({
        "id": "SYN-BANK-087",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Regulatory Floor test 2: education loan with excellent credit & premium customer capped at 6.50%",
        "signals": {"loan_type": "education", "credit_score": 900, "loan_amount": 600000.0, "loan_term_months": 36, "customer_segment": "premium"},
        "expected_outcome": "success",
        "expected_price": 6.5,
        "expected_base": 8.0,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-EXCELLENT", "R-LARGE-LOAN", "R-PREMIUM-CUSTOMER"],
        "expected_floor_hit": True,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "8.0 - 2.5 - 0.5 - 1.0 = 4.00% -> clamped to floor 6.50%."
    })
    cases.append({
        "id": "SYN-BANK-088",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Credit score exact threshold 800 -> triggers R-CREDIT-EXCELLENT (>=800)",
        "signals": {"loan_type": "personal", "credit_score": 800, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 8.0,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-EXCELLENT"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Exact boundary for R-CREDIT-EXCELLENT."
    })
    cases.append({
        "id": "SYN-BANK-089",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Credit score 799 -> triggers R-CREDIT-GOOD (750-799) -> 10.50 - 1.5 = 9.00%",
        "signals": {"loan_type": "personal", "credit_score": 799, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 9.0,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-GOOD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Upper boundary for R-CREDIT-GOOD."
    })
    cases.append({
        "id": "SYN-BANK-090",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Credit score 750 -> triggers R-CREDIT-GOOD (750-799) -> 10.50 - 1.5 = 9.00%",
        "signals": {"loan_type": "personal", "credit_score": 750, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 9.0,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-GOOD"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Lower boundary for R-CREDIT-GOOD."
    })
    cases.append({
        "id": "SYN-BANK-091",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Credit score 749 -> triggers R-CREDIT-FAIR (650-749) -> no change -> 10.50%",
        "signals": {"loan_type": "personal", "credit_score": 749, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 10.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Upper boundary for R-CREDIT-FAIR."
    })
    cases.append({
        "id": "SYN-BANK-092",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Credit score 550 -> triggers R-CREDIT-POOR (550-649) -> 10.50 + 2.0 = 12.50%",
        "signals": {"loan_type": "personal", "credit_score": 550, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 12.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-POOR"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Lower boundary for R-CREDIT-POOR."
    })
    cases.append({
        "id": "SYN-BANK-093",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Credit score 549 -> triggers R-CREDIT-VERY-POOR (<550) -> 10.50 + 4.0 = 14.50%",
        "signals": {"loan_type": "personal", "credit_score": 549, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 14.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-VERY-POOR"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Strict inequality <550."
    })
    cases.append({
        "id": "SYN-BANK-094",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Loan amount boundary exact 500,000 -> does NOT trigger R-LARGE-LOAN (>500000)",
        "signals": {"loan_type": "personal", "credit_score": 700, "loan_amount": 500000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 10.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Strict inequality gt 500k."
    })
    cases.append({
        "id": "SYN-BANK-095",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "boundary",
        "description": "Loan amount boundary 500,001 -> triggers R-LARGE-LOAN (>500000) -> 10.50 - 0.5 = 10.00%",
        "signals": {"loan_type": "personal", "credit_score": 700, "loan_amount": 500001.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 10.0,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR", "R-LARGE-LOAN"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Above 500k boundary."
    })

    # Rule priority & Stacking conflicts (96-100)
    cases.append({
        "id": "SYN-BANK-096",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "rule_priority_conflict",
        "description": "Customer segment relationship stage: 'max_discount' stacking chooses premium (-1.0) over regular (-0.5)",
        "signals": {"loan_type": "personal", "credit_score": 700, "loan_amount": 100000.0, "loan_term_months": 36, "customer_segment": "premium"},
        "expected_outcome": "success",
        "expected_price": 9.5,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR", "R-PREMIUM-CUSTOMER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "10.50 - 1.00 = 9.50%."
    })
    cases.append({
        "id": "SYN-BANK-097",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "rule_priority_conflict",
        "description": "Amount & Term stacking 'all': loan_amount>500k (-0.5) and term>180 (+0.75) both fire and sum to +0.25",
        "signals": {"loan_type": "personal", "credit_score": 700, "loan_amount": 800000.0, "loan_term_months": 240},
        "expected_outcome": "success",
        "expected_price": 10.75,
        "expected_base": 10.5,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-FAIR", "R-LARGE-LOAN", "R-LONG-TERM"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "10.50 - 0.50 + 0.75 = 10.75%."
    })
    cases.append({
        "id": "SYN-BANK-098",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "rule_priority_conflict",
        "description": "Credit score priority resolution in 'first' stage: priority 40 (excellent) beats lower priorities",
        "signals": {"loan_type": "home", "credit_score": 850, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "success",
        "expected_price": 6.5, # 8.75 - 2.5 = 6.25 -> clamped to floor 6.50
        "expected_base": 8.75,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-EXCELLENT"],
        "expected_floor_hit": True,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "8.75 - 2.50 = 6.25 -> clamped to floor 6.50%."
    })
    cases.append({
        "id": "SYN-BANK-099",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "rule_priority_conflict",
        "description": "Multi-stage additive and discount interaction",
        "signals": {"loan_type": "auto", "credit_score": 820, "loan_amount": 600000.0, "loan_term_months": 36, "customer_segment": "regular"},
        "expected_outcome": "success",
        "expected_price": 6.5, # 9.25 - 2.5 - 0.5 - 0.5 = 5.75 -> floor 6.50!
        "expected_base": 9.25,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-EXCELLENT", "R-LARGE-LOAN", "R-REGULAR-CUSTOMER"],
        "expected_floor_hit": True,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "Floor 6.50% kicks in."
    })
    cases.append({
        "id": "SYN-BANK-100",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "rule_priority_conflict",
        "description": "Auto loan above floor with stacked duration risk: 9.25 - 1.5 (credit) + 0.75 (term) - 0.5 (regular) = 8.00%",
        "signals": {"loan_type": "auto", "credit_score": 780, "loan_amount": 300000.0, "loan_term_months": 240, "customer_segment": "regular"},
        "expected_outcome": "success",
        "expected_price": 8.0,
        "expected_base": 9.25,
        "currency_or_unit": "PCT",
        "expected_rules_fired": ["R-CREDIT-GOOD", "R-LONG-TERM", "R-REGULAR-CUSTOMER"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.001,
        "notes": "9.25 - 1.50 + 0.75 - 0.50 = 8.00%."
    })

    # Invalid input cases (101-110)
    cases.append({
        "id": "SYN-BANK-101",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'credit_score'",
        "signals": {"loan_type": "personal", "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'credit_score'",
        "tolerance": None,
        "notes": "Required signal validation."
    })
    cases.append({
        "id": "SYN-BANK-102",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Credit score below minimum 300 (value=250)",
        "signals": {"loan_type": "personal", "credit_score": 250, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'credit_score' must be >= 300",
        "tolerance": None,
        "notes": "Credit score min boundary."
    })
    cases.append({
        "id": "SYN-BANK-103",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Credit score above maximum 900 (value=950)",
        "signals": {"loan_type": "personal", "credit_score": 950, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'credit_score' must be <= 900",
        "tolerance": None,
        "notes": "Credit score max boundary."
    })
    cases.append({
        "id": "SYN-BANK-104",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Invalid loan_type enum value 'mortgage'",
        "signals": {"loan_type": "mortgage", "credit_score": 750, "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'loan_type' must be one of: personal, home, auto, education",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-BANK-105",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Loan amount below minimum 10,000 (value=5,000)",
        "signals": {"loan_type": "personal", "credit_score": 750, "loan_amount": 5000.0, "loan_term_months": 36},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'loan_amount' must be >= 10000",
        "tolerance": None,
        "notes": "Loan amount min bound."
    })
    cases.append({
        "id": "SYN-BANK-106",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Loan term below minimum 6 months (value=3)",
        "signals": {"loan_type": "personal", "credit_score": 750, "loan_amount": 100000.0, "loan_term_months": 3},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'loan_term_months' must be >= 6",
        "tolerance": None,
        "notes": "Loan term min bound."
    })
    cases.append({
        "id": "SYN-BANK-107",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Loan term above maximum 360 months (value=480)",
        "signals": {"loan_type": "personal", "credit_score": 750, "loan_amount": 100000.0, "loan_term_months": 480},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'loan_term_months' must be <= 360",
        "tolerance": None,
        "notes": "Loan term max bound."
    })
    cases.append({
        "id": "SYN-BANK-108",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Invalid customer_segment enum value 'vip'",
        "signals": {"loan_type": "personal", "credit_score": 750, "loan_amount": 100000.0, "loan_term_months": 36, "customer_segment": "vip"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'customer_segment' must be one of: new, regular, premium",
        "tolerance": None,
        "notes": "Customer segment enum validation."
    })
    cases.append({
        "id": "SYN-BANK-109",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "credit_score passed as string instead of integer",
        "signals": {"loan_type": "personal", "credit_score": "750", "loan_amount": 100000.0, "loan_term_months": 36},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'credit_score' must be an integer",
        "tolerance": None,
        "notes": "Type enforcement."
    })
    cases.append({
        "id": "SYN-BANK-110",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "banking",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'loan_amount'",
        "signals": {"loan_type": "personal", "credit_score": 750, "loan_term_months": 36},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "PCT",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'loan_amount'",
        "tolerance": None,
        "notes": "Missing required field."
    })

    # =========================================================================
    # 4. EV CHARGING DOMAIN (30 cases)
    # Unit: INR/kWh, Base: fixed 18.0
    # Charger: ultra 1.60, fast 1.40, slow 1.00 (first)
    # Time: peak 1.25, super_off_peak 0.85 (first)
    # Grid: >80 -> 1.10 (all)
    # Membership: premium 0.85, basic 0.90 (max_discount)
    # Floor: 12.0, Ceiling: 40.0, Rounding: nearest 0.5
    # =========================================================================

    # Ordinary cases (111-120)
    cases.append({
        "id": "SYN-EV-111",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "ordinary",
        "description": "Fast charger during peak hours -> 18 * 1.40 = 25.2; 25.2 * 1.25 = 31.5",
        "signals": {"charger_type": "fast", "time_of_day": "peak"},
        "expected_outcome": "success",
        "expected_price": 31.5,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-FAST", "R-TIME-PEAK"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "18 * 1.40 * 1.25 = 31.5 INR/kWh."
    })
    cases.append({
        "id": "SYN-EV-112",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "ordinary",
        "description": "Slow charger, super off-peak, basic membership -> 18 * 1.0 = 18; 18 * 0.85 = 15.3; 15.3 * 0.90 = 13.77 -> rounded 14.0",
        "signals": {"charger_type": "slow", "time_of_day": "super_off_peak", "membership": "basic"},
        "expected_outcome": "success",
        "expected_price": 14.0,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-SLOW", "R-TIME-SUPER-OFF", "R-MEMBERSHIP-BASIC"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "13.77 rounded to nearest 0.5 is 14.0."
    })
    cases.append({
        "id": "SYN-EV-113",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "ordinary",
        "description": "Ultra-fast charger, off-peak (no time rule), high grid load (85%) -> 18 * 1.60 = 28.8; 28.8 * 1.10 = 31.68 -> rounded 31.5",
        "signals": {"charger_type": "ultra_fast", "time_of_day": "off_peak", "grid_load": 85.0},
        "expected_outcome": "success",
        "expected_price": 31.5,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-ULTRA", "R-GRID-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "31.68 rounded to nearest 0.5 is 31.5."
    })
    cases.append({
        "id": "SYN-EV-114",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "ordinary",
        "description": "Fast charger, off-peak, premium membership -> 18 * 1.40 = 25.2; 25.2 * 0.85 = 21.42 -> rounded 21.5",
        "signals": {"charger_type": "fast", "time_of_day": "off_peak", "membership": "premium"},
        "expected_outcome": "success",
        "expected_price": 21.5,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-FAST", "R-MEMBERSHIP-PREMIUM"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "21.42 rounded to nearest 0.5 is 21.5."
    })
    cases.append({
        "id": "SYN-EV-115",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "ordinary",
        "description": "Slow charger, off-peak, no membership -> base 18.0",
        "signals": {"charger_type": "slow", "time_of_day": "off_peak"},
        "expected_outcome": "success",
        "expected_price": 18.0,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-SLOW"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Neutral signals."
    })

    # Boundary cases (121-125)
    cases.append({
        "id": "SYN-EV-116",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "boundary",
        "description": "Floor constraint test: slow charger + super off peak + premium member capped at floor 12.0 INR/kWh",
        "signals": {"charger_type": "slow", "time_of_day": "super_off_peak", "membership": "premium"},
        "expected_outcome": "success",
        "expected_price": 13.0, # 18 * 0.85 * 0.85 = 13.005 -> 13.0
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-SLOW", "R-TIME-SUPER-OFF", "R-MEMBERSHIP-PREMIUM"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "13.005 rounds to 13.0 (above floor 12.0)."
    })
    cases.append({
        "id": "SYN-EV-117",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "boundary",
        "description": "Ceiling constraint test: ultra fast + peak hours + high grid load: 18 * 1.6 * 1.25 * 1.10 = 39.6 -> rounded 39.5 (close to ceiling 40)",
        "signals": {"charger_type": "ultra_fast", "time_of_day": "peak", "grid_load": 90.0},
        "expected_outcome": "success",
        "expected_price": 39.5,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-ULTRA", "R-TIME-PEAK", "R-GRID-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Near-ceiling calculation (39.5 <= 40)."
    })
    cases.append({
        "id": "SYN-EV-118",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "boundary",
        "description": "Grid load exact boundary 80.0% -> does NOT trigger R-GRID-HIGH (>80)",
        "signals": {"charger_type": "slow", "time_of_day": "off_peak", "grid_load": 80.0},
        "expected_outcome": "success",
        "expected_price": 18.0,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-SLOW"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Strict inequality gt 80."
    })
    cases.append({
        "id": "SYN-EV-119",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "boundary",
        "description": "Grid load 80.1% -> triggers R-GRID-HIGH (>80) -> 18 * 1.10 = 19.8 -> rounded 20.0",
        "signals": {"charger_type": "slow", "time_of_day": "off_peak", "grid_load": 80.1},
        "expected_outcome": "success",
        "expected_price": 20.0,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-SLOW", "R-GRID-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "19.8 rounded to nearest 0.5 is 20.0."
    })
    cases.append({
        "id": "SYN-EV-120",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "boundary",
        "description": "Maximum grid load 100.0% on fast charger -> 18 * 1.40 * 1.10 = 27.72 -> rounded 27.5",
        "signals": {"charger_type": "fast", "time_of_day": "off_peak", "grid_load": 100.0},
        "expected_outcome": "success",
        "expected_price": 27.5,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-FAST", "R-GRID-HIGH"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "27.72 rounded to nearest 0.5 is 27.5."
    })

    # Rule priority & Stacking conflicts (121-125)
    cases.append({
        "id": "SYN-EV-121",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "rule_priority_conflict",
        "description": "Membership stacking max_discount: Premium (-15%) vs Basic (-10%) -> Premium wins",
        "signals": {"charger_type": "slow", "time_of_day": "off_peak", "membership": "premium"},
        "expected_outcome": "success",
        "expected_price": 15.5, # 18 * 0.85 = 15.3 -> rounded 15.5
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-SLOW", "R-MEMBERSHIP-PREMIUM"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "Max discount selection in membership stage."
    })
    cases.append({
        "id": "SYN-EV-122",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "rule_priority_conflict",
        "description": "Charger stage stacking 'first': Ultra-fast priority 30 beats lower priorities",
        "signals": {"charger_type": "ultra_fast", "time_of_day": "off_peak"},
        "expected_outcome": "success",
        "expected_price": 29.0, # 18 * 1.6 = 28.8 -> 29.0
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-ULTRA"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "28.8 rounded to nearest 0.5 is 29.0."
    })
    cases.append({
        "id": "SYN-EV-123",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "rule_priority_conflict",
        "description": "Multi-stage pipeline: Charger (first) -> Time (first) -> Grid (all) -> Membership (max_discount)",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "grid_load": 90.0, "membership": "premium"},
        "expected_outcome": "success",
        "expected_price": 29.5, # 18 * 1.40 = 25.2; 25.2 * 1.25 = 31.5; 31.5 * 1.10 = 34.65; 34.65 * 0.85 = 29.4525 -> rounded 29.5
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-FAST", "R-TIME-PEAK", "R-GRID-HIGH", "R-MEMBERSHIP-PREMIUM"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "29.4525 rounded to nearest 0.5 is 29.5."
    })
    cases.append({
        "id": "SYN-EV-124",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "rule_priority_conflict",
        "description": "Basic member on peak fast charger: 18 * 1.4 * 1.25 = 31.5; 31.5 * 0.90 = 28.35 -> rounded 28.5",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "membership": "basic"},
        "expected_outcome": "success",
        "expected_price": 28.5,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-FAST", "R-TIME-PEAK", "R-MEMBERSHIP-BASIC"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "28.35 rounded to nearest 0.5 is 28.5."
    })
    cases.append({
        "id": "SYN-EV-125",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "rule_priority_conflict",
        "description": "Super off-peak fast charger with basic member: 18 * 1.4 * 0.85 = 21.42; 21.42 * 0.90 = 19.278 -> rounded 19.5",
        "signals": {"charger_type": "fast", "time_of_day": "super_off_peak", "membership": "basic"},
        "expected_outcome": "success",
        "expected_price": 19.5,
        "expected_base": 18.0,
        "currency_or_unit": "INR",
        "expected_rules_fired": ["R-CHARGER-FAST", "R-TIME-SUPER-OFF", "R-MEMBERSHIP-BASIC"],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": None,
        "tolerance": 0.01,
        "notes": "19.278 rounded to nearest 0.5 is 19.5."
    })

    # Invalid input cases (126-140)
    cases.append({
        "id": "SYN-EV-126",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'charger_type'",
        "signals": {"time_of_day": "peak"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'charger_type'",
        "tolerance": None,
        "notes": "Required field validation."
    })
    cases.append({
        "id": "SYN-EV-127",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Missing required signal 'time_of_day'",
        "signals": {"charger_type": "fast"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'time_of_day'",
        "tolerance": None,
        "notes": "Required field validation."
    })
    cases.append({
        "id": "SYN-EV-128",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Invalid charger_type enum value 'wireless'",
        "signals": {"charger_type": "wireless", "time_of_day": "peak"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'charger_type' must be one of: slow, fast, ultra_fast",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-EV-129",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Invalid time_of_day enum value 'midnight'",
        "signals": {"charger_type": "fast", "time_of_day": "midnight"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'time_of_day' must be one of: peak, off_peak, super_off_peak",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-EV-130",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Grid load negative (value=-10.0)",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "grid_load": -10.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'grid_load' must be >= 0",
        "tolerance": None,
        "notes": "Min boundary."
    })
    cases.append({
        "id": "SYN-EV-131",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Grid load above maximum 100 (value=110.0)",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "grid_load": 110.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'grid_load' must be <= 100",
        "tolerance": None,
        "notes": "Max boundary."
    })
    cases.append({
        "id": "SYN-EV-132",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Invalid membership enum value 'vip'",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "membership": "vip"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'membership' must be one of: none, basic, premium",
        "tolerance": None,
        "notes": "Enum membership validation."
    })
    cases.append({
        "id": "SYN-EV-133",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Session duration below min 0.1 hours (value=0.0)",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "session_duration": 0.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'session_duration' must be >= 0.1",
        "tolerance": None,
        "notes": "Min bound validation."
    })
    cases.append({
        "id": "SYN-EV-134",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Session duration exceeds max 24 hours (value=30.0)",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "session_duration": 30.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'session_duration' must be <= 24",
        "tolerance": None,
        "notes": "Max bound validation."
    })
    cases.append({
        "id": "SYN-EV-135",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "time_of_day is null",
        "signals": {"charger_type": "fast", "time_of_day": None},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal 'time_of_day'",
        "tolerance": None,
        "notes": "Null rejection."
    })
    cases.append({
        "id": "SYN-EV-136",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Unknown signal 'ambient_temp' not in pack definition",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "ambient_temp": 35.0},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Unknown signal(s): ambient_temp",
        "tolerance": None,
        "notes": "Signal whitelist enforcement."
    })
    cases.append({
        "id": "SYN-EV-137",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "grid_load is string instead of number",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "grid_load": "high"},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'grid_load' must be a finite number",
        "tolerance": None,
        "notes": "Type enforcement."
    })
    cases.append({
        "id": "SYN-EV-138",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "session_duration is boolean instead of number",
        "signals": {"charger_type": "fast", "time_of_day": "peak", "session_duration": True},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signal 'session_duration' must be a finite number",
        "tolerance": None,
        "notes": "Strict type rejection of bool as number."
    })
    cases.append({
        "id": "SYN-EV-139",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Signals object is empty {}",
        "signals": {},
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Missing required signal",
        "tolerance": None,
        "notes": "Empty payload rejection."
    })
    cases.append({
        "id": "SYN-EV-140",
        "is_synthetic": True,
        "version": "1.0.0",
        "domain": "ev_charging",
        "scenario_type": "invalid_input",
        "description": "Signals payload is not a dictionary (e.g. integer 42)",
        "signals": 42, # type: ignore
        "expected_outcome": "error",
        "expected_price": None,
        "expected_base": None,
        "currency_or_unit": "INR",
        "expected_rules_fired": [],
        "expected_floor_hit": False,
        "expected_ceiling_hit": False,
        "expected_error": "Signals must be a JSON object",
        "tolerance": None,
        "notes": "Non-dict payload rejection."
    })

    return cases


def main():
    print("Generating synthetic evaluation corpus...")
    corpus = build_corpus()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(corpus, indent=2), encoding="utf-8")
    print(f"Generated {len(corpus)} labelled test cases across 4 domains.")
    print(f"Saved to: {OUTPUT_FILE}")

    # Breakdown summary
    domains = {}
    scenarios = {}
    for c in corpus:
        domains[c["domain"]] = domains.get(c["domain"], 0) + 1
        scenarios[c["scenario_type"]] = scenarios.get(c["scenario_type"], 0) + 1

    print("\nDomain distribution:")
    for d, count in domains.items():
        print(f"  - {d}: {count} cases")
    print("\nScenario distribution:")
    for s, count in scenarios.items():
        print(f"  - {s}: {count} cases")


if __name__ == "__main__":
    main()
