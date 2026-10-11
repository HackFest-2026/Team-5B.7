"""
AI Copilot route — natural language → domain pack draft.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from copilot.provider import generate_pack_from_prompt
from engine.schema.pack import DomainPack
from engine.validate import validate_pack
from ..storage import upsert_pack

router = APIRouter(prefix="/v1/copilot", tags=["copilot"])


class CopilotRequest(BaseModel):
    prompt: str
    actor: str = "copilot-user"


@router.post("/generate")
def copilot_generate(req: CopilotRequest) -> Dict[str, Any]:
    """
    Translate natural language pricing intent into a domain pack draft.

    The AI cannot publish. It can only propose. The human approves.
    """
    result = generate_pack_from_prompt(req.prompt)

    if result.get("error"):
        return {
            "status": "fallback_used",
            "warning": result["error"],
            "pack": result["pack"],
            "validation": None,
        }

    pack_data = result["pack"]

    # Schema validation
    try:
        pack = DomainPack.model_validate(pack_data)
    except Exception as exc:
        return {
            "status": "schema_invalid",
            "error": str(exc),
            "pack": pack_data,
            "validation": None,
        }

    # Semantic validation
    validation = validate_pack(pack)

    # Save as draft (not published — human must approve)
    upsert_pack(pack.pack_id, pack.version, pack_data, status="draft")

    return {
        "status": "draft_saved" if validation.valid else "draft_saved_with_warnings",
        "pack": pack_data,
        "validation": validation.to_dict(),
    }
