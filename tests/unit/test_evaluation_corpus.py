"""
Automated pytest suite for the Track 2 Synthetic Evaluation Corpus.

Runs all 140 labelled test cases from data/synthetic_evaluation_corpus.json,
verifying:
  - Exact price calculations on valid inputs
  - Proper exception raising on invalid inputs
  - Strict guardrail constraint enforcement
  - Trace completeness
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
CORPUS_FILE = ROOT / "data" / "synthetic_evaluation_corpus.json"

from engine.schema.pack import DomainPack
from engine.runtime import compute_price, PricingError


def _load_corpus():
    if not CORPUS_FILE.exists():
        return []
    return json.loads(CORPUS_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def packs():
    packs_dir = ROOT / "packs"
    loaded = {}
    for pack_file in packs_dir.glob("*.json"):
        data = json.loads(pack_file.read_text(encoding="utf-8"))
        pack_id = data.get("pack_id")
        if pack_id:
            loaded[pack_id] = DomainPack.model_validate(data)
    return loaded


CORPUS_CASES = _load_corpus()


@pytest.mark.parametrize("case", CORPUS_CASES, ids=lambda c: c["id"])
def test_synthetic_case(case, packs):
    domain = case["domain"]
    pack = packs[domain]
    signals = case["signals"]
    expected_outcome = case["expected_outcome"]

    if expected_outcome == "success":
        result = compute_price(pack, signals)
        expected_price = case["expected_price"]
        tol = case.get("tolerance") or 0.01

        # Assert price matches expected ground truth within tolerance
        assert abs(float(result.price) - expected_price) <= tol, (
            f"Case {case['id']}: expected {expected_price}, got {float(result.price)}"
        )

        # Assert trace completeness
        assert len(result.trace.steps) > 0
        assert result.fingerprint is not None

        # Assert expected rules fired are present
        actual_fired = {step.rule_id for step in result.trace.steps if step.fired and step.rule_id}
        for exp_rule in case.get("expected_rules_fired", []):
            assert exp_rule in actual_fired, (
                f"Case {case['id']}: expected rule '{exp_rule}' to fire, actual fired: {actual_fired}"
            )

    elif expected_outcome == "error":
        with pytest.raises(PricingError) as exc_info:
            compute_price(pack, signals)

        expected_err = case.get("expected_error")
        if expected_err:
            assert expected_err.lower() in str(exc_info.value).lower(), (
                f"Case {case['id']}: expected error snippet '{expected_err}', got '{str(exc_info.value)}'"
            )
