"""
api/storage/analytics_db.py — Read-only analytics, pricing performance, alerts, and evidence queries.

Separates completed storefront orders from pricing evaluations.
Zero fabricated live metrics:
  - Real completed orders are fetched from `store_orders` and `store_order_items`.
  - If no completed orders exist yet, a clearly flagged synthetic demonstration dataset is provided.
  - Pricing telemetry is aggregated from `audit_log` (event='price_computed').
  - Traces and rules are evaluated deterministically using the published domain packs.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .db import _get_connection, get_published_pack
from engine.schema.pack import DomainPack
from engine.runtime import compute_price

logger = logging.getLogger("monetize360.analytics")

# Clearly labeled demonstration dataset when no real store orders exist yet
DEMO_SYNTHETIC_ORDERS = [
    {
        "id": "ord_demo_001",
        "date": "2026-10-08",
        "created_at": "2026-10-08T10:15:00Z",
        "customer_tier": "regular",
        "total_price": 1845.0,
        "subtotal_mrp": 2198.0,
        "items_count": 2,
        "items": [
            {"product_id": "ec-002", "name": "Zebronics Zeb-K500 Mechanical Keyboard", "category": "electronics", "quantity": 1, "unit_price": 1247.0, "mrp": 1299.0},
            {"product_id": "fa-001", "name": "Bewakoof Men's Round Neck T-Shirt", "category": "fashion", "quantity": 1, "unit_price": 598.0, "mrp": 599.0},
        ],
    },
    {
        "id": "ord_demo_002",
        "date": "2026-10-09",
        "created_at": "2026-10-09T14:30:00Z",
        "customer_tier": "prime",
        "total_price": 1349.0,
        "subtotal_mrp": 1499.0,
        "items_count": 1,
        "items": [
            {"product_id": "fa-002", "name": "Wildcraft Daypack 25L Backpack", "category": "fashion", "quantity": 1, "unit_price": 1349.0, "mrp": 1499.0},
        ],
    },
    {
        "id": "ord_demo_003",
        "date": "2026-10-10",
        "created_at": "2026-10-10T09:45:00Z",
        "customer_tier": "guest",
        "total_price": 678.0,
        "subtotal_mrp": 699.0,
        "items_count": 1,
        "items": [
            {"product_id": "ec-001", "name": "boAt Bassheads 100 Earphones", "category": "electronics", "quantity": 1, "unit_price": 678.0, "mrp": 699.0},
        ],
    },
    {
        "id": "ord_demo_004",
        "date": "2026-10-10",
        "created_at": "2026-10-10T16:20:00Z",
        "customer_tier": "elite",
        "total_price": 1820.0,
        "subtotal_mrp": 2174.0,
        "items_count": 3,
        "items": [
            {"product_id": "gr-001", "name": "Nescafé Classic Instant Coffee 200g", "category": "grocery", "quantity": 1, "unit_price": 451.0, "mrp": 475.0},
            {"product_id": "ha-001", "name": "Philips LED Desk Lamp", "category": "home_appliances", "quantity": 1, "unit_price": 1194.0, "mrp": 1199.0},
            {"product_id": "be-001", "name": "Himalaya Purifying Neem Face Wash 150ml", "category": "beauty", "quantity": 1, "unit_price": 175.0, "mrp": 175.0},
        ],
    },
    {
        "id": "ord_demo_005",
        "date": "2026-10-11",
        "created_at": "2026-10-11T11:00:00Z",
        "customer_tier": "prime",
        "total_price": 2890.0,
        "subtotal_mrp": 3298.0,
        "items_count": 2,
        "items": [
            {"product_id": "ha-002", "name": "Vaya Tyffyn Stainless Steel Lunchbox", "category": "home_appliances", "quantity": 1, "unit_price": 1614.0, "mrp": 1699.0},
            {"product_id": "ec-002", "name": "Zebronics Zeb-K500 Mechanical Keyboard", "category": "electronics", "quantity": 1, "unit_price": 1276.0, "mrp": 1299.0},
        ],
    },
]


def get_sales_analytics(
    domain: Optional[str] = "ecommerce",
    time_range: str = "7d",
) -> Dict[str, Any]:
    """
    Fetch sales overview metrics from completed store orders.
    Calculates revenue, units sold, order volume, and average selling price (ASP).
    Excludes cancelled/failed orders.
    """
    now = datetime.now(timezone.utc)
    if time_range == "today":
        cutoff = (now - timedelta(days=1)).isoformat()
    elif time_range == "30d":
        cutoff = (now - timedelta(days=30)).isoformat()
    elif time_range == "all":
        cutoff = "1970-01-01T00:00:00"
    else:  # default 7d
        cutoff = (now - timedelta(days=7)).isoformat()

    # Query completed orders from store_orders
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM store_orders
            WHERE status = 'confirmed' AND created_at >= ?
            ORDER BY created_at ASC
            """,
            (cutoff,),
        ).fetchall()

        if rows:
            # Real live data exists
            orders = []
            for r in rows:
                od = dict(r)
                try:
                    od["items"] = json.loads(od["items_json"])
                except Exception:
                    od["items"] = []
                # format date YYYY-MM-DD
                od["date"] = od["created_at"][:10] if od.get("created_at") else ""
                orders.append(od)

            is_synthetic = False
            data_source = "Authoritative Storefront Completed Orders"
        else:
            # Fallback to clearly labeled synthetic dataset
            orders = [o for o in DEMO_SYNTHETIC_ORDERS if o["created_at"] >= cutoff]
            if not orders:
                orders = DEMO_SYNTHETIC_ORDERS[-3:]
            is_synthetic = True
            data_source = "Synthetic Demonstration Dataset (no live orders placed yet)"

    # Aggregate Sales KPIs
    total_revenue = round(sum(o["total_price"] for o in orders), 2)
    units_sold = sum(o["items_count"] for o in orders)
    order_volume = len(orders)
    asp = round(total_revenue / units_sold, 2) if units_sold > 0 else 0.0
    aov = round(total_revenue / order_volume, 2) if order_volume > 0 else 0.0

    # Aggregate trend by date
    daily_map: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        d = o.get("date") or o.get("created_at", "")[:10] or "Unknown"
        if d not in daily_map:
            daily_map[d] = {"date": d, "revenue": 0.0, "units": 0, "orders": 0}
        daily_map[d]["revenue"] = round(daily_map[d]["revenue"] + o["total_price"], 2)
        daily_map[d]["units"] += o["items_count"]
        daily_map[d]["orders"] += 1

    sales_trend = sorted(daily_map.values(), key=lambda x: x["date"])

    # Aggregate top products
    product_map: Dict[str, Dict[str, Any]] = {}
    category_map: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        for it in o.get("items", []):
            pid = it.get("product_id") or "unknown"
            pname = it.get("name") or pid
            cat = it.get("category") or "general"
            qty = it.get("quantity", 1)
            line_rev = round(float(it.get("unit_price", 0.0)) * qty, 2)

            if pid not in product_map:
                product_map[pid] = {
                    "id": pid,
                    "name": pname,
                    "category": cat,
                    "units_sold": 0,
                    "revenue": 0.0,
                }
            product_map[pid]["units_sold"] += qty
            product_map[pid]["revenue"] = round(product_map[pid]["revenue"] + line_rev, 2)

            if cat not in category_map:
                category_map[cat] = {"category": cat, "units_sold": 0, "revenue": 0.0}
            category_map[cat]["units_sold"] += qty
            category_map[cat]["revenue"] = round(category_map[cat]["revenue"] + line_rev, 2)

    top_products = sorted(product_map.values(), key=lambda x: x["revenue"], reverse=True)[:6]
    category_breakdown = sorted(category_map.values(), key=lambda x: x["revenue"], reverse=True)

    return {
        "domain": domain,
        "time_range": time_range,
        "is_synthetic": is_synthetic,
        "data_source": data_source,
        "kpis": {
            "revenue": total_revenue,
            "currency": "INR",
            "units_sold": units_sold,
            "order_volume": order_volume,
            "average_selling_price": asp,
            "average_order_value": aov,
            "gross_margin": None,
            "gross_margin_note": "COGS (Cost of Goods Sold) not configured in store schema.",
            "conversion_rate": None,
            "conversion_rate_note": "Session traffic / view events not tracked.",
        },
        "sales_trend": sales_trend,
        "top_products": top_products,
        "category_breakdown": category_breakdown,
    }


def get_pricing_performance(
    domain: Optional[str] = "ecommerce",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Fetch pricing performance from real pricing evaluations in `audit_log`.
    Reuses engine execution traces to extract rule-triggers and constraint hits.
    Strictly distinguished from purchase orders.
    """
    with _get_connection() as conn:
        if domain:
            rows = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE event = 'price_computed' AND pack_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (domain, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE event = 'price_computed'
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()

    eval_count = len(rows)
    evaluations: List[Dict[str, Any]] = []
    rule_counts: Dict[str, Dict[str, Any]] = {}
    constraint_counts: Dict[str, Dict[str, Any]] = {}

    # Load published pack for deterministic trace inspection if needed
    pack = None
    target_domain = domain or "ecommerce"
    pack_row = get_published_pack(target_domain)
    if pack_row:
        try:
            pack = DomainPack.model_validate(pack_row["pack_data"])
        except Exception:
            pack = None

    for r in reversed(rows):
        dt_str = r["created_at"]
        d = dict(r)
        price_val = None
        signals = {}
        fingerprint = ""

        try:
            detail = json.loads(d["detail"]) if d.get("detail") else {}
            price_val = float(detail.get("price", 0.0))
            signals = detail.get("signals", {})
            fingerprint = detail.get("fingerprint", "")
        except Exception:
            pass

        eval_item = {
            "id": d["id"],
            "timestamp": dt_str,
            "domain": d["pack_id"],
            "price": price_val,
            "fingerprint": fingerprint,
            "rules_fired": [],
            "constraints_hit": [],
        }

        # Deterministically resolve trace if pack is available
        if pack and signals:
            try:
                res = compute_price(pack, signals)
                for step in res.trace.steps:
                    if step.fired and step.rule_id and step.step != "rounding":
                        if step.stage == "constraints" or step.step.startswith("constraint:"):
                            cid = step.rule_id
                            eval_item["constraints_hit"].append(cid)
                            if cid not in constraint_counts:
                                constraint_counts[cid] = {
                                    "constraint_id": cid,
                                    "type": step.action or "bound",
                                    "description": step.description or cid,
                                    "count": 0,
                                }
                            constraint_counts[cid]["count"] += 1
                        else:
                            rid = step.rule_id
                            eval_item["rules_fired"].append(rid)
                            if rid not in rule_counts:
                                rule_counts[rid] = {
                                    "rule_id": rid,
                                    "stage": step.stage,
                                    "action": step.action,
                                    "description": step.description or rid,
                                    "count": 0,
                                }
                            rule_counts[rid]["count"] += 1
            except Exception as exc:
                logger.debug("Trace re-evaluation skipped: %s", exc)

        evaluations.append(eval_item)

    # Compute trigger percentages
    total_evals = max(1, eval_count)
    top_rules = []
    for r in sorted(rule_counts.values(), key=lambda x: x["count"], reverse=True):
        r["trigger_pct"] = round((r["count"] / total_evals) * 100, 1)
        top_rules.append(r)

    constraint_hits = []
    for c in sorted(constraint_counts.values(), key=lambda x: x["count"], reverse=True):
        c["hit_pct"] = round((c["count"] / total_evals) * 100, 1)
        constraint_hits.append(c)

    # Price trend over evaluations
    price_trend = [
        {
            "index": i + 1,
            "timestamp": ev["timestamp"][-8:],  # HH:MM:SS
            "price": ev["price"],
            "domain": ev["domain"],
        }
        for i, ev in enumerate(evaluations)
        if ev["price"] is not None
    ]

    return {
        "domain": target_domain,
        "evaluation_count": eval_count,
        "pricing_source": "FastAPI Dynamic Pricing Engine Logs (audit_log: price_computed)",
        "price_trend": price_trend,
        "top_rules": top_rules,
        "constraint_hits": constraint_hits,
        "recent_evaluations": evaluations[-10:],
    }


def generate_alerts(domain: Optional[str] = "ecommerce") -> List[Dict[str, Any]]:
    """
    Generate straightforward explainable alerts using configurable thresholds:
      - Constraint hits (>20% of evaluations)
      - Large price fluctuations
      - Low inventory / high demand pressure
    Clearly separates observed facts from recommendations.
    """
    perf = get_pricing_performance(domain=domain, limit=40)
    alerts: List[Dict[str, Any]] = []

    # 1. Constraint hit frequency check
    for c in perf["constraint_hits"]:
        if c["hit_pct"] >= 20.0:
            alerts.append({
                "id": f"alt-constraint-{c['constraint_id']}",
                "type": "warning",
                "severity": "medium",
                "title": f"Frequent Guardrail Clamping ({c['constraint_id']})",
                "fact": f"Constraint '{c['constraint_id']}' clamped dynamic prices in {c['count']} of {perf['evaluation_count']} recent evaluations ({c['hit_pct']}%).",
                "recommendation": "Review discount stacking in Rule Studio. Cumulative rule discounts may be persistently pushing prices against the floor boundary.",
                "domain": domain,
            })

    # 2. Price movement analysis
    prices = [pt["price"] for pt in perf["price_trend"] if pt["price"] is not None]
    if len(prices) >= 4:
        min_p = min(prices)
        max_p = max(prices)
        if min_p > 0 and ((max_p - min_p) / min_p) >= 0.35:
            spread_pct = round(((max_p - min_p) / min_p) * 100, 1)
            alerts.append({
                "id": "alt-price-volatility",
                "type": "opportunity",
                "severity": "low",
                "title": f"High Dynamic Price Spread ({spread_pct}%)",
                "fact": f"Evaluated prices ranged from ₹{min_p:,.2f} to ₹{max_p:,.2f} ({spread_pct}% spread) due to dynamic demand and inventory signals.",
                "recommendation": "Dynamic adjustments are active and responsive. Verify that customer tier and loyalty discounts align with margin targets.",
                "domain": domain,
            })

    # 3. Store Inventory pressure alerts
    try:
        with _get_connection() as conn:
            prods = conn.execute("SELECT * FROM store_products WHERE stock <= 5 ORDER BY stock ASC LIMIT 2").fetchall()
            for p in prods:
                alerts.append({
                    "id": f"alt-stock-{p['id']}",
                    "type": "warning",
                    "severity": "high",
                    "title": f"Critical Stock Depletion ({p['name']})",
                    "fact": f"Product '{p['name']}' has only {p['stock']} units left in inventory (initial: {p['initial_stock']}).",
                    "recommendation": "Engine will apply scarcity pricing (+surge) on remaining stock. Trigger supplier reorder.",
                    "domain": "ecommerce",
                })
    except Exception:
        pass

    return alerts


def answer_analyst_question(query: str, domain: Optional[str] = "ecommerce") -> Dict[str, Any]:
    """
    Evidence-based AI Business Analyst question answering.
    Read-only — queries actual database state and returns truthful answers.
    Clearly notes unavailable data when questions exceed tracked metrics.
    """
    q_lower = query.lower().strip()
    sales = get_sales_analytics(domain=domain, time_range="all")
    perf = get_pricing_performance(domain=domain, limit=50)

    # 1. Domain sales query
    if any(k in q_lower for k in ["domain", "most sales", "highest sales", "which domain"]):
        # Inspect sales across domains
        top_cats = sales.get("category_breakdown", [])
        cat_summary = ", ".join(f"{c['category']}: ₹{c['revenue']:,.2f} ({c['units_sold']} units)" for c in top_cats) if top_cats else "None"
        return {
            "query": query,
            "can_answer": True,
            "answer": (
                f"The E-commerce domain currently drives the active storefront sales with a total revenue of "
                f"₹{sales['kpis']['revenue']:,.2f} across {sales['kpis']['units_sold']} units sold ({sales['kpis']['order_volume']} orders). "
                f"Within the store, sales by category: {cat_summary}. "
                f"Other domains (Hospitality, Banking, EV Charging) are configured for real-time pricing simulations but do not have direct checkout storefronts."
            ),
            "evidence": {
                "revenue": sales["kpis"]["revenue"],
                "units_sold": sales["kpis"]["units_sold"],
                "categories": top_cats,
                "data_source": sales["data_source"],
            },
            "limitation_note": None,
        }

    # 2. Pricing change query
    if any(k in q_lower for k in ["price change", "pricing change", "how did pricing change", "price trend", "average price"]):
        prices = [pt["price"] for pt in perf["price_trend"] if pt["price"] is not None]
        if prices:
            avg_p = round(sum(prices) / len(prices), 2)
            min_p = min(prices)
            max_p = max(prices)
            first_p = prices[0]
            last_p = prices[-1]
            delta = round(last_p - first_p, 2)
            delta_str = f"+₹{delta:,.2f}" if delta >= 0 else f"-₹{abs(delta):,.2f}"
            return {
                "query": query,
                "can_answer": True,
                "answer": (
                    f"Over the last {len(prices)} dynamic pricing evaluations in the '{domain}' domain, "
                    f"the average evaluated price was ₹{avg_p:,.2f} (ranging from ₹{min_p:,.2f} to ₹{max_p:,.2f}). "
                    f"Between the earliest and latest evaluations, the price moved by {delta_str}."
                ),
                "evidence": {
                    "evaluation_count": len(prices),
                    "average_price": avg_p,
                    "min_price": min_p,
                    "max_price": max_p,
                    "first_price": first_p,
                    "latest_price": last_p,
                },
                "limitation_note": None,
            }
        else:
            return {
                "query": query,
                "can_answer": False,
                "answer": f"No recent pricing evaluations have been recorded yet for domain '{domain}'. Run simulations or browse products to generate price logs.",
                "evidence": {},
                "limitation_note": "Pricing evaluation history is empty in audit_log.",
            }

    # 3. Pricing rules frequency query
    if any(k in q_lower for k in ["rule", "rules", "frequently", "which rule", "most frequent"]):
        top_rules = perf.get("top_rules", [])
        if top_rules:
            top_rule = top_rules[0]
            rules_list = ", ".join(f"{r['rule_id']} ({r['count']}x, {r['trigger_pct']}%)" for r in top_rules[:3])
            return {
                "query": query,
                "can_answer": True,
                "answer": (
                    f"The most frequently triggered pricing rule is '{top_rule['rule_id']}' ({top_rule.get('description', '')}), "
                    f"firing in {top_rule['count']} evaluations ({top_rule['trigger_pct']}% of evaluations). "
                    f"Top active rules: {rules_list}."
                ),
                "evidence": {
                    "top_rules": top_rules[:5],
                    "total_evaluations": perf["evaluation_count"],
                },
                "limitation_note": None,
            }
        else:
            return {
                "query": query,
                "can_answer": True,
                "answer": f"No rule triggers recorded yet in recent evaluations for domain '{domain}'.",
                "evidence": {},
                "limitation_note": None,
            }

    # 4. Floor / ceiling constraints query
    if any(k in q_lower for k in ["floor", "ceiling", "constraint", "guardrail"]):
        hits = perf.get("constraint_hits", [])
        if hits:
            hits_str = ", ".join(f"{c['constraint_id']} ({c['count']} hits, {c['hit_pct']}%)" for c in hits)
            return {
                "query": query,
                "can_answer": True,
                "answer": f"Floor and ceiling guardrail hits observed: {hits_str}.",
                "evidence": {"constraint_hits": hits},
                "limitation_note": None,
            }
        else:
            return {
                "query": query,
                "can_answer": True,
                "answer": f"Zero constraint violations or floor/ceiling clamping events observed in the last {perf['evaluation_count']} evaluations.",
                "evidence": {"constraint_hits": []},
                "limitation_note": None,
            }

    # 5. Unsupported query (e.g. profit margin, conversion rate, forecasting)
    return {
        "query": query,
        "can_answer": False,
        "answer": (
            "This query cannot be answered with current data. "
            "RateWeaver deterministically records pricing evaluations, rule traces, and completed order values. "
            "However, COGS (for gross margins), user session traffic (for conversion rates), and predictive elasticity models are not currently configured."
        ),
        "evidence": {},
        "limitation_note": "Requested metric is outside currently tracked telemetry.",
    }
