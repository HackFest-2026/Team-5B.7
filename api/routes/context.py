"""Operational context ingestion routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..context import ContextError, get_context, save_context
from ..models import ContextUpdateRequest
from ..storage import get_published_pack
from engine.schema.pack import DomainPack

router = APIRouter(prefix="/v1/context", tags=["context"])


def _load_pack(domain_id: str) -> DomainPack:
    row = get_published_pack(domain_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No published pack found for domain '{domain_id}'.")
    try:
        return DomainPack.model_validate(row["pack_data"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pack deserialization failed: {exc}") from None


@router.put("/{domain_id}")
def update_context(domain_id: str, req: ContextUpdateRequest) -> Dict[str, Any]:
    """Store a validated, expiring context snapshot for subsequent pricing requests."""
    try:
        snapshot = save_context(
            domain_id=domain_id,
            pack=_load_pack(domain_id),
            signals=req.signals,
            observed_at=req.observed_at,
            max_age_seconds=req.max_age_seconds,
            source=req.source,
        )
    except ContextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"status": "updated", "context": snapshot}


@router.get("/{domain_id}")
def read_context(domain_id: str) -> Dict[str, Any]:
    """Read the current context snapshot without exposing stale data."""
    try:
        _load_pack(domain_id)
        snapshot = get_context(domain_id)
    except ContextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No context snapshot found for domain '{domain_id}'.")
    return snapshot


@router.delete("/{domain_id}")
def clear_context(domain_id: str) -> Dict[str, Any]:
    """Delete the operational context snapshot for a domain."""
    from ..context import delete_context
    _load_pack(domain_id)
    deleted = delete_context(domain_id)
    return {"status": "cleared" if deleted else "not_found", "domain_id": domain_id}