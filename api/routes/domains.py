"""
Domain routes — list, get, validate, publish, rollback, lifecycle, and audit verification.

Authorization notes
-------------------
* All mutating endpoints (POST) are protected by the API key guard registered
  in api/main.py when the API_KEY environment variable is set.
* The ``actor`` field in request bodies records *who* performed an action for
  audit purposes.  It is distinct from the API key (authentication token) and
  is not a security boundary by itself — it is a governance label.
* Error responses deliberately avoid exposing internal exception details,
  filesystem paths, or stack traces to callers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from ..config import REQUIRE_APPROVAL, ENFORCE_ROLE_SEPARATION
from ..models import (
    ValidateRequest,
    PublishRequest,
    PackDraftRequest,
    RollbackRequest,
    LifecycleTransitionRequest,
    BumpVersionRequest,
)
from ..storage import (
    get_pack,
    get_published_pack,
    list_packs,
    list_all_pack_versions,
    get_audit_log,
    verify_audit_chain,
    publish_pack,
    rollback_pack,
    upsert_pack,
    create_new_version,
    transition_pack_lifecycle,
    log_audit_event,
    ImmutableVersionError,
    StaleVersionConflictError,
    TamperError,
)
from engine.schema.pack import DomainPack
from engine.validate import validate_pack

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["domains"])


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get("/domains")
def list_domains() -> List[Dict[str, Any]]:
    """List all known domains and their current status."""
    return list_packs()


@router.get("/domains/{domain_id}")
def get_domain(domain_id: str) -> Dict[str, Any]:
    """Get the current pack for a domain (published preferred)."""
    pack_row = get_published_pack(domain_id) or get_pack(domain_id)
    if pack_row is None:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found.")
    return pack_row


@router.get("/domains/{domain_id}/versions")
def get_domain_versions(domain_id: str) -> List[Dict[str, Any]]:
    """Return the full version history for a domain."""
    return list_all_pack_versions(domain_id)


# ---------------------------------------------------------------------------
# Write endpoints (protected by API key guard in api/main.py when API_KEY is set)
# ---------------------------------------------------------------------------

@router.post("/domains/{domain_id}/bump")
def bump_domain_version(domain_id: str, req: BumpVersionRequest) -> Dict[str, Any]:
    """Create a new draft version bumped from the current active version."""
    try:
        new_draft = create_new_version(
            pack_id=domain_id,
            bump_type=req.bump_type,
            custom_version=req.custom_version,
            actor=req.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "created", "pack": new_draft}


@router.post("/validate")
def validate_domain_pack(req: ValidateRequest) -> Dict[str, Any]:
    """
    Validate a pack JSON without saving it.

    Returns a structured result with errors and warnings.
    Schema errors (malformed JSON structure) are reported as SCHEMA-level errors.
    Validation errors (rule/signal conflicts etc.) use the C1–C7 codes.
    Validation outcomes are recorded in the cryptographic audit chain when pack_id is present.
    """
    pack_id = req.pack.get("pack_id") if isinstance(req.pack, dict) else None
    version = req.pack.get("version") if isinstance(req.pack, dict) else None

    try:
        pack = DomainPack.model_validate(req.pack)
    except Exception as exc:
        err_msg = str(exc)
        if pack_id:
            try:
                log_audit_event(
                    pack_id=pack_id,
                    version=version,
                    event="validation_failed",
                    actor=req.actor,
                    detail=f"Schema validation failed: {err_msg[:200]}",
                )
            except Exception as audit_exc:
                logger.warning("Failed to record validation audit event: %s", audit_exc)
        return {
            "valid": False,
            "errors": [{"code": "SCHEMA", "message": err_msg, "rule_ids": [], "severity": "error"}],
            "warnings": [],
        }

    result = validate_pack(pack)
    if pack_id:
        try:
            event = "validation_passed" if result.valid else "validation_failed"
            detail = (
                f"Validation passed ({len(result.warnings)} warnings)"
                if result.valid
                else f"Validation failed ({len(result.errors)} errors, {len(result.warnings)} warnings)"
            )
            log_audit_event(
                pack_id=pack_id,
                version=version,
                event=event,
                actor=req.actor,
                detail=detail,
            )
        except Exception as audit_exc:
            logger.warning("Failed to record validation audit event: %s", audit_exc)

    return result.to_dict()


@router.post("/draft")
def save_draft(req: PackDraftRequest) -> Dict[str, Any]:
    """
    Save a pack as a draft.

    Fails with 409 Conflict if attempting to mutate an already published or
    archived version, or if optimistic concurrency check detects a stale update.
    Create a new version via /domains/{id}/bump to add changes on top of a published baseline.
    """
    pack_data = req.pack
    pack_id = pack_data.get("pack_id")
    version = pack_data.get("version", "1.0.0")
    if not pack_id:
        raise HTTPException(status_code=400, detail="pack_id is required.")

    try:
        saved = upsert_pack(
            pack_id,
            version,
            pack_data,
            status="draft",
            actor=req.actor,
            expected_fingerprint=req.base_fingerprint,
        )
    except (ImmutableVersionError, StaleVersionConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error saving draft pack_id=%s version=%s", pack_id, version)
        raise HTTPException(status_code=500, detail="Failed to save draft. See server logs.")

    return {"status": "draft", "pack": saved}


@router.post("/publish")
def publish_domain(req: PublishRequest) -> Dict[str, Any]:
    """
    Publish a pack version.

    Safety gates (applied in order):
      1. Pack must exist.
      2. If require_approval=True (or env default), status must be 'approved'.
      3. Fingerprint integrity check (tamper detection).
      4. Schema and rule validation (C1–C7 + C-LIMIT checks).
      5. Embedded golden test verification (if test_cases defined in pack).
      6. Four-eyes / role separation check (when enforce_role_separation=True or env default).

    A published version becomes immutable — its content cannot be changed.
    The previously published version is automatically archived.
    """
    role_sep = (
        req.enforce_role_separation
        if req.enforce_role_separation is not None
        else ENFORCE_ROLE_SEPARATION
    )
    req_appr = (
        req.require_approval
        if req.require_approval is not None
        else REQUIRE_APPROVAL
    )
    try:
        updated = publish_pack(
            pack_id=req.pack_id,
            version=req.version,
            actor=req.actor,
            approver=req.approver,
            enforce_role_separation=role_sep,
            run_golden_tests=req.run_golden_tests,
            require_approval=req_appr,
        )
    except ImmutableVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except TamperError as exc:
        raise HTTPException(status_code=422, detail=f"Tampering detected: {exc}")
    except ValueError as exc:
        msg = str(exc)
        if "Role separation" in msg or "four-eyes" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)
    except Exception:
        logger.exception(
            "Unexpected publishing error pack_id=%s version=%s actor=%s",
            req.pack_id, req.version, req.actor,
        )
        raise HTTPException(status_code=500, detail="Unexpected publishing error. See server logs.")

    return {"status": "published", "pack": updated}


@router.post("/rollback")
def rollback_domain(req: RollbackRequest) -> Dict[str, Any]:
    """
    Restore a previously published version of a domain pack.

    History is preserved — the current published version is archived, not
    deleted.  The target version is re-validated before activation to ensure
    it is still sound.  A rollback event is recorded in the cryptographic
    audit chain.
    """
    try:
        restored = rollback_pack(
            pack_id=req.pack_id,
            target_version=req.target_version,
            actor=req.actor,
        )
    except TamperError as exc:
        raise HTTPException(status_code=422, detail=f"Rollback blocked by tampering detection: {exc}")
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception:
        logger.exception(
            "Unexpected rollback error pack_id=%s target=%s actor=%s",
            req.pack_id, req.target_version, req.actor,
        )
        raise HTTPException(status_code=500, detail="Rollback error. See server logs.")

    return {"status": "rolled_back", "pack": restored}


# ---------------------------------------------------------------------------
# Lifecycle transition endpoints
# ---------------------------------------------------------------------------

@router.post("/lifecycle/transition")
def transition_lifecycle(req: LifecycleTransitionRequest) -> Dict[str, Any]:
    """Transition pack through lifecycle: draft → in_review → approved → published → archived."""
    if not req.target_status:
        raise HTTPException(status_code=400, detail="target_status is required.")
    role_sep = (
        req.enforce_role_separation
        if req.enforce_role_separation is not None
        else ENFORCE_ROLE_SEPARATION
    )
    try:
        updated = transition_pack_lifecycle(
            pack_id=req.pack_id,
            version=req.version,
            target_status=req.target_status,
            actor=req.actor,
            reason=req.reason,
            enforce_role_separation=role_sep,
        )
    except ValueError as exc:
        msg = str(exc)
        if "Role separation" in msg:
            raise HTTPException(status_code=403, detail=msg)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "transitioned", "pack": updated}


@router.post("/lifecycle/submit")
def submit_for_review(req: LifecycleTransitionRequest) -> Dict[str, Any]:
    """Submit a draft pack for review (draft → in_review)."""
    req.target_status = "in_review"
    return transition_lifecycle(req)


@router.post("/lifecycle/approve")
def approve_review(req: LifecycleTransitionRequest) -> Dict[str, Any]:
    """Approve a pack in review (in_review → approved)."""
    req.target_status = "approved"
    return transition_lifecycle(req)


@router.post("/lifecycle/reject")
def reject_review(req: LifecycleTransitionRequest) -> Dict[str, Any]:
    """Reject a pack in review back to draft (in_review → draft)."""
    req.target_status = "draft"
    return transition_lifecycle(req)


# ---------------------------------------------------------------------------
# Audit endpoints
# ---------------------------------------------------------------------------

@router.get("/audit/verify")
def verify_system_audit() -> Dict[str, Any]:
    """Verify the global audit log hash chain across all domains."""
    return verify_audit_chain()


@router.get("/audit/{domain_id}/verify")
def verify_domain_audit(domain_id: str) -> Dict[str, Any]:
    """Verify the audit log hash chain for a specific domain."""
    return verify_audit_chain(pack_id=domain_id)


@router.get("/audit/{domain_id}")
def get_domain_audit(domain_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get audit log for a domain (most recent first)."""
    return get_audit_log(domain_id, limit=limit)


# ---------------------------------------------------------------------------
# Scorecard & Evidence endpoints
# ---------------------------------------------------------------------------

@router.get("/scorecard")
def get_scorecard_evidence() -> Dict[str, Any]:
    """Retrieve measured evidence, benchmark results, and audit verification for the scorecard."""
    import json
    from pathlib import Path
    evidence_dir = Path(__file__).parent.parent.parent / "docs" / "evidence"

    def _read_json(filename: str) -> Any:
        path = evidence_dir / filename
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    engine_bench = _read_json("benchmark.json") or []
    api_bench = _read_json("api_benchmark.json") or {}
    correctness = _read_json("correctness_report.json") or {}
    scorecard_md_path = evidence_dir / "scorecard.md"
    scorecard_md = scorecard_md_path.read_text(encoding="utf-8") if scorecard_md_path.exists() else None

    audit_verification = verify_audit_chain()

    domains = list_packs()
    domains_details = []
    packs_dir = Path(__file__).parent.parent.parent / "packs"
    for d in domains:
        pack_id = d.get("pack_id")
        pack_file = packs_dir / f"{pack_id}.json"
        signal_count = 0
        rule_count = 0
        base_desc = "Unknown"
        name = pack_id.replace("_", " ").title() if pack_id else ""
        if pack_file.exists():
            try:
                pdata = json.loads(pack_file.read_text(encoding="utf-8"))
                signal_count = len(pdata.get("signals", []))
                rule_count = len(pdata.get("rules", []))
                b = pdata.get("base", {})
                b_type = b.get("type", "unknown")
                if b_type == "formula":
                    base_desc = f"Formula ({b.get('expr')})"
                elif b_type == "table":
                    base_desc = f"Table (by {b.get('by')})"
                elif b_type == "fixed":
                    base_desc = f"Fixed ({b.get('value')})"
                else:
                    base_desc = b_type
            except Exception:
                pass
        domains_details.append({
            "pack_id": pack_id,
            "name": name,
            "version": d.get("version"),
            "status": d.get("status"),
            "signals_count": signal_count,
            "rules_count": rule_count,
            "base_description": base_desc,
        })

    return {
        "engine_benchmark": engine_bench,
        "api_benchmark": api_bench,
        "correctness": correctness,
        "audit_verification": audit_verification,
        "scorecard_markdown": scorecard_md,
        "domains": domains_details,
    }
