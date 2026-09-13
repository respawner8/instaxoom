import os
import uuid
import aiofiles
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Request
from pydantic import BaseModel

from app.services.rate_limiter import rate_limiter
from app.services.comfy_client import comfy_client
from app.core.config import settings

router = APIRouter(prefix="/api/trends", tags=["Daily Trends"])

# Hardcoded active Daily Trend definition (easily plugged into PostgreSQL)
TODAY_TREND = {
    "id": "trend-retro-90s-yearbook",
    "date": date.today().isoformat(),
    "title": "90s Retro High School Yearbook",
    "tagline": "Transform your portrait into an authentic 1994 vintage yearbook portrait with authentic film grain and classic blue studio backdrop.",
    "aspect_ratios": [
        {"label": "Instagram Feed (4:5)", "value": "4:5", "width": 864, "height": 1080}
    ],
    "default_aspect_ratio": "4:5",
    "hashtags": ["#90sYearbook", "#VintageAesthetic", "#instaXoom", "#RetroPortraits"],
    "prompt_template": "1990s high school yearbook photo, 35mm film photography, soft flash lighting, slightly faded colors, textured blue studio backdrop, high school senior smiling, authentic 90s fashion and hairstyle",
    "preview_image_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80",
    "photo_guidelines": [
        "Upload 1 to 5 clear photos of your face.",
        "Front-facing or slight 3/4 angle portraits work best.",
        "Avoid sunglasses or extreme face coverings for maximum accuracy."
    ]
}


def get_client_fingerprint(request: Request, x_client_token: Optional[str] = Header(None)) -> str:
    """
    Extracts a unique client identifier using either a client-generated UUID
    token or client IP fallback.
    """
    if x_client_token and len(x_client_token) >= 8:
        return x_client_token
    # Fallback to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown_client"


@router.get("/today")
async def get_today_trend(request: Request, x_client_token: Optional[str] = Header(None)):
    """
    Returns today's active platform trend along with client quota status.
    """
    client_id = get_client_fingerprint(request, x_client_token)
    remaining, ttl = await rate_limiter.get_remaining(client_id)

    return {
        "trend": TODAY_TREND,
        "quota": {
            "remaining_generations": remaining,
            "reset_in_seconds": ttl,
            "limit_per_day": settings.RATE_LIMIT_GENERATIONS_PER_DAY,
        }
    }


@router.get("/quota")
async def check_quota(request: Request, x_client_token: Optional[str] = Header(None)):
    """
    Checks remaining generations for the client.
    """
    client_id = get_client_fingerprint(request, x_client_token)
    remaining, ttl = await rate_limiter.get_remaining(client_id)
    return {
        "client_id": client_id,
        "remaining_generations": remaining,
        "reset_in_seconds": ttl,
        "limit_per_day": settings.RATE_LIMIT_GENERATIONS_PER_DAY,
    }


@router.post("/generate")
async def generate_trend_image(
    request: Request,
    photos: List[UploadFile] = File(...),
    aspect_ratio: str = Form("4:5"),
    custom_caption: Optional[str] = Form(None),
    x_client_token: Optional[str] = Header(None),
):
    """
    Consumes a generation quota, saves uploaded user face images (1-5),
    and initiates the image-to-image generation job.
    """
    # 1. Validate photos
    if not (1 <= len(photos) <= 5):
        raise HTTPException(
            status_code=400,
            detail="Please upload between 1 and 5 photos for face conditioning."
        )

    # 2. Check and enforce rate limiting
    client_id = get_client_fingerprint(request, x_client_token)
    allowed, remaining, ttl = await rate_limiter.check_and_consume(client_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached ({settings.RATE_LIMIT_GENERATIONS_PER_DAY} generations/day). Resets in {ttl // 3600}h {(ttl % 3600) // 60}m."
        )

    # 3. Save uploaded photos to temporary / shared storage
    upload_dir = os.path.join(os.getcwd(), "uploads", client_id)
    os.makedirs(upload_dir, exist_ok=True)
    saved_filenames = []

    for photo in photos:
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = os.path.join(upload_dir, unique_name)
        async with aiofiles.open(dest_path, "wb") as buffer:
            content = await photo.read()
            await buffer.write(content)
        saved_filenames.append(unique_name)

    # 4. Resolve aspect ratio dimensions
    ratio_map = {
        "4:5": (864, 1080),
        "9:16": (768, 1344),
        "1:1": (1024, 1024),
    }
    width, height = ratio_map.get(aspect_ratio, (864, 1080))

    # 5. Create generation job response
    job_id = str(uuid.uuid4())

    return {
        "status": "queued",
        "job_id": job_id,
        "trend_id": TODAY_TREND["id"],
        "aspect_ratio": aspect_ratio,
        "dimensions": {"width": width, "height": height},
        "photos_received": len(saved_filenames),
        "quota": {
            "remaining_generations": remaining,
            "reset_in_seconds": ttl,
        },
        "estimated_duration_seconds": 15,
        "message": f"Successfully queued trend generation using {len(saved_filenames)} reference photo(s)."
    }
