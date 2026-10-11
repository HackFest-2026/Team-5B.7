"""
Golden tests for the Banking domain (loan interest rate pricing).
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

PACK_FILE = ROOT / "packs" / "banking.json"


@pytest.fixture(scope="module")
def bank_pack() -> DomainPack:
    data = json.loads(PACK_FILE.read_text())
    return DomainPack.model_validate(data)


class TestBankingGolden:
    """
    Base rates: personal=10.50, home=8.75, auto=9.25, education=8.00
    Credit: ≥800→-2.5, 750-799→-1.5, 650-749→0, 550-649→+2, <550→+4
    Amount: >500k→-0.5
    Term: >180mo→+0.75
    Relationship: premium→-1.0, regular→-0.5
    Floor: 6.5   Ceiling: 24.0
    Rounding: nearest 0.25
    """

    def test_personal_excellent_credit(self, bank_pack):
        """Personal loan, credit=820 → base-2.5=8.0%, round to nearest 0.25→8.0."""
        result = compute_price(bank_pack, {
            "loan_type": "personal",
            "credit_score": 820,
            "loan_amount": 100000,
            "loan_term_months": 36,
        })
        assert result.price == Decimal("8.0")

    def test_personal_good_credit(self, bank_pack):
        """Personal loan, credit=770 → base-1.5=9.0%."""
        result = compute_price(bank_pack, {
            "loan_type": "personal",
            "credit_score": 770,
            "loan_amount": 100000,
            "loan_term_months": 36,
        })
        assert result.price == Decimal("9.0")

    def test_personal_poor_credit(self, bank_pack):
        """Personal loan, credit=580 → base+2.0=12.5%."""
        result = compute_price(bank_pack, {
            "loan_type": "personal",
            "credit_score": 580,
            "loan_amount": 100000,
            "loan_term_months": 36,
        })
        assert result.price == Decimal("12.5")

    def test_home_excellent_premium_customer(self, bank_pack):
        """Home loan, credit=850, premium customer, large loan, long term -> 8.75 - 2.5 (credit) - 0.5 (large) + 0.75 (term) - 1.0 (premium) = 5.50%, capped by 6.50% regulatory floor."""
        result = compute_price(bank_pack, {
            "loan_type": "home",
            "credit_score": 850,
            "loan_amount": 2000000,
            "loan_term_months": 240,
            "customer_segment": "premium",
        })
        assert result.price == Decimal("6.50")

    def test_regulatory_floor(self, bank_pack):
        """Rate can never go below 6.5% (regulatory floor)."""
        result = compute_price(bank_pack, {
            "loan_type": "education",
            "credit_score": 900,
            "loan_amount": 600000,
            "loan_term_months": 36,
            "customer_segment": "premium",
        })
        # education base=8.0, excellent: -2.5=5.5, large loan: -0.5=5.0, premium: -1.0=4.0
        # floor=6.5 kicks in → 6.5
        assert result.price == Decimal("6.5")

    def test_regulatory_ceiling(self, bank_pack):
        """Rate can never exceed 24.0%."""
        result = compute_price(bank_pack, {
            "loan_type": "personal",
            "credit_score": 300,
            "loan_amount": 50000,
            "loan_term_months": 360,
        })
        assert float(result.price) <= 24.0

    def test_determinism(self, bank_pack):
        """Same input → same fingerprint."""
        signals = {
            "loan_type": "personal",
            "credit_score": 700,
            "loan_amount": 200000,
            "loan_term_months": 60,
            "customer_segment": "regular",
        }
        r1 = compute_price(bank_pack, signals)
        r2 = compute_price(bank_pack, signals)
        assert r1.fingerprint == r2.fingerprint

    def test_large_loan_discount(self, bank_pack):
        """Loan >500k gets -0.5pp volume discount."""
        signals_small = {
            "loan_type": "personal", "credit_score": 700,
            "loan_amount": 100000, "loan_term_months": 36,
        }
        signals_large = {
            "loan_type": "personal", "credit_score": 700,
            "loan_amount": 600000, "loan_term_months": 36,
        }
        small = compute_price(bank_pack, signals_small).price
        large = compute_price(bank_pack, signals_large).price
        assert large < small  # large loan has volume discount

    def test_rounding_step_025(self, bank_pack):
        """Output must always be a multiple of 0.25."""
        result = compute_price(bank_pack, {
            "loan_type": "personal",
            "credit_score": 700,
            "loan_amount": 100000,
            "loan_term_months": 36,
        })
        remainder = float(result.price) % 0.25
        assert abs(remainder) < 0.001 or abs(remainder - 0.25) < 0.001
