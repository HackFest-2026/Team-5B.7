"""
Security middleware and dependency helpers.

API Key Guard
-------------
When the API_KEY environment variable is set, all mutating HTTP operations
(POST, PUT, PATCH, DELETE) must supply the key in the ``X-API-Key`` header.

Read-only operations (GET, HEAD, OPTIONS) are always permitted — they expose
only published pack metadata and are safe without authentication.

Development mode
----------------
When API_KEY is not set the guard logs a one-time startup warning (see
api/config.py) and passes all requests through.  This keeps local development
frictionless while making the production requirement explicit and enforceable.

Exempt paths
------------
The following paths bypass the key check regardless of method so that health
probes and documentation endpoints remain reachable by infrastructure:
  - GET /
  - GET /health
  - GET /docs
  - GET /openapi.json
  - GET /redoc
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import API_KEY

# Paths that are always reachable without an API key.
_ALWAYS_OPEN_PREFIXES = ("/docs", "/redoc", "/openapi.json")
_ALWAYS_OPEN_EXACT = {"/", "/health"}

# HTTP methods that do NOT mutate state.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


import os

async def api_key_guard(request: Request, call_next):
    """
    Middleware that enforces API key authentication on mutating requests.

    Logic:
      1. If API_KEY is not configured  → pass all requests (dev mode).
      2. If method is safe (GET/HEAD/OPTIONS) → pass.
      3. If path is in the exempt set → pass.
      4. Otherwise require X-Api-Key header to equal the configured API_KEY.
    """
    active_key = API_KEY or os.environ.get("API_KEY")
    if not active_key:
        # Dev mode — no key configured, pass everything.
        return await call_next(request)

    method = request.method.upper()
    path = request.url.path

    # Safe HTTP methods are read-only; no key required.
    if method in _SAFE_METHODS:
        return await call_next(request)

    # Infrastructure / documentation paths are always open.
    if path in _ALWAYS_OPEN_EXACT:
        return await call_next(request)
    if any(path.startswith(p) for p in _ALWAYS_OPEN_PREFIXES):
        return await call_next(request)

    # Enforce key check on all remaining mutating requests.
    supplied_key = request.headers.get("X-Api-Key") or request.headers.get("X-API-Key")
    if not supplied_key or supplied_key != active_key:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Unauthorized. A valid X-Api-Key header is required for this operation."
            },
        )

    return await call_next(request)
