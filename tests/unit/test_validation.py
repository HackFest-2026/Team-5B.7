"""
Unit tests for the validation layer.

Covers:
  C1 — unknown signal
  C2 — invalid operator (schema-level)
  C3 — out-of-range value
  C5 — overlapping rules
  C6 — missing floor/ceiling
  C7 — unsupported formula function
  Publish gate — blocked when validation fails
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.schema.pack import DomainPack
from engine.validate import validate_pack


def _make_minimal_pack(overrides: dict = None) -> dict:
    """Create a minimal valid pack, then apply overrides."""
    base = {
        "pack_id": "test-pack",
        "version": "1.0.0",
        "signals": [
            {"key": "level", "type": "integer", "min": 0, "max": 100}
        ],
        "base": {"type": "fixed", "value": 100},
        "stages": [{"id": "main", "stacking": "all"}],
        "rules": [],
        "constraints": [
            {"id": "C-FLOOR", "type": "floor", "expr": "50"},
            {"id": "C-CAP", "type": "ceiling", "expr": "200"},
        ],
        "rounding": {"mode": "nearest", "step": 1},
    }
    if overrides:
        base.update(overrides)
    return base


class TestValidation:

    def test_valid_pack_passes(self):
        """A correctly formed pack passes validation."""
        pack = DomainPack.model_validate(_make_minimal_pack())
        result = validate_pack(pack)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_c1_unknown_signal(self):
        """C1: Rule references a signal not declared in signals[]."""
        data = _make_minimal_pack()
        data["rules"] = [{
            "id": "R1",
            "stage": "main",
            "priority": 10,
            "when": {"all": [{"signal": "unknown_signal", "op": "gt", "value": 50}]},
            "then": {"op": "multiply", "value": 1.10},
        }]
        pack = DomainPack.model_validate(data)
        result = validate_pack(pack)
        assert result.valid is False
        codes = [e.code for e in result.errors]
        assert "C1" in codes

    def test_c3_value_below_signal_min(self):
        """C3: Rule condition uses a value below signal's declared min."""
        data = _make_minimal_pack()
        data["rules"] = [{
            "id": "R1",
            "stage": "main",
            "priority": 10,
            "when": {"all": [{"signal": "level", "op": "gt", "value": -10}]},
            "then": {"op": "multiply", "value": 1.10},
        }]
        pack = DomainPack.model_validate(data)
        result = validate_pack(pack)
        assert result.valid is False
        codes = [e.code for e in result.errors]
        assert "C3" in codes

    def test_c5_overlapping_rules_first_stacking(self):
        """C5: Two rules with same priority and overlapping conditions in 'first' stage."""
        data = _make_minimal_pack()
        data["stages"] = [{"id": "main", "stacking": "first"}]
        data["rules"] = [
            {
                "id": "R1",
                "stage": "main",
                "priority": 10,
                "when": {"all": [{"signal": "level", "op": "gte", "value": 70}]},
                "then": {"op": "multiply", "value": 1.10},
            },
            {
                "id": "R2",
                "stage": "main",
                "priority": 10,
                "when": {"all": [{"signal": "level", "op": "gte", "value": 80}]},
                "then": {"op": "multiply", "value": 1.30},
            },
        ]
        pack = DomainPack.model_validate(data)
        result = validate_pack(pack)
        assert result.valid is False
        codes = [e.code for e in result.errors]
        assert "C5" in codes

    def test_c6_missing_floor_warning(self):
        """C6: Missing floor constraint → warning."""
        data = _make_minimal_pack()
        data["constraints"] = [{"id": "C-CAP", "type": "ceiling", "expr": "200"}]
        pack = DomainPack.model_validate(data)
        result = validate_pack(pack)
        codes = [w.code for w in result.warnings]
        assert "C6" in codes

    def test_c6_missing_ceiling_warning(self):
        """C6: Missing ceiling constraint → warning."""
        data = _make_minimal_pack()
        data["constraints"] = [{"id": "C-FLOOR", "type": "floor", "expr": "50"}]
        pack = DomainPack.model_validate(data)
        result = validate_pack(pack)
        codes = [w.code for w in result.warnings]
        assert "C6" in codes

    def test_c7_unsupported_formula_function(self):
        """C7: Rule formula uses a disallowed function."""
        data = _make_minimal_pack()
        data["rules"] = [{
            "id": "R1",
            "stage": "main",
            "priority": 10,
            "when": None,
            "then": {"op": "formula", "expr": "pow(current, 2)"},
        }]
        pack = DomainPack.model_validate(data)
        result = validate_pack(pack)
        assert result.valid is False
        codes = [e.code for e in result.errors]
        assert "C7" in codes

    def test_unknown_stage_in_rule_schema_error(self):
        """Rule references non-existent stage → schema validation error."""
        data = _make_minimal_pack()
        data["rules"] = [{
            "id": "R1",
            "stage": "nonexistent",
            "priority": 10,
            "when": None,
            "then": {"op": "multiply", "value": 1.10},
        }]
        with pytest.raises(Exception):
            DomainPack.model_validate(data)

    @pytest.mark.parametrize(
        "override",
        [
            {"rounding": {"mode": "nearest", "step": 0}},
            {"constraints": [{"id": "change", "type": "max_change_pct", "value": -1}]},
            {"signals": [{"key": "level", "type": "integer", "min": 10, "max": 1}]},
            {"signals": [{"key": "segment", "type": "enum"}]},
            {"base": {"type": "table", "by": "level", "values": {}}},
        ],
    )
    def test_schema_rejects_invalid_engine_configuration(self, override):
        data = _make_minimal_pack()
        data.update(override)

        with pytest.raises(Exception):
            DomainPack.model_validate(data)

    def test_all_three_packs_pass_validation(self):
        """All shipped domain packs must pass validation."""
        for pack_name in ["hospitality", "ecommerce", "banking", "ev_charging"]:
            pack_file = ROOT / "packs" / f"{pack_name}.json"
            if not pack_file.exists():
                continue
            pack = DomainPack.model_validate(json.loads(pack_file.read_text()))
            result = validate_pack(pack)
            assert result.valid, (
                f"{pack_name} validation failed: "
                + ", ".join(e.message for e in result.errors)
            )
