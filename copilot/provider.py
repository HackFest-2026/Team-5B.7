"""
AI Copilot provider — translates natural language to domain pack JSON.

Uses OpenAI-compatible API (configurable via env vars).
Falls back to a stored template if the LLM is unavailable.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict

# Fallback pack used when LLM is unavailable
FALLBACK_PACK_PATH = Path(__file__).parent / "fallback_pack.json"

SYSTEM_PROMPT = """You are a pricing configuration assistant for Monetize360.

Your ONLY job is to translate a user's pricing intent into a valid JSON domain pack.

The domain pack schema is:
{
  "pack_id": "<snake_case_id>",
  "version": "1.0.0",
  "description": "<short description>",
  "unit": { "kind": "currency"|"rate"|"unit", "code": "INR"|"USD"|"PCT", "decimals": 0-4 },
  "signals": [
    { "key": "<key>", "type": "enum"|"number"|"integer"|"string"|"boolean", "values": [...], "min": <num>, "max": <num>, "required": true|false }
  ],
  "base": { "type": "fixed", "value": <num> } | { "type": "table", "by": "<signal_key>", "values": { "<key>": <num> } } | { "type": "formula", "expr": "<expr>" },
  "stages": [
    { "id": "<stage_id>", "stacking": "first"|"all"|"max_discount"|"min_discount"|"sum", "description": "<desc>" }
  ],
  "rules": [
    {
      "id": "<RULE-ID>",
      "stage": "<stage_id>",
      "priority": <integer>,
      "description": "<human readable>",
      "when": <condition> | null,
      "then": { "op": "multiply"|"add"|"subtract"|"set"|"lookup"|"formula", "value": <num> | "expr": "<expr>" | "by": "<key>", "table": {...} }
    }
  ],
  "constraints": [
    { "id": "<ID>", "type": "floor"|"ceiling"|"max_change_pct", "expr": "<expr or literal>" }
  ],
  "rounding": { "mode": "nearest"|"up"|"down"|"none", "step": <num> }
}

Condition structure:
- Simple: { "signal": "<key>", "op": "eq"|"neq"|"gt"|"gte"|"lt"|"lte"|"in"|"between", "value": <val> }
- All: { "all": [<condition>, ...] }
- Any: { "any": [<condition>, ...] }
- Not: { "not": <condition> }

Formula functions allowed: min(), max(), clamp() only.

IMPORTANT RULES:
1. Return ONLY valid JSON. No explanation, no markdown, no code blocks.
2. Every rule's stage must reference a stage listed in stages[].
3. Use snake_case for all IDs and keys.
4. If you cannot express something with the available primitives, omit it and add a comment in the description.
5. Always include at least one floor and one ceiling constraint.
"""


def generate_pack_from_prompt(prompt: str) -> Dict[str, Any]:
    """
    Call the LLM to generate a domain pack from a natural language prompt.
    
    Returns:
        { "pack": <dict>, "error": <str or None>, "raw": <str> }
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    
    if groq_key:
        api_key = groq_key
        api_base = os.environ.get("OPENAI_API_BASE", "https://api.groq.com/openai/v1")
        model = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
    elif gemini_key:
        api_key = gemini_key
        api_base = os.environ.get("OPENAI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai")
        model = os.environ.get("LLM_MODEL", "gemini-1.5-flash")
    elif deepseek_key:
        api_key = deepseek_key
        api_base = os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com/v1")
        model = os.environ.get("LLM_MODEL", "deepseek-chat")
    else:
        api_key = openai_key
        api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        return _use_fallback("No LLM API key configured (set GROQ_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY, or OPENAI_API_KEY). Running in offline fallback mode.")

    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        response = httpx.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        raw = data["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        cleaned = _strip_code_fences(raw)
        pack = json.loads(cleaned)
        return {"pack": pack, "error": None, "raw": raw}

    except Exception as exc:
        return _use_fallback(f"LLM call failed: {exc}")


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text


def _use_fallback(error: str) -> Dict[str, Any]:
    """Return the fallback EV charging pack when LLM is unavailable."""
    if FALLBACK_PACK_PATH.exists():
        pack = json.loads(FALLBACK_PACK_PATH.read_text(encoding="utf-8"))
    else:
        # Inline minimal fallback
        pack = {
            "pack_id": "ev_charging_fallback",
            "version": "1.0.0",
            "description": "EV charging fallback pack (AI unavailable)",
            "unit": {"kind": "currency", "code": "INR", "decimals": 2},
            "signals": [
                {"key": "charger_type", "type": "enum", "values": ["slow", "fast"], "required": True},
                {"key": "time_of_day", "type": "enum", "values": ["peak", "off_peak"], "required": True},
                {"key": "membership", "type": "enum", "values": ["none", "basic"], "required": False},
            ],
            "base": {"type": "fixed", "value": 18},
            "stages": [
                {"id": "charger", "stacking": "first"},
                {"id": "time_price", "stacking": "first"},
                {"id": "membership", "stacking": "max_discount"},
            ],
            "rules": [
                {"id": "R-FAST", "stage": "charger", "priority": 10, "when": {"all": [{"signal": "charger_type", "op": "eq", "value": "fast"}]}, "then": {"op": "multiply", "value": 1.40}},
                {"id": "R-PEAK", "stage": "time_price", "priority": 10, "when": {"all": [{"signal": "time_of_day", "op": "eq", "value": "peak"}]}, "then": {"op": "multiply", "value": 1.25}},
                {"id": "R-MEMBER", "stage": "membership", "priority": 10, "when": {"all": [{"signal": "membership", "op": "eq", "value": "basic"}]}, "then": {"op": "multiply", "value": 0.90}},
            ],
            "constraints": [
                {"id": "C-FLOOR", "type": "floor", "expr": "12"},
                {"id": "C-CEILING", "type": "ceiling", "expr": "40"},
            ],
            "rounding": {"mode": "nearest", "step": 0.5},
        }
    return {"pack": pack, "error": error, "raw": ""}
