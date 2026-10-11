"""
API request/response models.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class PriceRequest(BaseModel):
    domain: str
    signals: Dict[str, Any]
    actor: str = "api"


class BatchPriceItem(BaseModel):
    id: str
    signals: Dict[str, Any]


class BatchPriceRequest(BaseModel):
    domain: str
    items: List[BatchPriceItem]
    actor: str = "api"


class SimulateRequest(BaseModel):
    domain: str
    signals: Dict[str, Any]


class SweepRequest(BaseModel):
    domain: str
    base_signals: Dict[str, Any]
    sweep_signal: str
    sweep_values: List[Any]


class BeforeAfterRequest(BaseModel):
    domain: str
    signals_before: Dict[str, Any]
    signals_after: Dict[str, Any]


class CounterfactualRequest(BaseModel):
    domain: str
    base_signals: Dict[str, Any]
    counterfactuals: List[Dict[str, Any]]


class ContextUpdateRequest(BaseModel):
    signals: Dict[str, Any]
    observed_at: datetime
    max_age_seconds: int = Field(default=300, ge=1, le=86400)
    source: str = Field(default="synthetic-demo", min_length=1, max_length=100)


class ValidateRequest(BaseModel):
    pack: Dict[str, Any]
    actor: str = "validator"


class PublishRequest(BaseModel):
    pack_id: str
    version: str
    actor: str = "demo-user"
    approver: Optional[str] = None
    enforce_role_separation: Optional[bool] = None
    run_golden_tests: bool = True
    require_approval: Optional[bool] = None


class RollbackRequest(BaseModel):
    pack_id: str
    target_version: str
    actor: str = "demo-user"


class PackDraftRequest(BaseModel):
    pack: Dict[str, Any]
    actor: str = "draft-user"
    base_fingerprint: Optional[str] = None


class LifecycleTransitionRequest(BaseModel):
    pack_id: str
    version: str
    target_status: Optional[str] = None
    actor: str = "demo-user"
    reason: Optional[str] = None
    enforce_role_separation: Optional[bool] = None



class BumpVersionRequest(BaseModel):
    bump_type: Literal["major", "minor", "patch"] = "minor"
    custom_version: Optional[str] = None
    actor: str = "demo-user"


class StoreItemInput(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=500)
    expected_unit_price: Optional[float] = None


class StoreCheckoutRequest(BaseModel):
    idempotency_key: str
    items: List[StoreItemInput]
    customer_tier: Literal["guest", "regular", "prime", "elite"] = "guest"
    is_flash_sale: bool = False
    confirm_price_change: bool = False


class StoreQuoteRequest(BaseModel):
    items: List[StoreItemInput]
    customer_tier: Literal["guest", "regular", "prime", "elite"] = "guest"
    is_flash_sale: bool = False


class AnalystQueryRequest(BaseModel):
    query: str
    domain: Optional[str] = "ecommerce"
