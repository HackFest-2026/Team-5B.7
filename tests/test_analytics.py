"""
tests/test_analytics.py — Test suite for RateWeaver Sales Dashboard & Analytics endpoints.

Verifies:
  - Sales KPI calculation (revenue, units_sold, order_volume, ASP)
  - Date and domain filters
  - Distinction between completed orders and pricing evaluations
  - Distinction between real orders and synthetic demo dataset
  - Missing metric disclosure (gross margin & conversion rate noted as null)
  - Pricing performance telemetry (evaluation count, price trend, top rules, constraints)
  - What-if simulation comparison contract
  - AI Business Analyst evidence-based answers and honest limitation disclosure
  - Explainable alert generation
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.storage import reset_store_catalogue, execute_checkout_transaction

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_store():
    reset_store_catalogue()


def test_sales_overview_schema_and_synthetic_fallback():
    """Verify sales overview returns correct schema and falls back to synthetic dataset when empty."""
    res = client.get("/v1/analytics/overview?domain=ecommerce&range=7d")
    assert res.status_code == 200
    data = res.json()

    assert "kpis" in data
    kpis = data["kpis"]
    assert "revenue" in kpis
    assert "units_sold" in kpis
    assert "order_volume" in kpis
    assert "average_selling_price" in kpis
    assert kpis["revenue"] >= 0.0
    assert kpis["units_sold"] >= 0
    assert kpis["order_volume"] >= 0
    assert kpis["gross_margin"] is None
    assert "gross_margin_note" in kpis
    assert kpis["conversion_rate"] is None
    assert "conversion_rate_note" in kpis

    # Since catalogue was just reset, no completed orders exist yet, so synthetic is used
    assert data["is_synthetic"] is True
    assert "Synthetic" in data["data_source"]
    assert isinstance(data["sales_trend"], list)
    assert isinstance(data["top_products"], list)


def test_sales_overview_live_completed_order():
    """Verify that completing a real order switches dataset to live and calculates exact KPIs."""
    # Place a real order
    key = f"key_{uuid.uuid4().hex}"
    items = [{"product_id": "ec-001", "quantity": 2, "expected_unit_price": None}]
    order = execute_checkout_transaction(
        idempotency_key=key,
        items=items,
        customer_tier="guest",
    )
    assert order["status"] == "confirmed"
    order_total = order["total_price"]

    # Query overview
    res = client.get("/v1/analytics/overview?domain=ecommerce&range=7d")
    assert res.status_code == 200
    data = res.json()

    # Now live orders exist!
    assert data["is_synthetic"] is False
    assert "Authoritative Storefront" in data["data_source"]
    assert data["kpis"]["revenue"] == order_total
    assert data["kpis"]["units_sold"] == 2
    assert data["kpis"]["order_volume"] == 1
    assert data["kpis"]["average_selling_price"] == round(order_total / 2, 2)


def test_pricing_performance_telemetry():
    """Verify pricing performance endpoint returns evaluation counts and rule aggregations."""
    # First invoke /v1/price to generate telemetry
    price_res = client.post(
        "/v1/price",
        json={
            "domain": "ecommerce",
            "signals": {
                "category": "electronics",
                "mrp": 999.0,
                "inventory_pct": 5.0,
                "demand_score": 85.0,
                "days_since_listed": 30,
                "customer_tier": "prime",
                "is_flash_sale": True,
                "quantity": 1,
            },
        },
    )
    assert price_res.status_code == 200

    perf_res = client.get("/v1/analytics/pricing-performance?domain=ecommerce&limit=20")
    assert perf_res.status_code == 200
    perf = perf_res.json()

    assert perf["domain"] == "ecommerce"
    assert "evaluation_count" in perf
    assert perf["evaluation_count"] >= 1
    assert "pricing_source" in perf
    assert isinstance(perf["top_rules"], list)
    assert isinstance(perf["price_trend"], list)


def test_what_if_simulation_compare():
    """Verify /v1/simulate/compare endpoint for What-If scenario analysis."""
    base_signals = {
        "category": "electronics",
        "mrp": 1000.0,
        "inventory_pct": 50.0,
        "demand_score": 20.0,
        "days_since_listed": 45,
        "customer_tier": "guest",
        "is_flash_sale": False,
        "quantity": 1,
    }
    proposed_signals = {
        **base_signals,
        "demand_score": 90.0,
        "is_flash_sale": True,
        "customer_tier": "elite",
    }

    comp_res = client.post(
        "/v1/simulate/compare",
        json={
            "domain": "ecommerce",
            "signals_before": base_signals,
            "signals_after": proposed_signals,
        },
    )
    assert comp_res.status_code == 200
    comp = comp_res.json()
    assert "before" in comp
    assert "after" in comp
    assert "delta" in comp
    assert "delta_pct" in comp
    assert comp["before"]["price"] > 0
    assert comp["after"]["price"] > 0


def test_analyst_domain_sales_query():
    """Verify AI analyst answers questions regarding domain sales with evidence."""
    res = client.post(
        "/v1/analytics/analyst",
        json={"query": "Which domain had the most sales?", "domain": "ecommerce"},
    )
    assert res.status_code == 200
    ans = res.json()
    assert ans["can_answer"] is True
    assert "E-commerce" in ans["answer"]
    assert "revenue" in ans["evidence"]


def test_analyst_frequent_rules_query():
    """Verify AI analyst answers rule trigger questions."""
    # Ensure at least one pricing evaluation is logged
    client.post(
        "/v1/price",
        json={
            "domain": "ecommerce",
            "signals": {
                "category": "electronics",
                "mrp": 1200.0,
                "inventory_pct": 40.0,
                "demand_score": 30.0,
                "days_since_listed": 20,
                "customer_tier": "regular",
                "is_flash_sale": False,
                "quantity": 1,
            },
        },
    )

    res = client.post(
        "/v1/analytics/analyst",
        json={"query": "Which pricing rules triggered most frequently?", "domain": "ecommerce"},
    )
    assert res.status_code == 200
    ans = res.json()
    assert ans["can_answer"] is True
    assert "evidence" in ans


def test_analyst_unsupported_metrics_query():
    """Verify AI analyst honestly discloses when requested metrics are unavailable."""
    res = client.post(
        "/v1/analytics/analyst",
        json={"query": "What is our net profit margin on power banks?", "domain": "ecommerce"},
    )
    assert res.status_code == 200
    ans = res.json()
    assert ans["can_answer"] is False
    assert "cannot be answered" in ans["answer"].lower()
    assert ans["limitation_note"] is not None


def test_alerts_endpoint():
    """Verify alerts endpoint returns explainable threshold-driven alerts."""
    res = client.get("/v1/analytics/alerts?domain=ecommerce")
    assert res.status_code == 200
    alerts = res.json()
    assert isinstance(alerts, list)
    for alt in alerts:
        assert "title" in alt
        assert "fact" in alt
        assert "recommendation" in alt
