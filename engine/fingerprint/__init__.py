"""
Deterministic fingerprint generator.

SHA-256 of a canonicalized JSON of:
  - pack_id
  - pack_version
  - input signals (sorted keys)
  - final price
  - trace step ids and after values

Deliberately excludes: timestamps, request IDs, latency.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Dict, List


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Non-serializable: {type(obj)}")


def generate_fingerprint(
    pack_id: str,
    pack_version: str,
    input_signals: Dict[str, Any],
    price: Decimal,
    trace_steps: List[dict],
) -> str:
    """
    Produce a deterministic SHA-256 fingerprint for a pricing result.

    The same inputs will always produce the same fingerprint, regardless
    of the machine, time, or process that ran the calculation.
    """
    canonical = {
        "pack_id": pack_id,
        "pack_version": pack_version,
        # Sort signals by key for stable ordering
        "signals": {k: v for k, v in sorted(input_signals.items())},
        "price": str(price),
        # Include only rule_id + after for each step
        "trace": [
            {"step": s["step"], "rule_id": s["rule_id"], "after": str(s["after"])}
            for s in trace_steps
            if s["fired"]
        ],
    }

    canonical_json = json.dumps(canonical, sort_keys=True, default=_default)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _clean_dict(val: Any) -> Any:
    if isinstance(val, dict):
        return {k: _clean_dict(v) for k, v in val.items() if v is not None}
    if isinstance(val, list):
        return [_clean_dict(x) for x in val]
    return val


def canonical_pack_json(pack_data: Any) -> str:
    """
    Produce a deterministic, canonical JSON representation of a domain pack.
    Works for both Pydantic DomainPack instances and plain dicts.
    """
    if hasattr(pack_data, "model_dump"):
        data = pack_data.model_dump(mode="json", exclude_none=True)
    elif isinstance(pack_data, dict):
        try:
            from ..schema.pack import DomainPack
            data = DomainPack.model_validate(pack_data).model_dump(mode="json", exclude_none=True)
        except Exception:
            data = _clean_dict(pack_data)
    else:
        raise TypeError(f"Expected dict or DomainPack, got {type(pack_data)}")

    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default)



def compute_pack_fingerprint(pack_data: Any) -> str:
    """
    Calculate deterministic SHA-256 fingerprint for canonical pack content.
    """
    canonical = canonical_pack_json(pack_data)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_pack_fingerprint(pack_data: Any, expected_fingerprint: str) -> bool:
    """
    Verify whether the pack content matches an expected SHA-256 fingerprint.
    """
    if not expected_fingerprint or not isinstance(expected_fingerprint, str):
        return False
    actual = compute_pack_fingerprint(pack_data)
    return actual.lower() == expected_fingerprint.lower()
