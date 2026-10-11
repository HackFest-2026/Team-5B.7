"""
api/routes/store.py — Storefront API endpoints for products, inventory, quotes, checkout, and recommendations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..models import StoreCheckoutRequest, StoreQuoteRequest
from ..storage import (
    get_all_store_products,
    get_store_product_by_id,
    calculate_live_product_price,
    execute_checkout_transaction,
    get_order_by_id,
    get_product_recommendations,
    InsufficientStockError,
    PriceChangedError,
)

router = APIRouter(prefix="/v1/store", tags=["store"])


@router.get("/products")
def list_products() -> List[Dict[str, Any]]:
    """
    Get all catalogue products with authoritative stock and dynamic demand signals.
    """
    try:
        return get_all_store_products()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch products: {exc}")


@router.get("/products/{product_id}")
def get_product(product_id: str) -> Dict[str, Any]:
    """
    Get a single product with live inventory and signals.
    """
    product = get_store_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    return product


@router.get("/products/{product_id}/price")
def get_product_live_price(
    product_id: str,
    customer_tier: str = Query("guest"),
    is_flash_sale: bool = Query(False),
    quantity: int = Query(1, ge=1, le=500),
) -> Dict[str, Any]:
    """
    Calculate the live price for a specific product using the real RateWeaver ecommerce engine.
    """
    try:
        return calculate_live_product_price(
            product_id=product_id,
            customer_tier=customer_tier,
            is_flash_sale=is_flash_sale,
            quantity=quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pricing calculation failed: {exc}")


@router.post("/quote")
def quote_cart(req: StoreQuoteRequest) -> Dict[str, Any]:
    """
    Compute authoritative live quote for a set of cart items.
    Validates stock availability and computes current dynamic prices.
    """
    if not req.items:
        return {"items": [], "subtotal_mrp": 0.0, "total_price": 0.0, "total_items": 0}

    quoted_items = []
    total_price = 0.0
    subtotal_mrp = 0.0
    total_quantity = 0

    for it in req.items:
        product = get_store_product_by_id(it.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{it.product_id}' not found")

        try:
            price_data = calculate_live_product_price(
                product_id=it.product_id,
                customer_tier=req.customer_tier,
                is_flash_sale=req.is_flash_sale,
                quantity=it.quantity,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to price item '{it.product_id}': {exc}")

        unit_price = price_data["price"]
        mrp = product["signals"]["mrp"]
        line_total = round(unit_price * it.quantity, 2)
        line_mrp = round(mrp * it.quantity, 2)

        total_price += line_total
        subtotal_mrp += line_mrp
        total_quantity += it.quantity

        quoted_items.append({
            "product_id": it.product_id,
            "name": product["name"],
            "category": product["category"],
            "image_url": product["image_url"],
            "quantity": it.quantity,
            "unit_price": unit_price,
            "mrp": mrp,
            "subtotal": line_total,
            "in_stock": product["stock"] >= it.quantity,
            "available_stock": product["stock"],
            "fingerprint": price_data["fingerprint"],
        })

    return {
        "items": quoted_items,
        "customer_tier": req.customer_tier,
        "is_flash_sale": req.is_flash_sale,
        "subtotal_mrp": round(subtotal_mrp, 2),
        "total_price": round(total_price, 2),
        "total_items": total_quantity,
        "savings": round(max(0.0, subtotal_mrp - total_price), 2),
    }


@router.post("/checkout")
def checkout(req: StoreCheckoutRequest) -> Dict[str, Any]:
    """
    Execute transactional purchase with:
      - Idempotency key duplicate protection
      - Stock validation and atomic decrement
      - Live price revalidation against expected prices
      - Order creation
    """
    raw_items = [it.model_dump() for it in req.items]
    try:
        order = execute_checkout_transaction(
            idempotency_key=req.idempotency_key,
            items=raw_items,
            customer_tier=req.customer_tier,
            is_flash_sale=req.is_flash_sale,
            confirm_price_change=req.confirm_price_change,
        )
        return order

    except InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "INSUFFICIENT_STOCK", "message": str(exc)},
        )

    except PriceChangedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "PRICE_CHANGED",
                "message": str(exc),
                "details": exc.details,
            },
        )

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Checkout error: {exc}")


@router.get("/orders/{order_id}")
def get_order(order_id: str) -> Dict[str, Any]:
    """
    Fetch confirmed order by ID.
    """
    order = get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    return order


@router.get("/recommendations")
def recommendations(
    product_id: Optional[str] = Query(None),
    limit: int = Query(4, ge=1, le=12),
) -> List[Dict[str, Any]]:
    """
    Get dynamic product recommendations based on category affinity and order volume.
    Excludes out-of-stock products and the currently viewed product.
    Read-only — does not mutate stock or demand counters.
    """
    try:
        return get_product_recommendations(product_id=product_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Recommendation retrieval failed: {exc}")
