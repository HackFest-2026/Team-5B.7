"""Validated, SQLite-backed operational context snapshots."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from engine.schema.pack import DomainPack

from .storage.db import _get_connection

DEFAULT_CONTEXT_MAX_AGE_SECONDS = 300
MAX_CONTEXT_MAX_AGE_SECONDS = 86400


class ContextError(ValueError):
    """Raised when an operational context snapshot is invalid or stale."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContextError("observed_at must include a timezone offset.")
    return value.astimezone(timezone.utc)


def _validate_value(signal_key: str, signal_type: str, value: Any, minimum: Optional[float], maximum: Optional[float], values: Optional[list[Any]]) -> None:
    if value is None:
        raise ContextError(f"Context signal '{signal_key}' cannot be null.")

    if signal_type == "number":
        if type(value) not in (int, float) or not math.isfinite(float(value)):
            raise ContextError(f"Context signal '{signal_key}' must be a finite number.")
        numeric = Decimal(str(value))
        if minimum is not None and numeric < Decimal(str(minimum)):
            raise ContextError(f"Context signal '{signal_key}' must be >= {minimum}.")
        if maximum is not None and numeric > Decimal(str(maximum)):
            raise ContextError(f"Context signal '{signal_key}' must be <= {maximum}.")
    elif signal_type == "integer":
        if type(value) is not int:
            raise ContextError(f"Context signal '{signal_key}' must be an integer.")
        numeric = Decimal(value)
        if minimum is not None and numeric < Decimal(str(minimum)):
            raise ContextError(f"Context signal '{signal_key}' must be >= {minimum}.")
        if maximum is not None and numeric > Decimal(str(maximum)):
            raise ContextError(f"Context signal '{signal_key}' must be <= {maximum}.")
    elif signal_type == "boolean":
        if type(value) is not bool:
            raise ContextError(f"Context signal '{signal_key}' must be a boolean.")
    elif signal_type == "enum":
        if value not in (values or []):
            raise ContextError(f"Context signal '{signal_key}' must be one of: {', '.join(map(str, values or []))}.")
    elif signal_type == "string" and type(value) is not str:
        raise ContextError(f"Context signal '{signal_key}' must be a string.")


def validate_context(pack: DomainPack, signals: Dict[str, Any], observed_at: datetime, max_age_seconds: int) -> Dict[str, Any]:
    """Validate a partial context snapshot against the pack's signal metadata."""
    if not isinstance(signals, dict) or not signals:
        raise ContextError("Context signals must be a non-empty JSON object.")
    if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or not 1 <= max_age_seconds <= MAX_CONTEXT_MAX_AGE_SECONDS:
        raise ContextError(f"max_age_seconds must be between 1 and {MAX_CONTEXT_MAX_AGE_SECONDS}.")

    observed = _normalise_timestamp(observed_at)
    age_seconds = (_utc_now() - observed).total_seconds()
    if age_seconds < -30:
        raise ContextError("observed_at cannot be more than 30 seconds in the future.")
    if age_seconds > max_age_seconds:
        raise ContextError("Context snapshot is stale.")

    metadata = {signal.key: signal for signal in pack.signals}
    unknown = sorted(set(signals) - set(metadata))
    if unknown:
        raise ContextError(f"Unknown context signal(s): {', '.join(unknown)}.")

    for key, value in signals.items():
        signal = metadata[key]
        _validate_value(key, signal.type, value, signal.min, signal.max, signal.values)

    return {
        "signals": signals,
        "observed_at": observed,
        "expires_at": observed + timedelta(seconds=max_age_seconds),
    }


def _ensure_table() -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_snapshots (
                domain_id TEXT PRIMARY KEY,
                signals TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _context_fingerprint(signals: Dict[str, Any]) -> str:
    canonical = json.dumps(signals, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_context(domain_id: str, pack: DomainPack, signals: Dict[str, Any], observed_at: datetime, max_age_seconds: int, source: str) -> Dict[str, Any]:
    validated = validate_context(pack, signals, observed_at, max_age_seconds)
    now = _utc_now().isoformat()
    _ensure_table()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO context_snapshots (domain_id, signals, observed_at, expires_at, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(domain_id) DO UPDATE SET
                signals = excluded.signals,
                observed_at = excluded.observed_at,
                expires_at = excluded.expires_at,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                domain_id,
                json.dumps(validated["signals"], sort_keys=True),
                validated["observed_at"].isoformat(),
                validated["expires_at"].isoformat(),
                source,
                now,
            ),
        )
    return get_context(domain_id)


def get_context(domain_id: str) -> Optional[Dict[str, Any]]:
    _ensure_table()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT domain_id, signals, observed_at, expires_at, source, updated_at FROM context_snapshots WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()
    if row is None:
        return None

    expires_at = datetime.fromisoformat(row["expires_at"])
    if _utc_now() > expires_at:
        raise ContextError(f"Context snapshot for '{domain_id}' is stale.")

    signals = json.loads(row["signals"])
    return {
        "domain_id": row["domain_id"],
        "signals": signals,
        "observed_at": row["observed_at"],
        "expires_at": row["expires_at"],
        "source": row["source"],
        "updated_at": row["updated_at"],
        "fingerprint": _context_fingerprint(signals),
    }


def merge_context(domain_id: str, signals: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a current context snapshot with request values; request wins."""
    snapshot = get_context(domain_id)
    if snapshot is None:
        return dict(signals)
    return {**snapshot["signals"], **signals}


def delete_context(domain_id: str) -> bool:
    """Delete the context snapshot for a domain."""
    _ensure_table()
    with _get_connection() as conn:
        cursor = conn.execute("DELETE FROM context_snapshots WHERE domain_id = ?", (domain_id,))
        return cursor.rowcount > 0
