"""
api/routes/analytics.py — Sales Overview, Pricing Performance, Alerts, and AI Business Analyst API.

Strictly read-only endpoints:
  - GET  /v1/analytics/overview
  - GET  /v1/analytics/pricing-performance
  - GET  /v1/analytics/alerts
  - POST /v1/analytics/analyst
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from ..models import AnalystQueryRequest
from ..storage import (
    get_sales_analytics,
    get_pricing_performance,
    generate_alerts,
    answer_analyst_question,
)

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/overview")
def sales_overview(
    domain: Optional[str] = Query("ecommerce"),
    range: str = Query("7d"),
) -> Dict[str, Any]:
    """
    Fetch Sales Overview KPIs, sales trend chart data, and category breakdown.
    Calculates revenue from confirmed store orders.
    """
    try:
        return get_sales_analytics(domain=domain, time_range=range)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sales overview: {exc}")


@router.get("/pricing-performance")
def pricing_performance(
    domain: Optional[str] = Query("ecommerce"),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """
    Fetch Pricing Performance telemetry:
      - Pricing evaluation counts
      - Price trend from real engine evaluations
      - Most frequently triggered rules
      - Floor/ceiling guardrail hits
    """
    try:
        return get_pricing_performance(domain=domain, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pricing performance: {exc}")


@router.get("/alerts")
def alerts(
    domain: Optional[str] = Query("ecommerce"),
) -> List[Dict[str, Any]]:
    """
    Fetch explainable alerts and opportunities based on simple threshold logic:
      - Frequent floor/ceiling hits (>20%)
      - High price spread
      - Critical inventory stock depletion
    """
    try:
        return generate_alerts(domain=domain)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate alerts: {exc}")


@router.post("/analyst")
def business_analyst(req: AnalystQueryRequest) -> Dict[str, Any]:
    """
    Evidence-based AI Business Analyst question answering.
    Read-only — queries actual database state and returns truthful answers.
    Clearly notes unavailable data when questions exceed tracked metrics.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query text cannot be empty.")

    try:
        # Check if an external LLM is configured; otherwise use the deterministic evidence engine
        openai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        groq_key = os.environ.get("GROQ_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

        result = answer_analyst_question(query=req.query, domain=req.domain)

        # If LLM key is present, we could optionally enhance response phrasing while keeping evidence ground truth
        if (openai_key or groq_key or gemini_key or deepseek_key) and result.get("can_answer"):
            # Attempt LLM summarization if reachable
            try:
                import httpx
                if groq_key:
                    api_key = groq_key
                    api_base = os.environ.get("OPENAI_API_BASE", "https://api.groq.com/openai/v1")
                    model = "llama-3.3-70b-versatile"
                elif gemini_key:
                    api_key = gemini_key
                    api_base = os.environ.get("OPENAI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai")
                    model = "gemini-1.5-flash"
                elif deepseek_key:
                    api_key = deepseek_key
                    api_base = os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com/v1")
                    model = "deepseek-chat"
                else:
                    api_key = openai_key
                    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
                    model = "gpt-4o-mini"

                prompt = (
                    "You are RateWeaver's read-only business analyst assistant.\n"
                    "Respond to the user's question concisely using ONLY the provided verified evidence.\n"
                    "Do NOT extrapolate, hallucinate, or recommend changing pricing rules.\n\n"
                    f"User Query: {req.query}\n"
                    f"Verified Evidence: {result['evidence']}\n"
                    f"Deterministic Summary: {result['answer']}"
                )
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                resp = httpx.post(
                    f"{api_base}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 300,
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    llm_ans = resp.json()["choices"][0]["message"]["content"].strip()
                    if llm_ans:
                        result["answer"] = llm_ans
                        result["llm_augmented"] = True
            except Exception:
                # Fallback directly to deterministic evidence answer
                pass

        return result

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analyst processing error: {exc}")
