"""
Pricing routes — /price and /simulate.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..context import ContextError, merge_context
from ..models import (
    PriceRequest,
    BatchPriceRequest,
    SimulateRequest,
    SweepRequest,
    BeforeAfterRequest,
    CounterfactualRequest,
)
from ..storage import get_published_pack, log_price_event
from engine.schema.pack import DomainPack
from engine.runtime import compute_price, PricingError
from engine.simulate import (
    simulate_single,
    simulate_sweep,
    simulate_before_after,
    simulate_counterfactuals,
)

router = APIRouter(prefix="/v1", tags=["pricing"])

# In-memory LRU/dict cache for parsed domain packs to avoid continuous disk & Pydantic deserialization
_PACK_CACHE: Dict[str, Tuple[str, DomainPack]] = {}


def clear_pack_cache(domain: Optional[str] = None) -> None:
    if domain:
        _PACK_CACHE.pop(domain, None)
    else:
        _PACK_CACHE.clear()


def _load_published_pack(domain: str) -> DomainPack:
    pack_row = get_published_pack(domain)
    if pack_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No published pack found for domain '{domain}'. Publish a pack first.",
        )

    fp = pack_row.get("fingerprint") or pack_row.get("version") or ""
    if domain in _PACK_CACHE and _PACK_CACHE[domain][0] == fp:
        return _PACK_CACHE[domain][1]

    try:
        pack = DomainPack.model_validate(pack_row["pack_data"])
        _PACK_CACHE[domain] = (fp, pack)
        return pack
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pack deserialization failed: {exc}")


def _signals_with_context(domain: str, signals: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return merge_context(domain, signals)
    except ContextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/price")
def price(req: PriceRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Compute a deterministic price for the given domain and signals.
    """
    pack = _load_published_pack(req.domain)
    signals = _signals_with_context(req.domain, req.signals)
    try:
        result = compute_price(pack, signals)
    except PricingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pricing engine error: {exc}")

    # Fire-and-forget audit in background task so response returns immediately
    background_tasks.add_task(
        log_price_event,
        pack_id=pack.pack_id,
        version=pack.version,
        fingerprint=result.fingerprint,
        signals=signals,
        price=float(result.price),
    )

    return result.to_dict()


@router.post("/price/batch")
def price_batch(req: BatchPriceRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Batch compute deterministic prices for multiple items in a single round-trip.
    Instantaneous in-memory execution (<10ms for 50 items).
    """
    pack = _load_published_pack(req.domain)
    items_results = []
    errors = {}

    for it in req.items:
        try:
            signals = _signals_with_context(req.domain, it.signals)
            res = compute_price(pack, signals)
            res_dict = res.to_dict()
            res_dict["id"] = it.id
            items_results.append(res_dict)

            background_tasks.add_task(
                log_price_event,
                pack_id=pack.pack_id,
                version=pack.version,
                fingerprint=res.fingerprint,
                signals=signals,
                price=float(res.price),
            )
        except PricingError as exc:
            errors[it.id] = str(exc)
        except Exception as exc:
            errors[it.id] = f"Pricing error: {exc}"

    return {
        "domain": req.domain,
        "items": items_results,
        "errors": errors,
        "count": len(items_results),
    }


@router.post("/simulate")
def simulate(req: SimulateRequest) -> Dict[str, Any]:
    """Single simulation — same as /price but uses published pack."""
    pack = _load_published_pack(req.domain)
    signals = _signals_with_context(req.domain, req.signals)
    try:
        return simulate_single(pack, signals)
    except PricingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/simulate/sweep")
def sweep(req: SweepRequest) -> List[Dict[str, Any]]:
    """Sweep one signal across a range and return prices."""
    pack = _load_published_pack(req.domain)
    base_signals = _signals_with_context(req.domain, req.base_signals)
    return simulate_sweep(pack, base_signals, req.sweep_signal, req.sweep_values)


@router.post("/simulate/compare")
def compare(req: BeforeAfterRequest) -> Dict[str, Any]:
    """Before/after comparison."""
    pack = _load_published_pack(req.domain)
    signals_before = _signals_with_context(req.domain, req.signals_before)
    signals_after = _signals_with_context(req.domain, req.signals_after)
    try:
        return simulate_before_after(pack, signals_before, signals_after)
    except PricingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/simulate/counterfactual")
def counterfactual(req: CounterfactualRequest) -> List[Dict[str, Any]]:
    """Counterfactual analysis — what would the price have been?"""
    pack = _load_published_pack(req.domain)
    base_signals = _signals_with_context(req.domain, req.base_signals)
    try:
        return simulate_counterfactuals(pack, base_signals, req.counterfactuals)
    except PricingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
