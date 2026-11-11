"""Image-upload endpoint for the real Vision damage classifier."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ..services.damage_vision import VisionServiceError, assess_damage


router = APIRouter(prefix="/api/vision", tags=["vision"])
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class DamageAssessmentOut(BaseModel):
    grade: str = Field(pattern="^[SABC]$")
    damage_summary: str
    visible_evidence: list[str]
    confidence: float = Field(ge=0, le=1)
    needs_manual_review: bool
    provider: str = "gemini"


@router.post("/damage-assessment", response_model=DamageAssessmentOut)
async def damage_assessment(image: UploadFile = File(...)):
    """Upload a JPEG/PNG/WebP return photo and receive a four-level damage grade."""
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "JPEG, PNG, or WebP images only.")
    raw = await image.read(MAX_IMAGE_BYTES + 1)
    if not raw:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Image file is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image must be 10 MB or smaller.")
    try:
        result = await assess_damage(raw, image.content_type)
    except VisionServiceError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return DamageAssessmentOut(**result)
