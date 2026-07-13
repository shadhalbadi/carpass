from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# Auth
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = ""
    role: str = "buyer"
    company_name: str = ""
    phone: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    company_name: str
    phone: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# Cars / listings
class CarRecord(BaseModel):
    make: str = ""
    model: str = ""
    year: int | None = None
    mileage: int | None = None
    mileage_unit: str = "km"
    vin: str = ""
    damage: str = ""
    price: float = 0.0
    currency: str = "USD"
    location: str = ""
    country: str = ""
    photos: list[str] = []
    title: str = ""
    source: str = ""
    source_url: str = ""
    source_id: str = ""


class ListingOut(BaseModel):
    id: int
    source: str
    source_url: str
    make: str
    model: str
    year: int | None
    mileage: int | None
    mileage_unit: str
    vin: str
    damage: str
    price: float
    currency: str
    location: str
    country: str
    photos: list[str] = []
    title: str
    normalized_make: str
    normalized_model: str
    price_omr: float
    landed_cost_omr: float | None
    is_local: bool
    fetched_at: datetime
    freshness: str = ""

    model_config = {"from_attributes": True}


class ListingSearchParams(BaseModel):
    q: str | None = None
    make: str | None = None
    model: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    max_landed_omr: float | None = None
    source: str | None = None
    is_local: bool | None = None
    page: int = 1
    page_size: int = 20


class ListingSearchResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ListingOut]
    live: bool = False
    sources_ok: list[str] = []
    sources_attempted: list[str] = []
    errors: dict[str, str] = {}
    search_urls: dict[str, str] = {}
    message: str = ""


# Cost calculator
class FetchUrlRequest(BaseModel):
    url: str
    save: bool = True


class ManualCarRequest(BaseModel):
    car: CarRecord
    origin_country: str | None = None
    mode: str = "roro"
    save: bool = True


class CostLineItem(BaseModel):
    key: str
    label: str
    amount_omr: float
    amount_original: float | None = None
    currency_original: str | None = None
    notes: str = ""


class CostBreakdown(BaseModel):
    car: CarRecord
    line_items: list[CostLineItem]
    cif_omr: float
    total_landed_omr: float
    exchange_rates: dict[str, float]
    route: dict[str, Any] | None = None
    local_compare_omr: float | None = None
    local_sample_count: int = 0
    verdict: str = ""
    savings_omr: float | None = None
    verdict_message: str = ""


class CalculationOut(BaseModel):
    id: int
    source_url: str
    car: dict[str, Any]
    breakdown: dict[str, Any]
    total_landed_omr: float
    local_compare_omr: float | None
    verdict: str
    savings_omr: float | None
    created_at: datetime


# Fees / admin
class FeeOut(BaseModel):
    id: int
    key: str
    label: str
    value: float
    unit: str
    category: str
    notes: str

    model_config = {"from_attributes": True}


class FeeUpdate(BaseModel):
    value: float
    notes: str | None = None


class ShippingRouteOut(BaseModel):
    id: int
    origin_country: str
    origin_port: str
    dest_port: str
    mode: str
    min_usd: float
    max_usd: float
    inland_usd: float
    transit_days_min: int
    transit_days_max: int
    is_active: bool

    model_config = {"from_attributes": True}


class ShippingRouteUpdate(BaseModel):
    min_usd: float | None = None
    max_usd: float | None = None
    inland_usd: float | None = None
    transit_days_min: int | None = None
    transit_days_max: int | None = None
    is_active: bool | None = None


# Watches
class WatchCreate(BaseModel):
    name: str = ""
    make: str = ""
    model: str = ""
    year_min: int | None = None
    year_max: int | None = None
    max_landed_omr: float | None = None
    sources: list[str] = []


class WatchOut(BaseModel):
    id: int
    name: str
    make: str
    model: str
    year_min: int | None
    year_max: int | None
    max_landed_omr: float | None
    sources: list[str] = []
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: int
    title: str
    body: str
    is_read: bool
    created_at: datetime
    watch_id: int | None = None
    shipment_id: int | None = None

    model_config = {"from_attributes": True}


# Shipments
class ShipmentCreate(BaseModel):
    vin: str = ""
    make: str = ""
    model: str = ""
    year: int | None = None
    bill_of_lading: str = ""
    vessel_name: str = ""
    vessel_imo: str = ""
    container_number: str = ""
    origin_port: str = ""
    dest_port: str = "Sohar"
    listing_id: int | None = None
    notes: str = ""


class MilestoneUpdate(BaseModel):
    milestone: str
    status_note: str = ""


class MilestoneOut(BaseModel):
    id: int
    milestone: str
    status_note: str
    occurred_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    filename: str
    extracted: dict[str, Any] = {}
    is_complete: bool
    warnings: list[str] = []
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentCompleteness(BaseModel):
    required: list[str]
    present: list[str]
    missing: list[str]
    warnings: list[str]
    is_ready_for_customs: bool


class ShipmentOut(BaseModel):
    id: int
    tracking_code: str
    user_id: int
    agent_id: int | None
    vin: str
    make: str
    model: str
    year: int | None
    bill_of_lading: str
    vessel_name: str
    vessel_imo: str
    container_number: str
    origin_port: str
    dest_port: str
    current_milestone: str
    eta: datetime | None
    vessel_lat: float | None
    vessel_lon: float | None
    vessel_updated_at: datetime | None
    notes: str
    created_at: datetime
    updated_at: datetime
    milestones: list[MilestoneOut] = []
    documents: list[DocumentOut] = []
    completeness: DocumentCompleteness | None = None

    model_config = {"from_attributes": True}


class AgentAssign(BaseModel):
    agent_id: int


class PhotoVerifyRequest(BaseModel):
    listing_photo_urls: list[str] = []
    notes: str = ""


class PhotoVerifyResult(BaseModel):
    match_score: float
    same_vehicle_likely: bool
    new_damage_detected: bool
    details: str
