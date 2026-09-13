import os
import random
import uuid
import aiofiles
import httpx
from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

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

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs")


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


def build_workflow_prompt(
    positive_prompt: str,
    width: int = 864,
    height: int = 1080,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """
    Constructs the validated ComfyUI GGUF workflow graph for Flux.1 Schnell.
    """
    if seed is None:
        seed = random.randint(1, 10**14)

    return {
        "1": {
            "inputs": {
                "unet_name": "flux1-schnell-Q4_K_S.gguf"
            },
            "class_type": "UnetLoaderGGUF"
        },
        "2": {
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            },
            "class_type": "DualCLIPLoader"
        },
        "3": {
            "inputs": {
                "vae_name": "ae.safetensors"
            },
            "class_type": "VAELoader"
        },
        "4": {
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "5": {
            "inputs": {
                "text": positive_prompt,
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "6": {
            "inputs": {
                "text": "blurry, low quality, distorted face, bad anatomy, modern smartphone photo, deformed",
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "7": {
            "inputs": {
                "seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["4", 0]
            },
            "class_type": "KSampler"
        },
        "8": {
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0]
            },
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {
                "filename_prefix": "instaXoom_trend_4x5",
                "images": ["8", 0]
            },
            "class_type": "SaveImage"
        }
    }


@router.get("/today")
async def get_today_trend(request: Request, x_client_token: Optional[str] = Header(None)):
    """
    Returns today's active platform trend.
    Rate limiting is disabled for local development (unlimited generations).
    """
    return {
        "trend": TODAY_TREND,
        "quota": {
            "remaining_generations": 999,
            "reset_in_seconds": 86400,
            "limit_per_day": "unlimited",
            "rate_limit_enabled": False,
        }
    }


@router.get("/quota")
async def check_quota(request: Request, x_client_token: Optional[str] = Header(None)):
    """
    Checks remaining generations for the client.
    Rate limiting is disabled for local development (unlimited generations).
    """
    client_id = get_client_fingerprint(request, x_client_token)
    return {
        "client_id": client_id,
        "remaining_generations": 999,
        "reset_in_seconds": 86400,
        "limit_per_day": "unlimited",
        "rate_limit_enabled": False,
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
    Accepts 1 to 5 user photos, executes the ComfyUI inference workflow,
    and returns the URL of the generated 4:5 Instagram portrait.
    Rate limiting is bypassed for local development.
    """
    # 1. Validate photos
    if not (1 <= len(photos) <= 5):
        raise HTTPException(
            status_code=400,
            detail="Please upload between 1 and 5 photos for face conditioning."
        )

    client_id = get_client_fingerprint(request, x_client_token)

    # 2. Save uploaded photos to temporary / shared storage
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

    # 3. Resolve aspect ratio (default locked to 4:5)
    width, height = (864, 1080)
    if aspect_ratio == "4:5":
        width, height = (864, 1080)

    # 4. Construct prompt from Daily Trend template
    prompt_text = TODAY_TREND["prompt_template"]
    if custom_caption and custom_caption.strip():
        prompt_text = f"{prompt_text}, {custom_caption.strip()}"

    workflow_prompt = build_workflow_prompt(
        positive_prompt=prompt_text,
        width=width,
        height=height,
    )

    # 5. Dispatch job to ComfyUI and await completion
    job_id = str(uuid.uuid4())
    try:
        prompt_id = await comfy_client.queue_prompt(workflow_prompt, client_id=job_id)
        history = await comfy_client.wait_for_completion(prompt_id, client_id=job_id, timeout_seconds=120.0)
        output_filename = comfy_client.extract_output_filename(history)

        if not output_filename:
            raise RuntimeError(f"ComfyUI completed prompt {prompt_id} but returned no output image.")

        image_url = f"/api/trends/outputs/{output_filename}"

        return {
            "status": "completed",
            "job_id": job_id,
            "prompt_id": prompt_id,
            "trend_id": TODAY_TREND["id"],
            "aspect_ratio": "4:5",
            "dimensions": {"width": width, "height": height},
            "photos_received": len(saved_filenames),
            "image_url": image_url,
            "quota": {
                "remaining_generations": 999,
                "reset_in_seconds": 86400,
                "rate_limit_enabled": False,
            },
            "message": "Successfully generated 4:5 Instagram trend portrait."
        }

    except Exception as exc:
        print(f"[Generate Error] Inference failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Image generation failed: {str(exc)}"
        )


@router.api_route("/outputs/{filename}", methods=["GET", "HEAD"])
async def get_generated_image(filename: str):
    """
    Serves generated images from the shared outputs volume or proxies from ComfyUI.
    """
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(OUTPUTS_DIR, safe_filename)

    # Direct file serving if available in mounted volume
    if os.path.isfile(filepath):
        return FileResponse(filepath, media_type="image/png")

    # Fallback: proxy from ComfyUI /view endpoint
    comfy_view_url = f"{settings.COMFYUI_URL}/view?filename={safe_filename}&type=output"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(comfy_view_url)
            if resp.status_code == 200:
                return Response(content=resp.content, media_type="image/png")
        except Exception as err:
            print(f"[Outputs Proxy Error] Failed to proxy {safe_filename} from ComfyUI: {err}")

    raise HTTPException(status_code=404, detail="Generated image not found.")
