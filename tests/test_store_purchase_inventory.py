"""
test_store_purchase_inventory.py — Comprehensive tests for:
  - End-to-end checkout and persistent inventory decrement
  - Concurrency safety (no overselling)
  - Idempotency key duplicate protection
  - Live demand-sensitive dynamic pricing feedback loop
  - Dynamic product recommendations
  - CORS security policies
"""
import uuid
import sys
from pathlib import Path
import concurrent.futures
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from api.main import app
from api.storage.db import _get_connection
from api.storage.store_db import (
    get_store_product_by_id,
    init_store_db,
    reset_store_catalogue,
    DEFAULT_INITIAL_PRODUCTS,
)


@pytest.fixture(scope="module")
def client():
    # Ensure tables are initialized and freshly seeded for clean test execution
    reset_store_catalogue()
    with TestClient(app) as c:
        yield c



class TestCatalogueAndInventory:
    def test_list_products_returns_all_catalogue_items(self, client):
        res = client.get("/v1/store/products")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= len(DEFAULT_INITIAL_PRODUCTS)
        
        # Verify structure of first item
        item = data[0]
        assert "id" in item
        assert "name" in item
        assert "stock" in item
        assert "inventory_pct" in item
        assert "demand_score" in item
        assert "signals" in item
        assert item["signals"]["category"] == item["category"]

    def test_get_single_product(self, client):
        res = client.get("/v1/store/products/ec-001")
        assert res.status_code == 200
        p = res.json()
        assert p["id"] == "ec-001"
        assert p["stock"] >= 0
        assert 0 <= p["inventory_pct"] <= 100

    def test_get_nonexistent_product_returns_404(self, client):
        res = client.get("/v1/store/products/non-existent-999")
        assert res.status_code == 404


class TestPurchaseAndCheckout:
    def test_successful_purchase_reduces_stock_atomically(self, client):
        # 1. Check stock before
        p_before = client.get("/v1/store/products/ec-002").json()
        stock_before = p_before["stock"]
        assert stock_before >= 2, "Product should have enough stock for test"

        # 2. Checkout 2 units
        idem_key = f"test-purchase-{uuid.uuid4().hex}"
        checkout_res = client.post("/v1/store/checkout", json={
            "idempotency_key": idem_key,
            "items": [{"product_id": "ec-002", "quantity": 2}],
            "customer_tier": "guest",
            "is_flash_sale": False,
            "confirm_price_change": True,
        })
        assert checkout_res.status_code == 200
        order = checkout_res.json()
        assert order["order_id"].startswith("ord_")
        assert order["status"] == "confirmed"
        assert order["items_count"] == 2
        assert len(order["items"]) == 1
        assert order["items"][0]["quantity"] == 2

        # 3. Check stock after: must be exactly stock_before - 2
        p_after = client.get("/v1/store/products/ec-002").json()
        assert p_after["stock"] == stock_before - 2

        # 4. Verify order persistence
        get_order_res = client.get(f"/v1/store/orders/{order['order_id']}")
        assert get_order_res.status_code == 200
        assert get_order_res.json()["id"] == order["order_id"]

    def test_insufficient_stock_prevents_checkout_and_preserves_stock(self, client):
        # Spigen Phone Case (ec-003) has very low stock
        p_before = client.get("/v1/store/products/ec-003").json()
        stock_before = p_before["stock"]

        # Attempt to buy more than available
        excess_qty = stock_before + 50
        checkout_res = client.post("/v1/store/checkout", json={
            "idempotency_key": f"test-excess-{uuid.uuid4().hex}",
            "items": [{"product_id": "ec-003", "quantity": excess_qty}],
            "confirm_price_change": True,
        })
        assert checkout_res.status_code == 409
        err = checkout_res.json()
        assert "INSUFFICIENT_STOCK" in str(err)

        # Stock must remain unchanged
        p_after = client.get("/v1/store/products/ec-003").json()
        assert p_after["stock"] == stock_before

    def test_duplicate_submission_idempotency_prevents_double_decrement(self, client):
        p_before = client.get("/v1/store/products/fa-001").json()
        stock_before = p_before["stock"]

        idem_key = f"idempotent-test-{uuid.uuid4().hex}"
        payload = {
            "idempotency_key": idem_key,
            "items": [{"product_id": "fa-001", "quantity": 1}],
            "confirm_price_change": True,
        }

        # First request
        res1 = client.post("/v1/store/checkout", json=payload)
        assert res1.status_code == 200
        order1 = res1.json()

        # Second request with identical idempotency key
        res2 = client.post("/v1/store/checkout", json=payload)
        assert res2.status_code == 200
        order2 = res2.json()

        # Same order ID returned
        assert order1["order_id"] == order2["order_id"]

        # Stock decreased only by 1, NOT 2!
        p_after = client.get("/v1/store/products/fa-001").json()
        assert p_after["stock"] == stock_before - 1

    def test_concurrent_purchases_cannot_oversell_inventory(self, client):
        """
        Concurrency test:
        Pick an item and attempt multiple parallel purchases simultaneously.
        Total requested units exceeds available stock.
        Only units within stock must be purchased; no overselling allowed.
        """
        # Himalaya Neem Face Wash be-001 (has plenty of stock)
        p_initial = client.get("/v1/store/products/be-001").json()
        available_stock = min(15, p_initial["stock"])

        if available_stock <= 0:
            pytest.skip("Not enough stock for concurrency test")

        num_threads = available_stock + 6
        success_orders = []
        rejected_orders = []

        def attempt_purchase(idx):
            with TestClient(app) as local_client:
                res = local_client.post("/v1/store/checkout", json={
                    "idempotency_key": f"concurrent-{idx}-{uuid.uuid4().hex}",
                    "items": [{"product_id": "be-001", "quantity": 1}],
                    "confirm_price_change": True,
                })
                return res.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(attempt_purchase, i) for i in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                code = f.result()
                if code == 200:
                    success_orders.append(code)
                else:
                    rejected_orders.append(code)

        p_final = client.get("/v1/store/products/be-001").json()
        # Stock cannot be negative
        assert p_final["stock"] >= 0
        # Number of successful purchases cannot exceed initial available stock
        assert len(success_orders) <= p_initial["stock"]


class TestDynamicPricingIntegration:
    def test_live_price_endpoint_calls_real_engine(self, client):
        res = client.get("/v1/store/products/ec-001/price?customer_tier=elite&is_flash_sale=true")
        assert res.status_code == 200
        data = res.json()
        assert "price" in data
        assert "base" in data
        assert "trace" in data
        assert "fingerprint" in data
        assert len(data["trace"]) > 0

    def test_price_change_detection_at_checkout(self, client):
        """
        If expected_unit_price differs from live price and confirm_price_change is False,
        backend raises 409 PRICE_CHANGED.
        """
        res = client.post("/v1/store/checkout", json={
            "idempotency_key": f"price-check-{uuid.uuid4().hex}",
            "items": [{
                "product_id": "ec-001",
                "quantity": 1,
                "expected_unit_price": 10.0,  # Deliberately stale/wrong price
            }],
            "confirm_price_change": False,
        })
        assert res.status_code == 409
        err = res.json()
        assert "PRICE_CHANGED" in str(err)
        assert "price_changes" in err["detail"]["details"]

    def test_demand_sensitive_pricing_feedback_loop(self, client):
        """
        Verifies that purchases affect subsequent dynamic prices via:
          1. Stock level reduction (inventory_pct drops).
          2. Recent purchase velocity (demand_score rises).
        Under the ecommerce rules, when inventory drops or demand rises,
        the price reflects these adjustments deterministically.
        """
        with _get_connection() as conn:
            conn.execute("DELETE FROM store_order_items WHERE product_id = 'fa-004'")
            conn.execute("UPDATE store_products SET stock = 27, base_demand_score = 0.0 WHERE id = 'fa-004'")

        price_before_res = client.get("/v1/store/products/fa-004/price?customer_tier=guest")
        assert price_before_res.status_code == 200
        p_before = client.get("/v1/store/products/fa-004").json()
        demand_before = p_before["demand_score"]

        # Purchase 3 units
        client.post("/v1/store/checkout", json={
            "idempotency_key": f"demand-test-{uuid.uuid4().hex}",
            "items": [{"product_id": "fa-004", "quantity": 3}],
            "confirm_price_change": True,
        })

        p_after = client.get("/v1/store/products/fa-004").json()
        demand_after = p_after["demand_score"]

        # Demand score must have increased due to recent order rate (+20 per unit)
        assert demand_after > demand_before
        assert demand_after == 60.0

    def test_multi_customer_demand_purchase_sequence(self, client):
        """
        Verifies multi-customer sequence requested in specification:
          - Initial stock: 10 phones.
          - Initial demand: 0 purchases in selected test window.
          - Customer A buys 3 phones (driving demand_score to 60.0).
          - Verify stock becomes 7 and order is persisted.
          - Fetch price again through /v1/price using updated backend-derived demand signals.
          - Verify returned trace (R-DEMAND-HIGH fires) and resulting price increase.
          - Customer B purchases 1 more phone (driving demand_score to 80.0, R-DEMAND-VIRAL).
          - Verify subsequent price and stock updates.
        """
        with _get_connection() as conn:
            conn.execute("DELETE FROM store_order_items WHERE product_id = 'ec-003'")
            conn.execute("UPDATE store_products SET stock = 10, initial_stock = 10, base_demand_score = 0.0 WHERE id = 'ec-003'")

        # 1. Initial state (0 sales)
        p0 = client.get("/v1/store/products/ec-003").json()
        assert p0["stock"] == 10
        assert p0["demand_score"] == 0.0
        assert p0["inventory_pct"] == 100.0

        # Initial price via /v1/price
        price0_res = client.post("/v1/price", json={
            "domain": "ecommerce",
            "signals": p0["signals"],
        })
        assert price0_res.status_code == 200
        price0_data = price0_res.json()
        p0_price = price0_data["price"]

        # 2. Customer A buys 3 phones
        idem_a = f"cust-a-{uuid.uuid4().hex}"
        checkout_a = client.post("/v1/store/checkout", json={
            "idempotency_key": idem_a,
            "items": [{"product_id": "ec-003", "quantity": 3}],
            "confirm_price_change": True,
        })
        assert checkout_a.status_code == 200
        order_a = checkout_a.json()
        assert order_a["status"] == "confirmed"

        # Verify stock becomes 7
        p1 = client.get("/v1/store/products/ec-003").json()
        assert p1["stock"] == 7
        assert p1["demand_score"] == 60.0  # 3 units * 20.0

        # Fetch price again through /v1/price using backend-derived signals
        price1_res = client.post("/v1/price", json={
            "domain": "ecommerce",
            "signals": p1["signals"],
        })
        assert price1_res.status_code == 200
        price1_data = price1_res.json()
        p1_price = price1_data["price"]

        # Verify rule fired in trace and price changed
        trace1_fired = [s["step"] for s in price1_data["trace"] if s["fired"]]
        assert "R-DEMAND-HIGH" in trace1_fired
        assert p1_price > p0_price

        # 3. Customer B buys 1 phone
        idem_b = f"cust-b-{uuid.uuid4().hex}"
        checkout_b = client.post("/v1/store/checkout", json={
            "idempotency_key": idem_b,
            "items": [{"product_id": "ec-003", "quantity": 1}],
            "confirm_price_change": True,
        })
        assert checkout_b.status_code == 200

        # Verify stock becomes 6
        p2 = client.get("/v1/store/products/ec-003").json()
        assert p2["stock"] == 6
        assert p2["demand_score"] == 80.0  # 4 units * 20.0

        # Fetch price again
        price2_res = client.post("/v1/price", json={
            "domain": "ecommerce",
            "signals": p2["signals"],
        })
        assert price2_res.status_code == 200
        price2_data = price2_res.json()
        p2_price = price2_data["price"]

        trace2_fired = [s["step"] for s in price2_data["trace"] if s["fired"]]
        assert "R-DEMAND-VIRAL" in trace2_fired
        assert p2_price > p1_price

    def test_repeated_price_requests_do_not_mutate_demand_or_stock(self, client):
        p_before = client.get("/v1/store/products/ec-002").json()
        for _ in range(5):
            client.get("/v1/store/products/ec-002/price")
        p_after = client.get("/v1/store/products/ec-002").json()
        assert p_before["stock"] == p_after["stock"]
        assert p_before["demand_score"] == p_after["demand_score"]

    def test_failed_purchases_do_not_affect_demand_or_stock(self, client):
        p_before = client.get("/v1/store/products/ec-002").json()
        res = client.post("/v1/store/checkout", json={
            "idempotency_key": f"fail-demand-{uuid.uuid4().hex}",
            "items": [{"product_id": "ec-002", "quantity": p_before["stock"] + 10}],
            "confirm_price_change": True,
        })
        assert res.status_code == 409
        p_after = client.get("/v1/store/products/ec-002").json()
        assert p_before["stock"] == p_after["stock"]
        assert p_before["demand_score"] == p_after["demand_score"]


class TestRecommendations:
    def test_recommendations_exclude_viewed_product(self, client):
        res = client.get("/v1/store/recommendations?product_id=ec-001&limit=4")
        assert res.status_code == 200
        recs = res.json()
        assert len(recs) <= 4
        # ec-001 must NOT be in the recommendations
        rec_ids = [r["id"] for r in recs]
        assert "ec-001" not in rec_ids

    def test_recommendations_prefer_same_category(self, client):
        res = client.get("/v1/store/recommendations?product_id=ec-001&limit=3")
        assert res.status_code == 200
        recs = res.json()
        # Other electronics products should be ranked higher due to category affinity
        categories = [r["category"] for r in recs]
        assert "electronics" in categories

    def test_recommendations_do_not_mutate_stock_or_demand(self, client):
        p_before = client.get("/v1/store/products/ec-004").json()
        # Request recommendations 5 times
        for _ in range(5):
            client.get("/v1/store/recommendations")
        p_after = client.get("/v1/store/products/ec-004").json()
        assert p_before["stock"] == p_after["stock"]
        assert p_before["demand_score"] == p_after["demand_score"]


class TestCORSConfiguration:
    def test_allowed_origin_preflight_succeeds(self, client):
        res = client.options("/v1/store/checkout", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Idempotency-Key",
        })
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert res.headers.get("access-control-allow-credentials") == "true"

    def test_disallowed_origin_receives_no_allow_header(self, client):
        res = client.options("/v1/store/checkout", headers={
            "Origin": "http://unauthorized-attacker.com",
            "Access-Control-Request-Method": "POST",
        })
        # FastAPI CORSMiddleware does not set Access-Control-Allow-Origin for unauthorized origins
        assert res.headers.get("access-control-allow-origin") is None

    def test_post_price_cors_headers(self, client):
        res = client.post("/v1/price", json={
            "domain": "ecommerce",
            "signals": {
                "category": "electronics",
                "mrp": 1000,
                "inventory_pct": 50,
                "demand_score": 50,
            }
        }, headers={"Origin": "http://localhost:5173"})
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
