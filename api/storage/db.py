"""
Storage layer — SQLite-backed pack management.

Uses JSON columns for pack data. No ORM dependency.
Includes:
  - Semantic versioning validation and version bumping
  - Explicit lifecycle states: draft, in_review, approved, published, archived
  - Version immutability (published/archived packs cannot be mutated)
  - SHA-256 canonical pack fingerprinting
  - Tamper-evident cryptographic audit log with SHA-256 hash chain
  - Audit chain verification
  - Safe rollback preserving historical version immutability
  - Four-eyes role separation and publishing gates
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from engine.fingerprint import compute_pack_fingerprint, verify_pack_fingerprint
from engine.schema.pack import DomainPack, is_valid_semver, SEMVER_REGEX
from engine.validate import validate_pack
from engine.runtime import compute_price


_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "monetize360.db"
import os
DB_PATH = Path(os.environ["DB_PATH"]) if os.environ.get("DB_PATH") else _DEFAULT_DB_PATH
GENESIS_HASH = "0" * 64

LIFECYCLE_STATES = frozenset({"draft", "in_review", "approved", "published", "archived"})

VALID_TRANSITIONS = {
    "draft": {"in_review", "published"},
    "in_review": {"approved", "draft"},
    "approved": {"published", "draft"},
    "published": {"archived"},
    "archived": {"published"},
}


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class StorageError(Exception):
    """Base storage layer exception."""


class ImmutableVersionError(StorageError):
    """Raised when an attempt is made to mutate a published or archived version."""


class StaleVersionConflictError(StorageError):
    """Raised when an update conflicts with the current persisted state (optimistic concurrency conflict)."""


class TamperError(StorageError):
    """Raised when data tampering or hash mismatch is detected."""


# ---------------------------------------------------------------------------
# Semantic Versioning Helpers
# ---------------------------------------------------------------------------

def validate_semver(version: str) -> bool:
    """Validate Semantic Versioning string format (e.g., '1.0.0')."""
    return is_valid_semver(version)


def bump_semver(version: str, bump_type: str = "minor") -> str:
    """
    Deterministically bump a Semantic Version.
    Supports 'major', 'minor', and 'patch'.
    """
    if not validate_semver(version):
        raise ValueError(f"Cannot bump invalid SemVer '{version}'.")
    m = SEMVER_REGEX.match(version.strip())
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown bump type '{bump_type}'. Choose 'major', 'minor', or 'patch'.")


# ---------------------------------------------------------------------------
# Connection & Migration
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Ensure all required columns exist in older database files."""
    pack_cols = {row["name"] for row in conn.execute("PRAGMA table_info(packs)").fetchall()}
    if "created_by" not in pack_cols:
        conn.execute("ALTER TABLE packs ADD COLUMN created_by TEXT DEFAULT 'system'")
    if "fingerprint" not in pack_cols:
        conn.execute("ALTER TABLE packs ADD COLUMN fingerprint TEXT")

    audit_cols = {row["name"] for row in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
    if "prev_hash" not in audit_cols:
        conn.execute("ALTER TABLE audit_log ADD COLUMN prev_hash TEXT")
    if "entry_hash" not in audit_cols:
        conn.execute("ALTER TABLE audit_log ADD COLUMN entry_hash TEXT")


def init_db() -> None:
    """Create tables if they don't exist and run column migrations."""
    with _get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS packs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pack_id     TEXT NOT NULL,
                version     TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'draft',
                pack_data   TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                published_at TEXT,
                published_by TEXT,
                fingerprint TEXT,
                created_by  TEXT DEFAULT 'system',
                UNIQUE(pack_id, version)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pack_id     TEXT NOT NULL,
                version     TEXT,
                event       TEXT NOT NULL,
                actor       TEXT NOT NULL DEFAULT 'system',
                detail      TEXT,
                created_at  TEXT NOT NULL,
                prev_hash   TEXT,
                entry_hash  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_packs_pack_id ON packs(pack_id);
            CREATE INDEX IF NOT EXISTS idx_audit_pack_id ON audit_log(pack_id);
        """)
        _migrate_db(conn)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Audit Log Hash Chain
# ---------------------------------------------------------------------------

def _compute_audit_entry_hash(
    prev_hash: str,
    pack_id: str,
    version: Optional[str],
    event: str,
    actor: str,
    detail: Optional[str],
    created_at: str,
) -> str:
    """Deterministically compute SHA-256 for an audit entry."""
    payload = {
        "prev_hash": prev_hash,
        "pack_id": str(pack_id),
        "version": str(version) if version is not None else "",
        "event": str(event),
        "actor": str(actor),
        "detail": str(detail) if detail is not None else "",
        "created_at": str(created_at),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_AUDIT_CHAIN_LOCK = threading.Lock()


def _log_audit_conn(
    conn: sqlite3.Connection,
    pack_id: str,
    version: Optional[str],
    event: str,
    actor: str,
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a cryptographically linked entry to the audit log."""
    with _AUDIT_CHAIN_LOCK:
        now = _now()
        last_entry = conn.execute(
            "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        prev_hash = last_entry["entry_hash"] if (last_entry and last_entry["entry_hash"]) else GENESIS_HASH
        entry_hash = _compute_audit_entry_hash(
            prev_hash=prev_hash,
            pack_id=pack_id,
            version=version,
            event=event,
            actor=actor,
            detail=detail,
            created_at=now,
        )
        cursor = conn.execute(
            """
            INSERT INTO audit_log (pack_id, version, event, actor, detail, created_at, prev_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pack_id, version, event, actor, detail, now, prev_hash, entry_hash),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "pack_id": pack_id,
            "version": version,
            "event": event,
            "action": event,
            "actor": actor,
            "detail": detail,
            "created_at": now,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        }


def _log_audit(
    pack_id: str,
    version: Optional[str],
    event: str,
    actor: str,
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    with _get_connection() as conn:
        return _log_audit_conn(conn, pack_id, version, event, actor, detail)


log_audit_event = _log_audit  # Public alias for audit logging


def get_audit_log(pack_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Get audit entries, optionally filtered by pack_id."""
    with _get_connection() as conn:
        if pack_id:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE pack_id = ? ORDER BY id DESC LIMIT ?",
                (pack_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["action"] = d.get("event")  # compatibility with frontend
            result.append(d)
        return result


def verify_audit_chain(pack_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify the cryptographic hash chain of the audit log.
    Detects any tampering, insertion, deletion, or reordering.
    """
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id ASC").fetchall()
        if not rows:
            return {
                "valid": True,
                "total_records": 0,
                "message": "Audit log is empty",
            }

        expected_prev = GENESIS_HASH
        records_checked = 0

        for row in rows:
            row_id = row["id"]
            prev_hash = row["prev_hash"]
            entry_hash = row["entry_hash"]

            if not prev_hash or not entry_hash:
                return {
                    "valid": False,
                    "tampered_id": row_id,
                    "reason": f"Entry {row_id} lacks cryptographic hash chain metadata.",
                    "records_checked": records_checked,
                }

            if prev_hash != expected_prev:
                return {
                    "valid": False,
                    "tampered_id": row_id,
                    "reason": f"Broken chain link at entry {row_id}: prev_hash does not match preceding entry_hash.",
                    "expected_prev_hash": expected_prev,
                    "actual_prev_hash": prev_hash,
                    "records_checked": records_checked,
                }

            recomputed_hash = _compute_audit_entry_hash(
                prev_hash=prev_hash,
                pack_id=row["pack_id"],
                version=row["version"],
                event=row["event"],
                actor=row["actor"],
                detail=row["detail"],
                created_at=row["created_at"],
            )

            if entry_hash != recomputed_hash:
                return {
                    "valid": False,
                    "tampered_id": row_id,
                    "reason": f"Hash mismatch at entry {row_id}: entry content has been modified.",
                    "expected_entry_hash": recomputed_hash,
                    "actual_entry_hash": entry_hash,
                    "records_checked": records_checked,
                }

            expected_prev = entry_hash
            records_checked += 1

        return {
            "valid": True,
            "total_records": records_checked,
            "latest_hash": expected_prev,
            "message": "Audit hash chain is intact and fully verified.",
        }


def log_price_event(pack_id: str, version: str, fingerprint: str, signals: dict, price: float) -> None:
    detail = json.dumps({"fingerprint": fingerprint, "signals": signals, "price": price}, sort_keys=True)
    _log_audit(pack_id, version, "price_computed", "engine", detail)


# ---------------------------------------------------------------------------
# Pack Management (CRUD, SemVer & Immutability)
# ---------------------------------------------------------------------------

def upsert_pack(
    pack_id: str,
    version: str,
    pack_data: dict,
    status: str = "draft",
    actor: str = "system",
    expected_fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upsert pack data with SemVer validation, immutability enforcement, and optimistic concurrency.
    """
    if not validate_semver(version):
        raise ValueError(f"Version '{version}' is not valid Semantic Versioning. Expected X.Y.Z (e.g. '1.0.0').")

    if status not in LIFECYCLE_STATES:
        raise ValueError(f"Invalid status '{status}'. Allowed: {sorted(LIFECYCLE_STATES)}")

    now = _now()
    fp = compute_pack_fingerprint(pack_data)

    with _get_connection() as conn:
        existing = conn.execute(
            "SELECT id, status, pack_data, fingerprint FROM packs WHERE pack_id = ? AND version = ?",
            (pack_id, version),
        ).fetchone()

        if existing:
            existing_status = existing["status"]
            existing_fp = existing["fingerprint"]
            if not existing_fp and existing["pack_data"]:
                try:
                    existing_fp = compute_pack_fingerprint(json.loads(existing["pack_data"]))
                except Exception:
                    existing_fp = None

            # Stale-version / optimistic concurrency check:
            if expected_fingerprint is not None and existing_fp != expected_fingerprint:
                raise StaleVersionConflictError(
                    f"Stale version conflict on pack '{pack_id}' v{version}: "
                    f"current fingerprint is '{existing_fp[:12] if existing_fp else 'unknown'}...', "
                    f"but expected '{expected_fingerprint[:12]}...'. "
                    "Another update occurred concurrently; please reload the pack."
                )

            # Immutability enforcement:
            if existing_status in ("published", "archived"):
                if existing_fp == fp:
                    # Content is identical: idempotent no-op, preserve published/archived status
                    if not existing["fingerprint"]:
                        conn.execute("UPDATE packs SET fingerprint = ? WHERE id = ?", (fp, existing["id"]))
                    return get_pack(pack_id, version)
                else:
                    raise ImmutableVersionError(
                        f"Version '{version}' of pack '{pack_id}' is {existing_status} and immutable. "
                        "Cannot overwrite a published or archived version with different configuration. "
                        "Please create a new version."
                    )

            # If existing pack was in_review or approved and content is modified, reset to draft
            new_status = status
            event_name = "draft_updated"
            if existing_status in ("in_review", "approved") and existing_fp != fp:
                new_status = "draft"
                event_name = "draft_reset_on_edit"

            conn.execute(
                """
                UPDATE packs
                SET pack_data = ?, status = ?, fingerprint = ?, updated_at = ?
                WHERE pack_id = ? AND version = ?
                """,
                (json.dumps(pack_data), new_status, fp, now, pack_id, version),
            )
            _log_audit_conn(
                conn,
                pack_id=pack_id,
                version=version,
                event=event_name,
                actor=actor,
                detail=f"Updated pack {pack_id} v{version} (status: {new_status}, fingerprint: {fp[:12]}...)",
            )
        else:
            # Create new pack
            conn.execute(
                """
                INSERT INTO packs (pack_id, version, status, pack_data, fingerprint, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pack_id, version, status, json.dumps(pack_data), fp, actor, now, now),
            )
            event_name = "draft_created" if status == "draft" else f"pack_{status}"
            _log_audit_conn(
                conn,
                pack_id=pack_id,
                version=version,
                event=event_name,
                actor=actor,
                detail=f"Created {pack_id} v{version} as {status} (fingerprint: {fp[:12]}...)",
            )

    return get_pack(pack_id, version)


def create_new_version(
    pack_id: str,
    bump_type: str = "minor",
    custom_version: Optional[str] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Create a new draft version for a domain pack:
      - Validates SemVer
      - Copies configuration from the latest active version
      - Initializes status as 'draft'
      - Sets author/created_by
    """
    base_pack = get_published_pack(pack_id) or get_pack(pack_id)
    if base_pack is None:
        raise ValueError(f"Domain '{pack_id}' not found. Cannot create new version.")

    if custom_version:
        if not validate_semver(custom_version):
            raise ValueError(f"Custom version '{custom_version}' is not valid Semantic Versioning (X.Y.Z).")
        new_version = custom_version.strip()
    else:
        new_version = bump_semver(base_pack["version"], bump_type=bump_type)

    existing = get_pack(pack_id, new_version)
    if existing:
        raise ValueError(f"Version '{new_version}' already exists for pack '{pack_id}'.")

    new_pack_data = copy.deepcopy(base_pack["pack_data"])
    new_pack_data["version"] = new_version

    return upsert_pack(pack_id, new_version, new_pack_data, status="draft", actor=actor)


# ---------------------------------------------------------------------------
# Explicit Lifecycle Transitions
# ---------------------------------------------------------------------------

def transition_pack_lifecycle(
    pack_id: str,
    version: str,
    target_status: str,
    actor: str = "system",
    reason: Optional[str] = None,
    enforce_role_separation: bool = False,
) -> Dict[str, Any]:
    """
    Explicit lifecycle transition:
      draft -> in_review -> approved -> published -> archived
    Validates state transitions and enforces actor permissions.
    """
    if target_status not in LIFECYCLE_STATES:
        raise ValueError(f"Invalid target status '{target_status}'. Allowed: {sorted(LIFECYCLE_STATES)}")

    pack_row = get_pack(pack_id, version)
    if pack_row is None:
        raise ValueError(f"Pack '{pack_id}' v{version} not found.")

    current_status = pack_row.get("status", "draft")
    if current_status == target_status:
        return pack_row

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ValueError(
            f"Invalid lifecycle transition for pack '{pack_id}' v{version} from '{current_status}' to '{target_status}'. "
            f"Allowed transitions from '{current_status}': {sorted(allowed)}"
        )

    # Actor permission checks: approver cannot be draft editor
    if target_status == "approved" and enforce_role_separation:
        draft_author = pack_row.get("created_by") or "system"
        if actor != "seed" and actor.lower() == draft_author.lower():
            raise ValueError(
                f"Role separation violation: Editor '{draft_author}' cannot approve their own pack. "
                "A separate reviewer/approver is required."
            )

    now = _now()
    with _get_connection() as conn:
        conn.execute(
            "UPDATE packs SET status = ?, updated_at = ? WHERE pack_id = ? AND version = ?",
            (target_status, now, pack_id, version),
        )
        detail = json.dumps({
            "action": "lifecycle_transition",
            "from_status": current_status,
            "to_status": target_status,
            "reason": reason,
        }, sort_keys=True)
        _log_audit_conn(
            conn,
            pack_id=pack_id,
            version=version,
            event=f"status_{target_status}",
            actor=actor,
            detail=detail,
        )

    return get_pack(pack_id, version)


def get_pack(pack_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get a pack. If version is None, returns the latest published, or latest by updated_at."""
    with _get_connection() as conn:
        if version:
            row = conn.execute(
                "SELECT * FROM packs WHERE pack_id = ? AND version = ?",
                (pack_id, version),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM packs
                WHERE pack_id = ?
                ORDER BY
                    CASE WHEN status = 'published' THEN 0 ELSE 1 END,
                    updated_at DESC
                LIMIT 1
                """,
                (pack_id,),
            ).fetchone()

        if row is None:
            return None
        return _row_to_dict(row)


def get_published_pack(pack_id: str) -> Optional[Dict[str, Any]]:
    """Get the currently published version of a pack."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM packs WHERE pack_id = ? AND status = 'published' ORDER BY published_at DESC LIMIT 1",
            (pack_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)


def publish_pack(
    pack_id: str,
    version: str,
    actor: str = "demo-user",
    approver: Optional[str] = None,
    enforce_role_separation: bool = False,
    run_golden_tests: bool = True,
    require_approval: bool = False,
) -> Dict[str, Any]:
    """
    Publish a pack version with safety gates:
      1. Pack must exist.
      2. If require_approval is True, pack must be in 'approved' status.
      3. Fingerprint integrity check (tamper detection).
      4. Schema and rule validation.
      5. Golden test verification (if test cases are defined in pack).
      6. Four-eyes / role separation check (editor cannot approve their own changes).
    """
    pack_row = get_pack(pack_id, version)
    if pack_row is None:
        raise ValueError(f"Pack '{pack_id}' v{version} not found.")

    current_status = pack_row.get("status", "draft")
    if require_approval and current_status != "approved":
        raise ValueError(
            f"Publish blocked: Pack '{pack_id}' v{version} is in status '{current_status}'. "
            "It must be in 'approved' status before publishing."
        )

    pack_data = pack_row["pack_data"]

    # 1. Fingerprint verification
    expected_fp = pack_row.get("fingerprint")
    actual_fp = compute_pack_fingerprint(pack_data)
    if expected_fp and expected_fp != actual_fp:
        raise TamperError(
            f"Integrity check failed for pack '{pack_id}' v{version}: "
            f"Stored fingerprint '{expected_fp}' does not match content hash '{actual_fp}'."
        )

    # 2. Schema and rule validation
    try:
        pack_obj = DomainPack.model_validate(pack_data)
    except Exception as exc:
        raise ValueError(f"Schema validation failed: {exc}") from exc

    validation = validate_pack(pack_obj)
    if not validation.valid:
        error_msgs = "; ".join(e.message for e in validation.errors)
        raise ValueError(f"Publish blocked: validation failed: {error_msgs}")

    # 3. Golden test verification (if test cases are defined in pack or provided)
    if run_golden_tests:
        test_cases = pack_data.get("test_cases") or pack_data.get("golden_tests") or []
        for idx, tc in enumerate(test_cases):
            signals = tc.get("signals", {})
            expected_price = tc.get("expected_price")
            if expected_price is not None:
                try:
                    price_res = compute_price(pack_obj, signals)
                    if abs(float(price_res.price) - float(expected_price)) > 1e-4:
                        raise ValueError(
                            f"Golden test #{idx + 1} failed: expected {expected_price}, got {price_res.price} "
                            f"with signals {signals}"
                        )
                except Exception as exc:
                    raise ValueError(f"Golden test #{idx + 1} execution error: {exc}") from exc

    # 4. Role separation (four-eyes principle)
    effective_approver = approver or actor
    draft_author = pack_row.get("created_by") or "system"
    if enforce_role_separation:
        if effective_approver != "seed" and effective_approver.lower() == draft_author.lower():
            raise ValueError(
                f"Role separation violation: Editor '{draft_author}' cannot approve/publish their own pack. "
                "A separate approver is required."
            )

    now = _now()
    with _get_connection() as conn:
        # Archive any currently published versions
        conn.execute(
            "UPDATE packs SET status = 'archived', updated_at = ? WHERE pack_id = ? AND status = 'published'",
            (now, pack_id),
        )
        # Publish the target version
        conn.execute(
            """
            UPDATE packs
            SET status = 'published', published_at = ?, published_by = ?, fingerprint = ?, updated_at = ?
            WHERE pack_id = ? AND version = ?
            """,
            (now, effective_approver, actual_fp, now, pack_id, version),
        )
        _log_audit_conn(
            conn,
            pack_id=pack_id,
            version=version,
            event="published",
            actor=effective_approver,
            detail=f"Version {version} published (fingerprint: {actual_fp[:12]}..., author: {draft_author})",
        )

    return get_pack(pack_id, version)


def rollback_pack(
    pack_id: str,
    target_version: str,
    actor: str = "demo-user",
) -> Dict[str, Any]:
    """
    Safely rollback a domain to a previous version:
      - Restores the target version as published.
      - Archives the currently published version.
      - Preserves version history (does NOT mutate historical pack content).
      - Verifies integrity of the target version before rollback.
      - Records the rollback in the cryptographic audit log.
    """
    target_row = get_pack(pack_id, target_version)
    if target_row is None:
        raise ValueError(f"Cannot rollback: target version '{target_version}' not found for pack '{pack_id}'.")

    # Integrity check on target version
    actual_fp = compute_pack_fingerprint(target_row["pack_data"])
    if target_row.get("fingerprint") and target_row["fingerprint"] != actual_fp:
        raise TamperError(
            f"Cannot rollback: target version '{target_version}' failed integrity verification."
        )

    # Validation check on target version
    try:
        pack_obj = DomainPack.model_validate(target_row["pack_data"])
        v_res = validate_pack(pack_obj)
        if not v_res.valid:
            raise ValueError("Cannot rollback: target version failed pack validation.")
    except Exception as exc:
        raise ValueError(f"Cannot rollback: target version failed validation: {exc}") from exc

    current_pub = get_published_pack(pack_id)
    from_version = current_pub["version"] if current_pub else None

    if from_version == target_version:
        raise ValueError(f"Pack '{pack_id}' is already at version '{target_version}'.")

    now = _now()
    with _get_connection() as conn:
        # Archive current published version
        conn.execute(
            "UPDATE packs SET status = 'archived', updated_at = ? WHERE pack_id = ? AND status = 'published'",
            (now, pack_id),
        )
        # Restore target version as published
        conn.execute(
            """
            UPDATE packs
            SET status = 'published', published_at = ?, published_by = ?, updated_at = ?
            WHERE pack_id = ? AND version = ?
            """,
            (now, actor, now, pack_id, target_version),
        )
        audit_detail = json.dumps({
            "action": "rollback",
            "from_version": from_version,
            "to_version": target_version,
            "restored_by": actor,
            "fingerprint": actual_fp,
        }, sort_keys=True)
        _log_audit_conn(
            conn,
            pack_id=pack_id,
            version=target_version,
            event="rollback",
            actor=actor,
            detail=audit_detail,
        )

    return get_pack(pack_id, target_version)


def list_packs() -> List[Dict[str, Any]]:
    """List all unique domain IDs with their current status."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT pack_id, version, status, created_at, updated_at, published_at, published_by, fingerprint
            FROM packs
            ORDER BY pack_id, updated_at DESC
            """
        ).fetchall()
        seen = {}
        result = []
        for row in rows:
            pid = row["pack_id"]
            if pid not in seen:
                seen[pid] = True
                result.append(dict(row))
        return result


def list_all_pack_versions(pack_id: str) -> List[Dict[str, Any]]:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT pack_id, version, status, created_at, updated_at, published_at, published_by, fingerprint, created_by
            FROM packs
            WHERE pack_id = ?
            ORDER BY updated_at DESC
            """,
            (pack_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    if "pack_data" in d and d["pack_data"]:
        try:
            d["pack_data"] = json.loads(d["pack_data"])
        except Exception:
            pass
    if "fingerprint" in d and d["fingerprint"]:
        # Verify content integrity against fingerprint
        if isinstance(d.get("pack_data"), dict):
            actual_fp = compute_pack_fingerprint(d["pack_data"])
            d["fingerprint_verified"] = (actual_fp == d["fingerprint"])
        else:
            d["fingerprint_verified"] = True
    elif isinstance(d.get("pack_data"), dict):
        d["fingerprint"] = compute_pack_fingerprint(d["pack_data"])
        d["fingerprint_verified"] = True
    return d
