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
# Multi-Theme Presets (Easily extended or linked to PostgreSQL)
THEMES = [
    {
        "id": "trend-retro-90s-yearbook",
        "title": "1990s High School Yearbook",
        "category": "Vintage",
        "tagline": "Authentic 1994 vintage yearbook portrait with film grain, soft flash, and blue studio backdrop.",
        "hashtags": ["#90sYearbook", "#VintageAesthetic", "#instaXoom", "#RetroPortraits"],
        "prompt_template": "1990s high school yearbook photo, 35mm film photography, soft direct camera flash lighting, slightly faded vintage colors, textured blue studio portrait backdrop, smiling high school student, authentic 90s hair and collar shirt",
        "preview_image_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-cyberpunk-neon",
        "title": "Cyberpunk 2077 Neon",
        "category": "Sci-Fi",
        "tagline": "Dystopian night city portrait drenched in vivid magenta and cyan neon reflections.",
        "hashtags": ["#Cyberpunk", "#NeonTokyo", "#instaXoom", "#SciFiPortrait"],
        "prompt_template": "cyberpunk portrait, high-tech glowing neon rain-slicked city streets background, dramatic volumetric rim lighting, vivid magenta and cyan reflections, wearing futuristic cybernetic collar and techwear jacket, 8k cinematic film still, detailed reflections",
        "preview_image_url": "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-70s-polaroid",
        "title": "1970s Warm Polaroid",
        "category": "Retro",
        "tagline": "Nostalgic analog snapshot with warm sun-drenched golden tones and subtle light leaks.",
        "hashtags": ["#70sVibe", "#AnalogFilm", "#PolaroidAesthetic", "#instaXoom"],
        "prompt_template": "1970s vintage polaroid snapshot, warm sepia and golden hour daylight, subtle authentic light leak, soft analog film grain, retro 70s casual wardrobe, candid intimate expression, Kodachrome color palette, nostalgic mood",
        "preview_image_url": "https://images.unsplash.com/photo-1509967419530-da38b4704bc6?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-old-money-luxury",
        "title": "Old Money / Quiet Luxury",
        "category": "Editorial",
        "tagline": "Timeless editorial portrait in a Mediterranean villa garden with natural golden sunlight.",
        "hashtags": ["#OldMoney", "#QuietLuxury", "#EditorialPortrait", "#instaXoom"],
        "prompt_template": "editorial luxury portrait in Lake Como villa terrace garden, soft afternoon golden sunlight, natural bokeh cypress trees and lake in background, wearing tailored cream linen blazer, elegant poised expression, Vogue magazine cover aesthetic",
        "preview_image_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-studio-ghibli",
        "title": "Studio Ghibli Anime",
        "category": "Animation",
        "tagline": "Dreamy, hand-painted anime portrait with vibrant skies and whimsical storybook atmosphere.",
        "hashtags": ["#GhibliStyle", "#AnimePortrait", "#ArtisticAesthetic", "#instaXoom"],
        "prompt_template": "masterpiece anime portrait in the whimsical art style of Studio Ghibli, painted watercolor clouds, gentle summer breeze moving hair, warm afternoon light, vibrant hand-drawn aesthetic, high details, Hayao Miyazaki aesthetic",
        "preview_image_url": "https://images.unsplash.com/photo-1563089145-599997674d42?auto=format&fit=crop&w=800&q=80",
    },
]

TODAY_TREND = THEMES[0]

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
    reference_image: Optional[str] = None,
    width: int = 864,
    height: int = 1080,
    seed: Optional[int] = None,
    use_pulid: bool = False,
) -> Dict[str, Any]:
    """
    Constructs the ComfyUI workflow graph for Flux.1 Schnell.
    Optionally attaches PuLID face likeness injection if reference image and models are present.
    """
    if seed is None:
        seed = random.randint(1, 10**14)

    unet_name = settings.FLUX_UNET_NAME
    is_gguf = unet_name.endswith(".gguf")
    is_dev = "dev" in unet_name.lower()

    # Step count and UNet loader resolution
    steps = 20 if is_dev else settings.DEFAULT_STEPS
    unet_node: Dict[str, Any] = {
        "inputs": {"unet_name": unet_name},
        "class_type": "UnetLoaderGGUF" if is_gguf else "UNETLoader"
    }
    if not is_gguf:
        unet_node["inputs"]["weight_dtype"] = "default"

    prompt_graph: Dict[str, Any] = {
        "1": unet_node,
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

    # Model input source (default: base UNet)
    model_source = ["1", 0]

    # Optional PuLID Face Identity Injection
    if use_pulid and reference_image:
        prompt_graph["10"] = {
            "inputs": {
                "image": reference_image,
                "upload": "image"
            },
            "class_type": "LoadImage"
        }
        prompt_graph["11"] = {
            "inputs": {
                "pulid_file": "pulid_flux_v0.9.1.safetensors"
            },
            "class_type": "PulidFluxModelLoader"
        }
        prompt_graph["12"] = {
            "inputs": {
                "provider": "CUDA"
            },
            "class_type": "PulidFluxInsightFaceLoader"
        }
        prompt_graph["13"] = {
            "inputs": {},
            "class_type": "PulidFluxEvaClipLoader"
        }
        prompt_graph["14"] = {
            "inputs": {
                "model": ["1", 0],
                "pulid_flux": ["11", 0],
                "eva_clip": ["13", 0],
                "face_analysis": ["12", 0],
                "image": ["10", 0],
                "weight": 0.85,
                "start_at": 0.0,
                "end_at": 1.0
            },
            "class_type": "ApplyPulidFlux"
        }
        model_source = ["14", 0]

    # Positive conditioning (Flux dev requires FluxGuidance node at 3.5, Schnell uses direct CLIP encode)
    positive_source = ["5", 0]
    if is_dev:
        prompt_graph["15"] = {
            "inputs": {
                "guidance": 3.5,
                "conditioning": ["5", 0]
            },
            "class_type": "FluxGuidance"
        }
        positive_source = ["15", 0]

    prompt_graph["7"] = {
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
            "model": model_source,
            "positive": positive_source,
            "negative": ["6", 0],
            "latent_image": ["4", 0]
        },
        "class_type": "KSampler"
    }

    return prompt_graph


@router.get("/today")
async def get_today_trend(request: Request, x_client_token: Optional[str] = Header(None)):
    """
    Returns today's active platform trend along with full themes catalogue.
    Rate limiting is disabled for local development (unlimited generations).
    """
    return {
        "trend": TODAY_TREND,
        "themes": THEMES,
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
    prompt: Optional[str] = Form(None),
    theme_id: Optional[str] = Form("trend-retro-90s-yearbook"),
    x_client_token: Optional[str] = Header(None),
):
    """
    Accepts 1 to 5 user photos, executes the ComfyUI inference workflow,
    and returns the URL of the generated 4:5 Instagram portrait.
    Supports real-time edited custom prompts and multi-theme selection.
    """
    # 1. Validate photos
    if not (1 <= len(photos) <= 5):
        raise HTTPException(
            status_code=400,
            detail="Please upload between 1 and 5 photos for face conditioning."
        )

    client_id = get_client_fingerprint(request, x_client_token)

    # 2. Save uploaded photos to shared uploads directory (visible to ComfyUI as /app/ComfyUI/input)
    upload_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    saved_filenames = []

    for photo in photos:
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        unique_name = f"user_{uuid.uuid4().hex[:12]}{ext}"
        dest_path = os.path.join(upload_dir, unique_name)
        async with aiofiles.open(dest_path, "wb") as buffer:
            content = await photo.read()
            await buffer.write(content)
        saved_filenames.append(unique_name)

    # 3. Resolve aspect ratio (default locked to 4:5)
    width, height = (864, 1080)
    if aspect_ratio == "4:5":
        width, height = (864, 1080)

    # 4. Resolve prompt: User-edited prompt takes precedence, falls back to selected theme template
    selected_theme = next((t for t in THEMES if t["id"] == theme_id), TODAY_TREND)

    if prompt and prompt.strip():
        final_prompt = prompt.strip()
    else:
        final_prompt = selected_theme["prompt_template"]

    if custom_caption and custom_caption.strip() and custom_caption.strip() not in final_prompt:
        final_prompt = f"{final_prompt}, {custom_caption.strip()}"

    primary_ref_image = saved_filenames[0] if saved_filenames else None

    # 5. Build ComfyUI workflow graph (attempting PuLID first, falling back to base if weights absent)
    workflow_prompt = build_workflow_prompt(
        positive_prompt=final_prompt,
        reference_image=primary_ref_image,
        width=width,
        height=height,
        use_pulid=True if primary_ref_image else False,
    )

    # 6. Dispatch job to ComfyUI and await completion
    job_id = str(uuid.uuid4())
    try:
        try:
            prompt_id = await comfy_client.queue_prompt(workflow_prompt, client_id=job_id)
        except Exception as queue_err:
            # If PuLID node is missing on server, automatically fallback to base UNet graph
            print(f"[Notice] PuLID node dispatch notice ({queue_err}). Retrying with baseline diffusion...")
            fallback_prompt = build_workflow_prompt(
                positive_prompt=final_prompt,
                reference_image=None,
                width=width,
                height=height,
                use_pulid=False,
            )
            prompt_id = await comfy_client.queue_prompt(fallback_prompt, client_id=job_id)

        history = await comfy_client.wait_for_completion(prompt_id, client_id=job_id, timeout_seconds=120.0)
        output_filename = comfy_client.extract_output_filename(history)

        if not output_filename:
            raise RuntimeError(f"ComfyUI completed prompt {prompt_id} but returned no output image.")

        image_url = f"/api/trends/outputs/{output_filename}"

        return {
            "status": "completed",
            "job_id": job_id,
            "prompt_id": prompt_id,
            "theme_id": selected_theme["id"],
            "theme_title": selected_theme["title"],
            "prompt_used": final_prompt,
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
