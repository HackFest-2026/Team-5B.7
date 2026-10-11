"""
FastAPI application entry point.

Security and CORS notes
-----------------------
* CORS origins are read from CORS_ALLOWED_ORIGINS (see api/config.py and
  .env.example).  The default allows localhost dev servers only.
  The previous allow_origins=["*"] + allow_credentials=True combination is a
  browser-level security error (browsers reject it); it has been replaced.

* When the API_KEY environment variable is set, all mutating operations
  (POST/PUT/PATCH/DELETE) require an X-Api-Key header matching that value.
  Read operations (GET/HEAD/OPTIONS) and infrastructure paths are exempt.
  In development (API_KEY unset) the guard is transparent and a warning is
  logged at startup.

* Error responses for unexpected server errors no longer include raw Python
  exception strings to avoid leaking internal implementation details.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure the project root is on sys.path for direct invocations.
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from api.config import CORS_ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS, APP_ENV
from api.security import api_key_guard
from api.routes import (
    domains_router,
    pricing_router,
    copilot_router,
    context_router,
    store_router,
    analytics_router,
)
from api.storage import (
    init_db,
    init_store_db,
    upsert_pack,
    get_published_pack,
    publish_pack,
)

logger = logging.getLogger(__name__)

MAX_BODY_SIZE_BYTES = 1_048_576  # 1 MB maximum request payload

app = FastAPI(
    title="Monetize360 API",
    description="Universal Dynamic Pricing Engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Origins are configured via the CORS_ALLOWED_ORIGINS environment variable.
# See .env.example for documentation. In development the Vite dev server
# (localhost:5173) and CRA (localhost:3000) are allowed by default.
# allow_credentials requires explicit origins — never use "*" with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Api-Key", "X-Request-ID", "Idempotency-Key"],
)

# ---------------------------------------------------------------------------
# Security middleware — API key guard for mutating operations
# ---------------------------------------------------------------------------
app.middleware("http")(api_key_guard)


# ---------------------------------------------------------------------------
# Request body size limit
# ---------------------------------------------------------------------------
@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    """Enforce maximum request body size to guard against denial-of-service."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request entity too large. "
                            f"Maximum allowed size is {MAX_BODY_SIZE_BYTES} bytes (1MB)."
                        )
                    },
                )
        except ValueError:
            pass
    return await call_next(request)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(domains_router)
app.include_router(pricing_router)
app.include_router(copilot_router)
app.include_router(context_router)
app.include_router(store_router)
app.include_router(analytics_router)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    """Initialize DB and seed domain packs from the packs/ directory."""
    logging.basicConfig(level=logging.INFO)
    logger.info("[startup] environment=%s cors_origins=%s", APP_ENV, CORS_ALLOWED_ORIGINS)
    init_db()
    init_store_db()
    _seed_packs()


def _seed_packs() -> None:
    """Load JSON packs from packs/ and publish them if not already present.

    Seeding is idempotent: if a pack is already published the function
    preserves its status without mutating the stored content.
    """
    packs_dir = Path(__file__).parent.parent / "packs"
    if not packs_dir.exists():
        return

    for pack_file in sorted(packs_dir.glob("*.json")):
        try:
            pack_data = json.loads(pack_file.read_text(encoding="utf-8"))
            pack_id = pack_data.get("pack_id")
            version = pack_data.get("version", "1.0.0")
            if not pack_id:
                continue

            existing = get_published_pack(pack_id)
            if existing is None:
                upsert_pack(pack_id, version, pack_data, status="draft", actor="seed")
                publish_pack(pack_id, version, actor="seed")
                logger.info("[seed] Published %s v%s", pack_id, version)
            elif existing["version"] != version:
                upsert_pack(pack_id, version, pack_data, status="draft", actor="seed")
                publish_pack(pack_id, version, actor="seed")
                logger.info("[seed] Published updated %s v%s (was v%s)", pack_id, version, existing["version"])
            else:
                # Idempotent re-seed: preserves published version without mutating.
                upsert_pack(
                    pack_id,
                    version,
                    pack_data,
                    status=existing.get("status", "published"),
                    actor="seed",
                )
                logger.info("[seed] %s already published as v%s", pack_id, existing["version"])

        except Exception as exc:
            # Log the error server-side but do NOT expose it in an HTTP response.
            logger.error("[seed] Failed to load %s: %s", pack_file.name, exc)


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "Monetize360",
        "version": "1.0.0",
        "description": "Universal Dynamic Pricing Engine",
        "environment": APP_ENV,
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok", "environment": APP_ENV}
