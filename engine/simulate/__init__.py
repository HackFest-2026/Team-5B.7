"""
Simulator — single price, variable sweep, and before/after comparison.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..schema.pack import DomainPack
from ..runtime import compute_price


def simulate_single(pack: DomainPack, signals: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single price calculation and return the result dict."""
    result = compute_price(pack, signals)
    return result.to_dict()


def simulate_sweep(
    pack: DomainPack,
    base_signals: Dict[str, Any],
    sweep_signal: str,
    sweep_values: List[Any],
) -> List[Dict[str, Any]]:
    """
    Sweep one signal across a list of values, returning a price for each.
    """
    results = []
    for val in sweep_values:
        signals = {**base_signals, sweep_signal: val}
        try:
            result = compute_price(pack, signals)
            results.append(
                {
                    "signal_value": val,
                    "price": float(result.price),
                    "fingerprint": result.fingerprint,
                }
            )
        except Exception as exc:
            results.append({"signal_value": val, "error": str(exc)})
    return results


def simulate_before_after(
    pack: DomainPack,
    signals_before: Dict[str, Any],
    signals_after: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare prices before and after a signal change."""
    before = compute_price(pack, signals_before)
    after = compute_price(pack, signals_after)
    delta = float(after.price) - float(before.price)
    delta_pct = (delta / float(before.price) * 100) if before.price else 0.0
    return {
        "before": before.to_dict(),
        "after": after.to_dict(),
        "delta": delta,
        "delta_pct": round(delta_pct, 2),
    }


def simulate_counterfactuals(
    pack: DomainPack,
    base_signals: Dict[str, Any],
    counterfactuals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    For each counterfactual override, compute what the price would have been.
    """
    base_result = compute_price(pack, base_signals)
    results = [
        {
            "label": "actual",
            "signals": base_signals,
            "price": float(base_result.price),
        }
    ]
    for cf in counterfactuals:
        label = cf.get("label", "counterfactual")
        overrides = cf.get("signals", {})
        cf_signals = {**base_signals, **overrides}
        try:
            cf_result = compute_price(pack, cf_signals)
            results.append(
                {
                    "label": label,
                    "signals": cf_signals,
                    "price": float(cf_result.price),
                    "delta": float(cf_result.price) - float(base_result.price),
                }
            )
        except Exception as exc:
            results.append({"label": label, "error": str(exc)})
    return results
