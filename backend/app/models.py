from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    BUYER = "buyer"
    AGENT = "agent"
    ADMIN = "admin"
    DEALER = "dealer"


class MilestoneStatus(str, Enum):
    PURCHASED = "purchased"
    EXPORT_YARD = "export_yard"
    ON_VESSEL = "on_vessel"
    ARRIVED_PORT = "arrived_port"
    CUSTOMS = "customs"
    RELEASED = "released"
    DELIVERED = "delivered"


class DocumentType(str, Enum):
    BILL_OF_LADING = "bill_of_lading"
    AUCTION_INVOICE = "auction_invoice"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    INSURANCE = "insurance"
    CUSTOMS_DECLARATION = "customs_declaration"
    OTHER = "other"
    EXPORT_YARD_PHOTO = "export_yard_photo"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default=UserRole.BUYER.value)
    company_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    calculations = relationship("Calculation", back_populates="user")
    watches = relationship("WatchAlert", back_populates="user")
    shipments = relationship("Shipment", back_populates="user", foreign_keys="Shipment.user_id")
    agent_shipments = relationship("Shipment", back_populates="agent", foreign_keys="Shipment.agent_id")


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_source_listing"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)  # copart, iaai, dubizzle_uae, beforward, opensooq
    source_id: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    make: Mapped[str] = mapped_column(String(100), index=True, default="")
    model: Mapped[str] = mapped_column(String(100), index=True, default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage_unit: Mapped[str] = mapped_column(String(10), default="km")
    vin: Mapped[str] = mapped_column(String(50), default="", index=True)
    damage: Mapped[str] = mapped_column(String(255), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    location: Mapped[str] = mapped_column(String(255), default="")
    country: Mapped[str] = mapped_column(String(50), default="")
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    title: Mapped[str] = mapped_column(String(500), default="")
    normalized_make: Mapped[str] = mapped_column(String(100), default="", index=True)
    normalized_model: Mapped[str] = mapped_column(String(100), default="", index=True)
    price_omr: Mapped[float] = mapped_column(Float, default=0.0)
    landed_cost_omr: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("listings.id"), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    price_history = relationship("PriceHistory", back_populates="listing")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    price_omr: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    listing = relationship("Listing", back_populates="price_history")


class FeeTable(Base):
    __tablename__ = "fee_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(255), default="")
    value: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(50), default="OMR")  # OMR, percent, USD
    category: Mapped[str] = mapped_column(String(50), default="general")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ShippingRoute(Base):
    __tablename__ = "shipping_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin_country: Mapped[str] = mapped_column(String(50), index=True)
    origin_port: Mapped[str] = mapped_column(String(100), default="")
    dest_port: Mapped[str] = mapped_column(String(100), default="Sohar")
    mode: Mapped[str] = mapped_column(String(20), default="roro")  # roro, container
    min_usd: Mapped[float] = mapped_column(Float, default=900.0)
    max_usd: Mapped[float] = mapped_column(Float, default=1400.0)
    inland_usd: Mapped[float] = mapped_column(Float, default=200.0)
    transit_days_min: Mapped[int] = mapped_column(Integer, default=25)
    transit_days_max: Mapped[int] = mapped_column(Integer, default=40)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Calculation(Base):
    __tablename__ = "calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    listing_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("listings.id"), nullable=True)
    car_json: Mapped[str] = mapped_column(Text, default="{}")
    breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    total_landed_omr: Mapped[float] = mapped_column(Float, default=0.0)
    local_compare_omr: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str] = mapped_column(String(50), default="")
    savings_omr: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="calculations")


class WatchAlert(Base):
    __tablename__ = "watch_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    make: Mapped[str] = mapped_column(String(100), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    year_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_landed_omr: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="watches")
    notifications = relationship("Notification", back_populates="watch")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    watch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("watch_alerts.id"), nullable=True)
    shipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("shipments.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watch = relationship("WatchAlert", back_populates="notifications")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    agent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    listing_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("listings.id"), nullable=True)
    vin: Mapped[str] = mapped_column(String(50), default="", index=True)
    make: Mapped[str] = mapped_column(String(100), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bill_of_lading: Mapped[str] = mapped_column(String(255), default="")
    vessel_name: Mapped[str] = mapped_column(String(255), default="")
    vessel_imo: Mapped[str] = mapped_column(String(50), default="")
    container_number: Mapped[str] = mapped_column(String(50), default="")
    origin_port: Mapped[str] = mapped_column(String(100), default="")
    dest_port: Mapped[str] = mapped_column(String(100), default="Sohar")
    current_milestone: Mapped[str] = mapped_column(String(50), default=MilestoneStatus.PURCHASED.value)
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vessel_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    vessel_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    vessel_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="shipments", foreign_keys=[user_id])
    agent = relationship("User", back_populates="agent_shipments", foreign_keys=[agent_id])
    milestones = relationship("ShipmentMilestone", back_populates="shipment", cascade="all, delete-orphan")
    documents = relationship("ShipmentDocument", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentMilestone(Base):
    __tablename__ = "shipment_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int] = mapped_column(Integer, ForeignKey("shipments.id"), index=True)
    milestone: Mapped[str] = mapped_column(String(50))
    status_note: Mapped[str] = mapped_column(Text, default="")
    updated_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    shipment = relationship("Shipment", back_populates="milestones")


class ShipmentDocument(Base):
    __tablename__ = "shipment_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int] = mapped_column(Integer, ForeignKey("shipments.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(50), default=DocumentType.OTHER.value)
    filename: Mapped[str] = mapped_column(String(255), default="")
    filepath: Mapped[str] = mapped_column(String(500), default="")
    extracted_json: Mapped[str] = mapped_column(Text, default="{}")
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    shipment = relationship("Shipment", back_populates="documents")
