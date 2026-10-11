"""
Application configuration — loaded from environment variables.

All security-sensitive settings are read from the environment so that
secrets never appear in source code.  See .env.example for documentation.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

# Auto-load .env file from project root if present
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.exists():
    try:
        for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _k, _v = _k.strip(), _v.strip()
                if _k and _k not in os.environ:
                    os.environ[_k] = _v
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def _parse_origins(raw: str) -> list[str]:
    """Parse a comma-separated origins string into a clean list."""
    return [o.strip() for o in raw.split(",") if o.strip()]


_CORS_ENV = os.environ.get("CORS_ALLOWED_ORIGINS", "")

if _CORS_ENV:
    CORS_ALLOWED_ORIGINS: list[str] = _parse_origins(_CORS_ENV)
else:
    # Safe default for local development: Vite (5173) and CRA (3000).
    # Explicitly NOT "*" — combining "*" with allow_credentials=True is a
    # browser-level security error and will be rejected by all modern browsers.
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

# Credentials (cookies / Authorization headers) are only safe when origins
# are explicit.  We therefore always derive this from the origins list.
CORS_ALLOW_CREDENTIALS: bool = bool(CORS_ALLOWED_ORIGINS)

# ---------------------------------------------------------------------------
# API Key guard for mutating operations
# ---------------------------------------------------------------------------

API_KEY: str | None = os.environ.get("API_KEY") or None

# Dev-mode warning — emitted once at import time so it appears in server logs.
if API_KEY is None:
    warnings.warn(
        "[security] API_KEY is not set. Mutating endpoints (draft/publish/rollback) "
        "are unprotected. Set API_KEY in your environment for production use.",
        stacklevel=1,
    )

# ---------------------------------------------------------------------------
# Application environment label
# ---------------------------------------------------------------------------

APP_ENV: str = os.environ.get("APP_ENV", "development")

# ---------------------------------------------------------------------------
# Database path override
# ---------------------------------------------------------------------------

DB_PATH_OVERRIDE: str | None = os.environ.get("DB_PATH") or None

# ---------------------------------------------------------------------------
# Governance & Role Separation Defaults
# ---------------------------------------------------------------------------

REQUIRE_APPROVAL: bool = os.environ.get("REQUIRE_APPROVAL", "false").lower() in ("true", "1", "yes")
ENFORCE_ROLE_SEPARATION: bool = os.environ.get("ENFORCE_ROLE_SEPARATION", "false").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# LLM Providers Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY") or None

