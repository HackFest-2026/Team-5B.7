"""
store_db.py — Persistent inventory, orders, and recommendation store for RateWeaver.

Uses SQLite with transactional concurrency control:
  - Atomic stock check and decrement
  - Idempotency key protection
  - Dynamic demand score calculation from recent order rate
  - Dynamic inventory_pct calculation from live stock level
  - Dynamic product recommendations based on category affinity and order volume
"""
from __future__ import annotations

import logging
import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .db import _get_connection, _now, get_published_pack
from engine.schema.pack import DomainPack
from engine.runtime import compute_price

logger = logging.getLogger("monetize360.store")

DEFAULT_INITIAL_PRODUCTS = [
    {
        "id": "ec-001",
        "name": "boAt Bassheads 100 Earphones",
        "category": "electronics",
        "short_desc": "In-ear wired earphones with mic, 10mm drivers, tangle-free cable.",
        "image_url": "/products/earphones.png",
        "rating": 4.3,
        "review_count": 12400,
        "mrp": 699.0,
        "initial_stock": 50,
        "stock": 36,
        "base_demand_score": 0.0,
        "days_since_listed": 210,
    },
    {
        "id": "ec-002",
        "name": "Zebronics Zeb-K500 Mechanical Keyboard",
        "category": "electronics",
        "short_desc": "USB wired mechanical keyboard, rainbow LED backlight, 104 keys.",
        "image_url": "/products/keyboard.png",
        "rating": 4.1,
        "review_count": 3870,
        "mrp": 1299.0,
        "initial_stock": 40,
        "stock": 18,
        "base_demand_score": 0.0,
        "days_since_listed": 95,
    },
    {
        "id": "ec-003",
        "name": "Spigen Rugged Armor Phone Case",
        "category": "electronics",
        "short_desc": "Military-grade drop protection case with matte carbon texture.",
        "image_url": "/products/phonecase.png",
        "rating": 4.5,
        "review_count": 8920,
        "mrp": 999.0,
        "initial_stock": 25,
        "stock": 2,
        "base_demand_score": 0.0,
        "days_since_listed": 30,
    },
    {
        "id": "ec-004",
        "name": "Ambrane 20000mAh Power Bank",
        "category": "electronics",
        "short_desc": "Dual USB output, 18W fast charging, compact design, LED indicator.",
        "image_url": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=400&q=80",
        "rating": 4.0,
        "review_count": 6120,
        "mrp": 1799.0,
        "initial_stock": 50,
        "stock": 44,
        "base_demand_score": 0.0,
        "days_since_listed": 300,
    },
    {
        "id": "fa-001",
        "name": "Bewakoof Men's Round Neck T-Shirt",
        "category": "fashion",
        "short_desc": "Pure cotton, regular fit, graphic print, available in multiple colours.",
        "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&q=80",
        "rating": 4.2,
        "review_count": 22000,
        "mrp": 599.0,
        "initial_stock": 60,
        "stock": 36,
        "base_demand_score": 0.0,
        "days_since_listed": 45,
    },
    {
        "id": "fa-002",
        "name": "Wildcraft Daypack 25L Backpack",
        "category": "fashion",
        "short_desc": "Water-resistant nylon, padded straps, laptop compartment.",
        "image_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=400&q=80",
        "rating": 4.4,
        "review_count": 9800,
        "mrp": 1499.0,
        "initial_stock": 30,
        "stock": 6,
        "base_demand_score": 0.0,
        "days_since_listed": 120,
    },
    {
        "id": "fa-003",
        "name": "WROGN Snapback Cap",
        "category": "fashion",
        "short_desc": "Structured snapback, embroidered logo, one-size-fits-most.",
        "image_url": "https://images.unsplash.com/photo-1521369909029-2afed882baee?w=400&q=80",
        "rating": 3.9,
        "review_count": 4200,
        "mrp": 499.0,
        "initial_stock": 40,
        "stock": 34,
        "base_demand_score": 0.0,
        "days_since_listed": 195,
    },
    {
        "id": "fa-004",
        "name": "Cotstyle Men's Ankle Socks (Pack of 5)",
        "category": "fashion",
        "short_desc": "Breathable cotton blend, anti-slip heel, casual everyday wear.",
        "image_url": "/products/socks.png",
        "rating": 4.6,
        "review_count": 31000,
        "mrp": 349.0,
        "initial_stock": 50,
        "stock": 27,
        "base_demand_score": 0.0,
        "days_since_listed": 60,
    },
    {
        "id": "gr-001",
        "name": "Nescafé Classic Instant Coffee 200g",
        "category": "grocery",
        "short_desc": "Rich roasted flavour, 100% pure coffee, resealable jar.",
        "image_url": "/products/coffee.png",
        "rating": 4.5,
        "review_count": 48000,
        "mrp": 475.0,
        "initial_stock": 60,
        "stock": 39,
        "base_demand_score": 0.0,
        "days_since_listed": 10,
    },
    {
        "id": "gr-002",
        "name": "Quaker Rolled Oats 1kg",
        "category": "grocery",
        "short_desc": "Whole grain oats, high fibre, quick 3-minute cook time.",
        "image_url": "https://images.unsplash.com/photo-1517673400267-0251440c45dc?w=400&q=80",
        "rating": 4.3,
        "review_count": 18500,
        "mrp": 230.0,
        "initial_stock": 50,
        "stock": 39,
        "base_demand_score": 0.0,
        "days_since_listed": 20,
    },
    {
        "id": "ha-001",
        "name": "Philips LED Desk Lamp",
        "category": "home_appliances",
        "short_desc": "Eye-care technology, adjustable brightness, USB charging port.",
        "image_url": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=400&q=80",
        "rating": 4.2,
        "review_count": 5600,
        "mrp": 1199.0,
        "initial_stock": 30,
        "stock": 15,
        "base_demand_score": 0.0,
        "days_since_listed": 75,
    },
    {
        "id": "ha-002",
        "name": "Vaya Tyffyn Stainless Steel Lunchbox",
        "category": "home_appliances",
        "short_desc": "3-tier tiffin, vacuum-insulated, keeps food hot for 6 hours.",
        "image_url": "/products/lunchbox.png",
        "rating": 4.7,
        "review_count": 13200,
        "mrp": 1699.0,
        "initial_stock": 25,
        "stock": 1,
        "base_demand_score": 0.0,
        "days_since_listed": 55,
    },
    {
        "id": "be-001",
        "name": "Himalaya Purifying Neem Face Wash 150ml",
        "category": "beauty",
        "short_desc": "Ayurvedic formula, controls oil, prevents pimples, gentle daily use.",
        "image_url": "/products/facewash.png",
        "rating": 4.4,
        "review_count": 95000,
        "mrp": 175.0,
        "initial_stock": 80,
        "stock": 64,
        "base_demand_score": 0.0,
        "days_since_listed": 15,
    },
    {
        "id": "be-002",
        "name": "Vaseline Lip Therapy Tin 20g",
        "category": "beauty",
        "short_desc": "Petroleum-based lip balm, heals dry and chapped lips overnight.",
        "image_url": "/products/lipbalm.png",
        "rating": 4.6,
        "review_count": 42000,
        "mrp": 125.0,
        "initial_stock": 60,
        "stock": 54,
        "base_demand_score": 0.0,
        "days_since_listed": 200,
    },
]


class StoreError(Exception):
    """Base exception for store operations."""


class InsufficientStockError(StoreError):
    """Raised when an item has insufficient inventory."""


class PriceChangedError(StoreError):
    """Raised when live price changed from expected price without customer confirmation."""
    def __init__(self, message: str, details: Dict[str, Any]):
        super().__init__(message)
        self.details = details


def init_store_db() -> None:
    """Initialize store tables and seed initial inventory."""
    with _get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS store_products (
                id                 TEXT PRIMARY KEY,
                name               TEXT NOT NULL,
                category           TEXT NOT NULL,
                short_desc         TEXT,
                image_url          TEXT,
                rating             REAL DEFAULT 4.0,
                review_count       INTEGER DEFAULT 0,
                mrp                REAL NOT NULL,
                initial_stock      INTEGER NOT NULL,
                stock              INTEGER NOT NULL,
                base_demand_score  REAL NOT NULL,
                days_since_listed  INTEGER NOT NULL,
                created_at         TEXT NOT NULL,
                updated_at         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS store_orders (
                id                 TEXT PRIMARY KEY,
                idempotency_key    TEXT UNIQUE,
                status             TEXT NOT NULL DEFAULT 'confirmed',
                customer_tier      TEXT NOT NULL DEFAULT 'guest',
                is_flash_sale      INTEGER NOT NULL DEFAULT 0,
                subtotal_mrp       REAL NOT NULL,
                total_price        REAL NOT NULL,
                items_count        INTEGER NOT NULL,
                items_json         TEXT NOT NULL,
                created_at         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS store_order_items (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id           TEXT NOT NULL,
                product_id         TEXT NOT NULL,
                quantity           INTEGER NOT NULL,
                unit_price         REAL NOT NULL,
                mrp                REAL NOT NULL,
                created_at         TEXT NOT NULL,
                FOREIGN KEY(order_id) REFERENCES store_orders(id),
                FOREIGN KEY(product_id) REFERENCES store_products(id)
            );

            CREATE INDEX IF NOT EXISTS idx_store_products_category ON store_products(category);
            CREATE INDEX IF NOT EXISTS idx_store_orders_idempotency ON store_orders(idempotency_key);
            CREATE INDEX IF NOT EXISTS idx_store_order_items_product ON store_order_items(product_id, created_at);
        """)

        # Seed products if table is empty
        count = conn.execute("SELECT COUNT(*) as c FROM store_products").fetchone()["c"]
        if count == 0:
            now = _now()
            for p in DEFAULT_INITIAL_PRODUCTS:
                conn.execute(
                    """
                    INSERT INTO store_products (
                        id, name, category, short_desc, image_url, rating, review_count,
                        mrp, initial_stock, stock, base_demand_score, days_since_listed,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p["id"], p["name"], p["category"], p["short_desc"], p["image_url"],
                        p["rating"], p["review_count"], p["mrp"], p["initial_stock"], p["stock"],
                        p["base_demand_score"], p["days_since_listed"], now, now
                    ),
                )

        # Calibrate base_demand_score to 0.0 for existing seeded rows so purchases immediately drive demand metrics
        conn.execute("UPDATE store_products SET base_demand_score = 0.0 WHERE base_demand_score > 0.0")


def reset_store_catalogue() -> None:
    """Reset store products to DEFAULT_INITIAL_PRODUCTS and clear orders for clean test runs."""
    init_store_db()
    with _get_connection() as conn:
        conn.execute("DELETE FROM store_order_items")
        conn.execute("DELETE FROM store_orders")
        conn.execute("DELETE FROM store_products")
        now = _now()
        for p in DEFAULT_INITIAL_PRODUCTS:
            conn.execute(
                """
                INSERT INTO store_products (
                    id, name, category, short_desc, image_url, rating, review_count,
                    mrp, initial_stock, stock, base_demand_score, days_since_listed,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p["id"], p["name"], p["category"], p["short_desc"], p["image_url"],
                    p["rating"], p["review_count"], p["mrp"], p["initial_stock"], p["stock"],
                    p["base_demand_score"], p["days_since_listed"], now, now
                ),
            )


def calculate_dynamic_demand_score(base_demand: float, recent_sales: int) -> float:
    """
    Calculate dynamic demand score reacting to authoritative 24h purchase velocity.
    Each recent sale unit adds +20.0 points to the demand score, bounded in [0.0, 100.0].
    """
    return max(0.0, min(100.0, round(base_demand + (recent_sales * 20.0), 1)))


def _get_recent_order_quantity(conn: sqlite3.Connection, product_id: str, hours: int = 24) -> int:
    """Calculate quantity sold in the sliding time window."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) as qty
        FROM store_order_items
        WHERE product_id = ? AND created_at >= ?
        """,
        (product_id, cutoff),
    ).fetchone()
    return int(row["qty"]) if row else 0


def _build_product_dict(row: sqlite3.Row, recent_sales: int = 0) -> Dict[str, Any]:
    """Calculate dynamic signals from authoritative database state."""
    d = dict(row)
    initial_stock = max(1, d["initial_stock"])
    current_stock = max(0, d["stock"])

    # Authoritative inventory_pct based on current stock vs initial stock
    inv_pct = max(0.0, min(100.0, round((current_stock / initial_stock) * 100.0, 1)))

    # Demand score reacts to recent purchase velocity: +20 points per recent sale unit, capped at 100
    base_demand = float(d["base_demand_score"])
    dynamic_demand = calculate_dynamic_demand_score(base_demand, recent_sales)

    d["inventory_pct"] = inv_pct
    d["demand_score"] = dynamic_demand
    d["recent_sales"] = recent_sales
    d["in_stock"] = current_stock > 0

    d["signals"] = {
        "category": d["category"],
        "mrp": float(d["mrp"]),
        "inventory_pct": inv_pct,
        "demand_score": dynamic_demand,
        "days_since_listed": int(d["days_since_listed"]),
    }
    return d


def get_all_store_products() -> List[Dict[str, Any]]:
    """Return all products with authoritative inventory and dynamic demand signals."""
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM store_products ORDER BY category, id").fetchall()
        result = []
        for r in rows:
            recent_sales = _get_recent_order_quantity(conn, r["id"])
            result.append(_build_product_dict(r, recent_sales))
        return result


def get_store_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    """Fetch single product with authoritative signals."""
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM store_products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return None
        recent_sales = _get_recent_order_quantity(conn, product_id)
        return _build_product_dict(row, recent_sales)


def calculate_live_product_price(
    product_id: str,
    customer_tier: str = "guest",
    is_flash_sale: bool = False,
    quantity: int = 1,
) -> Dict[str, Any]:
    """
    Compute live dynamic price using the published RateWeaver ecommerce pack.
    """
    product = get_store_product_by_id(product_id)
    if not product:
        raise ValueError(f"Product '{product_id}' not found")

    pack_row = get_published_pack("ecommerce")
    if not pack_row:
        raise ValueError("Published ecommerce domain pack not found")

    pack = DomainPack.model_validate(pack_row["pack_data"])

    signals = {
        "category": product["signals"]["category"],
        "mrp": float(product["signals"]["mrp"]),
        "inventory_pct": float(product["signals"]["inventory_pct"]),
        "demand_score": float(product["signals"]["demand_score"]),
        "days_since_listed": int(product["signals"]["days_since_listed"]),
        "customer_tier": customer_tier,
        "is_flash_sale": bool(is_flash_sale),
        "quantity": int(quantity),
    }

    result = compute_price(pack, signals)
    fired_steps = [s.step for s in result.trace.steps if s.fired and s.step != "rounding" and s.before is not None]
    logger.info(
        "[StorePricing] Calculated live price for product=%s: price=%s (base=%s, demand_score=%s, inv_pct=%s, fired_steps=%s)",
        product_id,
        result.price,
        result.base,
        signals["demand_score"],
        signals["inventory_pct"],
        fired_steps,
    )
    return {
        "product_id": product_id,
        "price": float(result.price),
        "base": float(result.base),
        "fingerprint": result.fingerprint,
        "trace": result.trace.to_list(),
        "signals": signals,
    }


def execute_checkout_transaction(
    idempotency_key: str,
    items: List[Dict[str, Any]],
    customer_tier: str = "guest",
    is_flash_sale: bool = False,
    confirm_price_change: bool = False,
) -> Dict[str, Any]:
    """
    Execute atomic checkout transaction with:
      - Idempotency key duplicate protection
      - Stock validation and atomic decrement
      - Live price revalidation against expected prices
      - Order and order_items creation
      - Rollback of entire transaction if any check fails
    """
    if not items:
        raise ValueError("Cannot checkout with an empty cart.")

    # 1. Check idempotency key first
    with _get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM store_orders WHERE idempotency_key = ?",
            (idempotency_key,)
        ).fetchone()
        if existing:
            order_data = dict(existing)
            order_data["order_id"] = order_data["id"]
            order_data["items"] = json.loads(order_data["items_json"])
            order_data["idempotent_replay"] = True
            return order_data

    # Load published ecommerce domain pack
    pack_row = get_published_pack("ecommerce")
    if not pack_row:
        raise ValueError("Published ecommerce pack not found")
    pack = DomainPack.model_validate(pack_row["pack_data"])

    now = _now()
    order_id = f"ord_{uuid.uuid4().hex[:12]}"

    conn = _get_connection()
    try:
        # Begin explicit immediate transaction for atomicity and concurrency locking
        conn.execute("BEGIN IMMEDIATE")

        # 2. Validate all products and stock availability
        price_changes = []
        prepared_items = []
        total_price = 0.0
        subtotal_mrp = 0.0
        total_quantity = 0

        for item in items:
            pid = item["product_id"]
            qty = int(item["quantity"])
            if qty <= 0:
                raise ValueError(f"Invalid quantity {qty} for product {pid}")

            row = conn.execute("SELECT * FROM store_products WHERE id = ?", (pid,)).fetchone()
            if not row:
                raise ValueError(f"Product '{pid}' does not exist.")

            current_stock = int(row["stock"])
            p_name = row["name"]
            p_mrp = float(row["mrp"])

            if current_stock < qty:
                raise InsufficientStockError(
                    f"Insufficient stock for '{p_name}'. Available: {current_stock}, requested: {qty}."
                )

            # Compute authoritative price under current stock and demand
            recent_sales = _get_recent_order_quantity(conn, pid)
            initial_stock = max(1, int(row["initial_stock"]))
            inv_pct = max(0.0, min(100.0, round((current_stock / initial_stock) * 100.0, 1)))
            base_demand = float(row["base_demand_score"])
            dynamic_demand = calculate_dynamic_demand_score(base_demand, recent_sales)

            signals = {
                "category": row["category"],
                "mrp": p_mrp,
                "inventory_pct": inv_pct,
                "demand_score": dynamic_demand,
                "days_since_listed": int(row["days_since_listed"]),
                "customer_tier": customer_tier,
                "is_flash_sale": bool(is_flash_sale),
                "quantity": qty,
            }

            price_res = compute_price(pack, signals)
            authoritative_unit_price = float(price_res.price)

            logger.info(
                "[CheckoutQuote] Item priced: pid=%s, unit_price=%s, demand_score=%s (recent_sales=%d), inv_pct=%s",
                pid,
                authoritative_unit_price,
                dynamic_demand,
                recent_sales,
                inv_pct,
            )

            # Check expected unit price if passed by client
            expected_price = item.get("expected_unit_price")
            if expected_price is not None:
                expected_float = float(expected_price)
                if abs(authoritative_unit_price - expected_float) > 0.01:
                    price_changes.append({
                        "product_id": pid,
                        "name": p_name,
                        "old_price": expected_float,
                        "new_price": authoritative_unit_price,
                        "delta": round(authoritative_unit_price - expected_float, 2),
                    })

            line_subtotal = round(authoritative_unit_price * qty, 2)
            total_price += line_subtotal
            subtotal_mrp += round(p_mrp * qty, 2)
            total_quantity += qty

            prepared_items.append({
                "product_id": pid,
                "name": p_name,
                "category": row["category"],
                "image_url": row["image_url"],
                "quantity": qty,
                "unit_price": authoritative_unit_price,
                "mrp": p_mrp,
                "subtotal": line_subtotal,
                "fingerprint": price_res.fingerprint,
            })

        # 3. Check for unconfirmed price changes
        if price_changes and not confirm_price_change:
            raise PriceChangedError(
                "Prices have updated for one or more items in your cart based on live engine evaluation.",
                {
                    "price_changes": price_changes,
                    "updated_total": round(total_price, 2),
                    "subtotal_mrp": round(subtotal_mrp, 2),
                }
            )

        # 4. Atomically decrement stock
        for pitem in prepared_items:
            cur = conn.execute(
                """
                UPDATE store_products
                SET stock = stock - ?, updated_at = ?
                WHERE id = ? AND stock >= ?
                """,
                (pitem["quantity"], now, pitem["product_id"], pitem["quantity"]),
            )
            if cur.rowcount == 0:
                raise InsufficientStockError(
                    f"Concurrency conflict: stock for '{pitem['name']}' changed during checkout. Please retry."
                )
            logger.info(
                "[CheckoutInventory] Stock decremented: product_id=%s, qty=%d, order_id=%s",
                pitem["product_id"],
                pitem["quantity"],
                order_id,
            )

        # 5. Insert order record
        conn.execute(
            """
            INSERT INTO store_orders (
                id, idempotency_key, status, customer_tier, is_flash_sale,
                subtotal_mrp, total_price, items_count, items_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                idempotency_key,
                "confirmed",
                customer_tier,
                1 if is_flash_sale else 0,
                round(subtotal_mrp, 2),
                round(total_price, 2),
                total_quantity,
                json.dumps(prepared_items),
                now,
            ),
        )

        logger.info(
            "[CheckoutSuccess] Order confirmed: order_id=%s, idempotency_key=%s, total=%s, items=%d",
            order_id,
            idempotency_key,
            round(total_price, 2),
            total_quantity,
        )

        # 6. Insert order items
        for pitem in prepared_items:
            conn.execute(
                """
                INSERT INTO store_order_items (
                    order_id, product_id, quantity, unit_price, mrp, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    pitem["product_id"],
                    pitem["quantity"],
                    pitem["unit_price"],
                    pitem["mrp"],
                    now,
                ),
            )

        conn.commit()

        return {
            "id": order_id,
            "order_id": order_id,
            "idempotency_key": idempotency_key,
            "status": "confirmed",
            "customer_tier": customer_tier,
            "is_flash_sale": is_flash_sale,
            "subtotal_mrp": round(subtotal_mrp, 2),
            "total_price": round(total_price, 2),
            "items_count": total_quantity,
            "items": prepared_items,
            "created_at": now,
            "message": "Order placed successfully! (Demo purchase - no real payment charged)",
        }

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch order details by order_id."""
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM store_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = json.loads(d["items_json"])
        return d


def get_product_recommendations(
    product_id: Optional[str] = None,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    """
    Generate dynamic product recommendations:
      - Excludes out-of-stock products (stock > 0)
      - Excludes current product if product_id is specified
      - If product_id specified: prioritizes same category, ranked by recent popularity & rating
      - If no product_id: returns top trending products across catalogue ranked by sales & rating
      - Completely read-only: does not modify inventory or demand counts
    """
    with _get_connection() as conn:
        all_rows = conn.execute("SELECT * FROM store_products WHERE stock > 0").fetchall()
        if not all_rows:
            return []

        products_data = []
        target_category = None

        if product_id:
            curr = conn.execute("SELECT category FROM store_products WHERE id = ?", (product_id,)).fetchone()
            if curr:
                target_category = curr["category"]

        for r in all_rows:
            if product_id and r["id"] == product_id:
                continue

            recent_sales = _get_recent_order_quantity(conn, r["id"])
            p_dict = _build_product_dict(r, recent_sales)

            # Category affinity weight
            affinity_score = 10.0 if (target_category and r["category"] == target_category) else 0.0
            # Ranking score = affinity + (recent_sales * 2) + rating
            p_dict["recommendation_score"] = affinity_score + (recent_sales * 2.0) + float(r["rating"])
            products_data.append(p_dict)

        # Sort descending by recommendation_score
        products_data.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return products_data[:limit]
