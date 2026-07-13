import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user, require_roles
from app.config import get_settings
from app.database import get_db
from app.models import DocumentType, MilestoneStatus, Shipment, ShipmentDocument, User
from app.schemas import (
    DocumentCompleteness,
    DocumentOut,
    MilestoneUpdate,
    PhotoVerifyRequest,
    PhotoVerifyResult,
    ShipmentCreate,
    ShipmentOut,
)
from app.services.documents import build_warnings, completeness_report, extract_document_fields, verify_photos
from app.services.tracking import add_milestone, generate_tracking_code, refresh_vessel_position

router = APIRouter(prefix="/api/shipments", tags=["shipments"])
settings = get_settings()


def _doc_out(d: ShipmentDocument) -> DocumentOut:
    try:
        extracted = json.loads(d.extracted_json or "{}")
    except json.JSONDecodeError:
        extracted = {}
    try:
        warnings = json.loads(d.warnings_json or "[]")
    except json.JSONDecodeError:
        warnings = []
    return DocumentOut(
        id=d.id,
        doc_type=d.doc_type,
        filename=d.filename,
        extracted=extracted,
        is_complete=d.is_complete,
        warnings=warnings,
        uploaded_at=d.uploaded_at,
    )


def _shipment_out(s: Shipment) -> ShipmentOut:
    docs = [_doc_out(d) for d in (s.documents or [])]
    return ShipmentOut(
        id=s.id,
        tracking_code=s.tracking_code,
        user_id=s.user_id,
        agent_id=s.agent_id,
        vin=s.vin,
        make=s.make,
        model=s.model,
        year=s.year,
        bill_of_lading=s.bill_of_lading,
        vessel_name=s.vessel_name,
        vessel_imo=s.vessel_imo,
        container_number=s.container_number,
        origin_port=s.origin_port,
        dest_port=s.dest_port,
        current_milestone=s.current_milestone,
        eta=s.eta,
        vessel_lat=s.vessel_lat,
        vessel_lon=s.vessel_lon,
        vessel_updated_at=s.vessel_updated_at,
        notes=s.notes,
        created_at=s.created_at,
        updated_at=s.updated_at,
        milestones=list(s.milestones or []),
        documents=docs,
        completeness=completeness_report(list(s.documents or [])),
    )


async def _load_shipment(db: AsyncSession, shipment_id: int) -> Shipment | None:
    result = await db.execute(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
    )
    return result.scalar_one_or_none()


@router.post("", response_model=ShipmentOut)
async def create_shipment(
    payload: ShipmentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = Shipment(
        tracking_code=generate_tracking_code(),
        user_id=user.id,
        vin=payload.vin.upper(),
        make=payload.make,
        model=payload.model,
        year=payload.year,
        bill_of_lading=payload.bill_of_lading,
        vessel_name=payload.vessel_name,
        vessel_imo=payload.vessel_imo,
        container_number=payload.container_number,
        origin_port=payload.origin_port,
        dest_port=payload.dest_port or "Sohar",
        listing_id=payload.listing_id,
        notes=payload.notes,
        current_milestone=MilestoneStatus.PURCHASED.value,
    )
    db.add(s)
    await db.flush()
    await add_milestone(db, s, MilestoneStatus.PURCHASED.value, "Shipment created", user.id)
    await db.commit()
    s = await _load_shipment(db, s.id)
    return _shipment_out(s)


@router.get("", response_model=list[ShipmentOut])
async def my_shipments(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Shipment)
        .where(Shipment.user_id == user.id)
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
        .order_by(Shipment.id.desc())
    )
    return [_shipment_out(s) for s in result.scalars().all()]


@router.get("/track/{tracking_code}", response_model=ShipmentOut)
async def track_public(tracking_code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Shipment)
        .where(Shipment.tracking_code == tracking_code.upper())
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Tracking code not found")
    await refresh_vessel_position(db, s)
    await db.commit()
    s = await _load_shipment(db, s.id)
    return _shipment_out(s)


@router.get("/{shipment_id}", response_model=ShipmentOut)
async def get_shipment(shipment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    s = await _load_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if s.user_id != user.id and s.agent_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    await refresh_vessel_position(db, s)
    await db.commit()
    s = await _load_shipment(db, shipment_id)
    return _shipment_out(s)


@router.post("/{shipment_id}/milestones", response_model=ShipmentOut)
async def update_milestone(
    shipment_id: int,
    payload: MilestoneUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _load_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if s.user_id != user.id and s.agent_id != user.id and user.role not in {"admin", "agent"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        await add_milestone(db, s, payload.milestone, payload.status_note, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.milestone == MilestoneStatus.ON_VESSEL.value:
        await refresh_vessel_position(db, s)
    await db.commit()
    s = await _load_shipment(db, shipment_id)
    return _shipment_out(s)


@router.post("/{shipment_id}/documents", response_model=DocumentOut)
async def upload_document(
    shipment_id: int,
    doc_type: str = Form(DocumentType.OTHER.value),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _load_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if s.user_id != user.id and s.agent_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    upload_root = Path(settings.upload_dir) / f"shipment_{shipment_id}"
    upload_root.mkdir(parents=True, exist_ok=True)
    dest = upload_root / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    extracted = await extract_document_fields(str(dest), doc_type, file.filename)
    warnings = build_warnings(s, extracted, doc_type)
    # sync useful fields onto shipment if empty
    if extracted.get("vin") and not s.vin:
        s.vin = extracted["vin"]
    if extracted.get("bill_of_lading") and not s.bill_of_lading:
        s.bill_of_lading = extracted["bill_of_lading"]
    if extracted.get("vessel_name") and not s.vessel_name:
        s.vessel_name = extracted["vessel_name"]

    doc = ShipmentDocument(
        shipment_id=shipment_id,
        doc_type=doc_type,
        filename=file.filename,
        filepath=str(dest),
        extracted_json=json.dumps(extracted),
        is_complete=True,
        warnings_json=json.dumps(warnings),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _doc_out(doc)


@router.get("/{shipment_id}/completeness", response_model=DocumentCompleteness)
async def get_completeness(shipment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    s = await _load_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if s.user_id != user.id and s.agent_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return completeness_report(list(s.documents or []))


@router.post("/{shipment_id}/verify-photos", response_model=PhotoVerifyResult)
async def verify_export_photos(
    shipment_id: int,
    payload: PhotoVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _load_shipment(db, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    yard_urls = []
    for d in s.documents or []:
        if d.doc_type == DocumentType.EXPORT_YARD_PHOTO.value:
            yard_urls.append(d.filepath)
    return verify_photos(payload.listing_photo_urls, yard_urls)
