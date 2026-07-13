"""Document vault OCR extraction, completeness, and photo verification."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models import DocumentType, Shipment, ShipmentDocument
from app.schemas import DocumentCompleteness, PhotoVerifyResult
from app.services.normalize import photo_similarity_score

REQUIRED_DOCS = [
    DocumentType.BILL_OF_LADING.value,
    DocumentType.AUCTION_INVOICE.value,
    DocumentType.CERTIFICATE_OF_ORIGIN.value,
]


async def extract_document_fields(filepath: str, doc_type: str, filename: str) -> dict[str, Any]:
    """Extract fields via LLM vision when available, else filename/text heuristics."""
    settings = get_settings()
    path = Path(filepath)
    suffix = path.suffix.lower()

    # Try OpenAI vision for images
    if settings.openai_api_key and suffix in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
        try:
            result = await _llm_vision_extract(filepath, doc_type)
            if result:
                return result
        except Exception:
            pass

    data: dict[str, Any] = {"doc_type": doc_type, "filename": filename}
    blob = filename.upper()
    if suffix in {".txt", ".csv", ".json", ".md"}:
        try:
            blob += "\n" + path.read_text(encoding="utf-8", errors="ignore").upper()
        except Exception:
            pass

    vin = re.search(r"[A-HJ-NPR-Z0-9]{17}", blob)
    if vin:
        data["vin"] = vin.group(0)
    bol = re.search(r"(?:BL|BOL|B/?L)[-_ ]?[A-Z0-9]{5,}", blob)
    if bol:
        data["bill_of_lading"] = bol.group(0)
    if "INVOICE" in blob:
        data["has_invoice_keyword"] = True
    if "ORIGIN" in blob or "COO" in blob:
        data["has_origin_keyword"] = True
    return data


async def _llm_vision_extract(filepath: str, doc_type: str) -> dict[str, Any] | None:
    import base64

    import httpx

    settings = get_settings()
    path = Path(filepath)
    if path.suffix.lower() == ".pdf":
        # skip binary PDF without rendering in MVP
        return None
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    prompt = (
        f"This is a {doc_type} shipping/import document. Extract JSON fields: "
        "vin, bill_of_lading, invoice_number, invoice_amount, currency, origin_country, "
        "vessel_name, container_number, issue_date, consignee. Use null when unknown."
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)


def build_warnings(shipment: Shipment, extracted: dict[str, Any], doc_type: str) -> list[str]:
    warnings: list[str] = []
    vin = (extracted.get("vin") or "").upper()
    if vin and shipment.vin and vin != shipment.vin.upper():
        warnings.append(f"VIN mismatch: document {vin} vs shipment {shipment.vin}")
    bol = extracted.get("bill_of_lading") or ""
    if bol and shipment.bill_of_lading and bol.replace(" ", "") != shipment.bill_of_lading.replace(" ", ""):
        warnings.append("Bill of lading number does not match shipment record")
    vessel = extracted.get("vessel_name") or ""
    if vessel and shipment.vessel_name and vessel.lower() not in shipment.vessel_name.lower():
        warnings.append(f"Vessel name differs: document '{vessel}' vs '{shipment.vessel_name}'")
    if doc_type == DocumentType.AUCTION_INVOICE.value and not extracted.get("invoice_number") and not extracted.get("has_invoice_keyword"):
        warnings.append("Could not detect invoice number — please verify manually")
    return warnings


def completeness_report(documents: list[ShipmentDocument]) -> DocumentCompleteness:
    present_types = {d.doc_type for d in documents}
    present = [t for t in REQUIRED_DOCS if t in present_types]
    missing = [t for t in REQUIRED_DOCS if t not in present_types]
    warnings: list[str] = []
    for d in documents:
        try:
            warnings.extend(json.loads(d.warnings_json or "[]"))
        except json.JSONDecodeError:
            pass
    return DocumentCompleteness(
        required=REQUIRED_DOCS,
        present=present,
        missing=missing,
        warnings=warnings,
        is_ready_for_customs=len(missing) == 0 and not any("mismatch" in w.lower() for w in warnings),
    )


def verify_photos(listing_urls: list[str], yard_urls: list[str]) -> PhotoVerifyResult:
    score = photo_similarity_score(listing_urls, yard_urls)
    # Without vision model, treat non-empty yard photos as present and score by URL overlap
    same = score >= 0.3 or (listing_urls and yard_urls and score == 0.0 and len(yard_urls) > 0)
    # Heuristic: if we have yard photos but zero overlap with listing URLs, flag possible new set / damage review
    new_damage = bool(yard_urls) and score < 0.15
    details = (
        f"URL overlap score={score:.2f}. "
        + ("Listing and yard photo sets look related. " if same else "Could not confirm photo overlap. ")
        + ("Manual damage review recommended." if new_damage else "No strong new-damage signal from URLs alone.")
    )
    return PhotoVerifyResult(
        match_score=round(score, 3),
        same_vehicle_likely=same or bool(yard_urls),
        new_damage_detected=new_damage,
        details=details,
    )
