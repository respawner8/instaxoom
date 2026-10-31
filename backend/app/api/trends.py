import asyncio
import json
import os
import random
import uuid
import aiofiles
import httpx
from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, desc

from app.services.comfy_client import comfy_client
from app.services.azure_image_client import azure_image_client
from app.services.storage_service import storage_service
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.api.deps import get_current_user, get_current_user_optional
from app.models.user import User, UserCredit, CreditTransaction, Generation, ThemePreset
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from app.core.app_metrics import (
    generation_attempts,
    generation_success,
    generation_failure,
    credit_deductions,
    credit_rejections,
    revenue_integrity_anomalies,
)

tracer = trace.get_tracer("instaxoom.trends")

router = APIRouter(prefix="/api/trends", tags=["Daily Trends"])


# Hardcoded active Daily Trend definition (easily plugged into PostgreSQL)
# Multi-Theme Presets (Easily extended or linked to PostgreSQL)
THEMES = [
    {
        "id": "trend-perfect-headshot",
        "title": "Perfect Headshot",
        "category": "Professional",
        "tagline": "Crisp, studio-quality corporate headshot with flattering studio lighting and sharp executive attire.",
        "hashtags": ["#ProfessionalHeadshot", "#LinkedInPhoto", "#ExecutivePortrait", "#CreatorBot"],
        "prompt_template": "ultra-sharp professional executive headshot portrait, crisp studio lighting, subtle softbox key light and rim light, blurred modern architectural office studio background, wearing tailored executive blazer, confident friendly approachable expression, natural skin texture, 85mm portrait lens, 8k professional studio photography",
        "preview_image_url": "https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-auto-enhance",
        "title": "Auto Photo Enhance",
        "category": "Studio Polish",
        "tagline": "Intelligently rebalance color, exposure, brightness, contrast, and clarity to make your photo look its absolute best.",
        "hashtags": ["#PhotoEnhance", "#AutoRetouch", "#ColorGrading", "#CreatorBot"],
        "prompt_template": "masterpiece studio-grade portrait remaster and auto-enhancement of the subject, perfectly balanced exposure, dynamic contrast correction, rich true-to-life color grading, crystal clear sharpness, subtle flattering studio fill lighting, natural skin tones and texture, clean high-definition photographic polish",
        "preview_image_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-retro-90s-yearbook",
        "title": "1990s Yearbook",
        "category": "Vintage",
        "tagline": "Authentic 1994 vintage yearbook portrait with film grain, soft flash, and blue studio backdrop.",
        "hashtags": ["#90sYearbook", "#VintageAesthetic", "#CreatorBot", "#RetroPortraits"],
        "prompt_template": "1990s retro vintage yearbook portrait, 35mm film photography, soft direct camera flash lighting, slightly faded vintage colors, textured blue studio portrait backdrop, smiling adult subject, authentic 90s hair and collar shirt",
        "preview_image_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-cyberpunk-neon",
        "title": "Cyberpunk 2077",
        "category": "Sci-Fi",
        "tagline": "Dystopian night city portrait drenched in vivid magenta and cyan neon reflections.",
        "hashtags": ["#Cyberpunk", "#NeonTokyo", "#CreatorBot", "#SciFiPortrait"],
        "prompt_template": "cyberpunk portrait, high-tech glowing neon rain-slicked city streets background, dramatic volumetric rim lighting, vivid magenta and cyan reflections, wearing futuristic cybernetic collar and techwear jacket, 8k cinematic film still, detailed reflections",
        "preview_image_url": "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-70s-polaroid",
        "title": "1970s Polaroid",
        "category": "Retro",
        "tagline": "Nostalgic analog snapshot with warm sun-drenched golden tones and subtle light leaks.",
        "hashtags": ["#70sVibe", "#AnalogFilm", "#PolaroidAesthetic", "#CreatorBot"],
        "prompt_template": "1970s vintage polaroid snapshot, warm sepia and golden hour daylight, subtle authentic light leak, soft analog film grain, retro 70s casual wardrobe, candid intimate expression, Kodachrome color palette, nostalgic mood",
        "preview_image_url": "https://images.unsplash.com/photo-1509967419530-da38b4704bc6?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-old-money-luxury",
        "title": "Old Money Luxury",
        "category": "Editorial",
        "tagline": "Timeless editorial portrait in a Mediterranean villa garden with natural golden sunlight.",
        "hashtags": ["#OldMoney", "#QuietLuxury", "#EditorialPortrait", "#CreatorBot"],
        "prompt_template": "editorial luxury portrait in Lake Como villa terrace garden, soft afternoon golden sunlight, natural bokeh cypress trees and lake in background, wearing tailored cream linen blazer, elegant poised expression, Vogue magazine cover aesthetic",
        "preview_image_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=800&q=80",
    },
    {
        "id": "trend-studio-ghibli",
        "title": "Studio Ghibli",
        "category": "Animation",
        "tagline": "Dreamy, hand-painted anime portrait with vibrant skies and whimsical storybook atmosphere.",
        "hashtags": ["#GhibliStyle", "#AnimePortrait", "#ArtisticAesthetic", "#CreatorBot"],
        "prompt_template": "masterpiece anime portrait in the whimsical art style of Studio Ghibli, painted watercolor clouds, gentle summer breeze moving hair, warm afternoon light, vibrant hand-drawn aesthetic, high details, Hayao Miyazaki aesthetic",
        "preview_image_url": "https://images.unsplash.com/photo-1563089145-599997674d42?auto=format&fit=crop&w=800&q=80",
    },
]

TODAY_TREND = THEMES[0]


async def get_active_themes() -> List[Dict[str, Any]]:
    """
    Returns active themes from PostgreSQL, falling back to static THEMES
    if database is empty or unavailable.
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ThemePreset)
                .where(ThemePreset.is_active == True)
                .order_by(ThemePreset.order_index, ThemePreset.created_at)
            )
            res = await session.execute(stmt)
            db_themes = res.scalars().all()
            if db_themes:
                return [
                    {
                        "id": t.id,
                        "title": t.title,
                        "category": t.category,
                        "tagline": t.tagline,
                        "hashtags": t.hashtags or [],
                        "prompt_template": t.prompt_template,
                        "preview_image_url": t.preview_image_url,
                    }
                    for t in db_themes
                ]
    except Exception:
        pass
    return THEMES


async def resolve_theme(theme_id: Optional[str]) -> Dict[str, Any]:
    """
    Resolves the theme specification by ID from DB or static THEMES,
    falling back to today's active trend.
    """
    if theme_id:
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(ThemePreset).where(
                    ThemePreset.id == theme_id,
                    ThemePreset.is_active == True,
                )
                res = await session.execute(stmt)
                db_t = res.scalar_one_or_none()
                if db_t:
                    return {
                        "id": db_t.id,
                        "title": db_t.title,
                        "category": db_t.category,
                        "tagline": db_t.tagline,
                        "hashtags": db_t.hashtags or [],
                        "prompt_template": db_t.prompt_template,
                        "preview_image_url": db_t.preview_image_url,
                    }
        except Exception:
            pass

        matched = next((t for t in THEMES if t["id"] == theme_id), None)
        if matched:
            return matched

    active = await get_active_themes()
    return active[0] if active else TODAY_TREND


OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs")
generation_lock = asyncio.Lock()


async def generation_capacity():
    if not settings.SINGLE_GENERATION_AT_A_TIME:
        yield
        return
    if generation_lock.locked():
        raise HTTPException(
            status_code=429,
            detail="The image generator is busy. Please try again shortly.",
            headers={"Retry-After": "30"},
        )
    async with generation_lock:
        yield


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


def apply_gender_to_prompt(prompt: str, gender: Optional[str]) -> str:
    """
    Injects clear gender-anchoring tokens to ensure FLUX does not default
    to generating a female portrait when a male subject is provided.
    """
    if not gender:
        return prompt

    clean_gender = gender.strip().lower()
    if clean_gender not in ("male", "female"):
        return prompt

    if clean_gender == "male":
        # Check if already specified in the prompt
        if any(term in prompt.lower() for term in [" male", " man ", " gentleman"]):
            return prompt
        return f"portrait of a handsome man, male subject, {prompt}"

    elif clean_gender == "female":
        if any(term in prompt.lower() for term in [" female", " woman ", " lady"]):
            return prompt
        return f"portrait of an elegant woman, female subject, {prompt}"

    return prompt


def build_workflow_prompt(
    positive_prompt: str,
    reference_image: Optional[str] = None,
    width: int = 864,
    height: int = 1080,
    seed: Optional[int] = None,
    use_pulid: bool = False,
    reference_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Constructs the ComfyUI workflow graph for Flux.1 Schnell / Dev.
    Optionally attaches PuLID face likeness injection. If multiple reference images
    are supplied, combines them using ComfyUI native ImageBatch nodes to pool face vectors.
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

    # Resolve list of reference images (supporting both single and multiple photos)
    if reference_images is not None:
        images_list = [img for img in reference_images if img]
    elif reference_image:
        images_list = [reference_image]
    else:
        images_list = []

    # Optional PuLID Face Identity Injection
    if use_pulid and images_list:
        prompt_graph["11"] = {
            "inputs": {
                "pulid_file": "pulid_flux_v0.9.1.safetensors"
            },
            "class_type": "PulidFluxModelLoader"
        }
        prompt_graph["12"] = {
            "inputs": {
                "provider": settings.PULID_PROVIDER
            },
            "class_type": "PulidFluxInsightFaceLoader"
        }
        prompt_graph["13"] = {
            "inputs": {},
            "class_type": "PulidFluxEvaClipLoader"
        }

        # Single image vs Multi-image batching
        if len(images_list) == 1:
            prompt_graph["10"] = {
                "inputs": {
                    "image": images_list[0],
                    "upload": "image"
                },
                "class_type": "LoadImage"
            }
            pulid_image_source = ["10", 0]
        else:
            # Multi-image: create LoadImage node for each photo
            for idx, img_name in enumerate(images_list):
                node_id = f"10_{idx}"
                prompt_graph[node_id] = {
                    "inputs": {
                        "image": img_name,
                        "upload": "image"
                    },
                    "class_type": "LoadImage"
                }

            # Chain ImageBatch nodes to create a pooled batch tensor [B, H, W, C]
            prompt_graph["20_0"] = {
                "inputs": {
                    "image1": ["10_0", 0],
                    "image2": ["10_1", 0]
                },
                "class_type": "ImageBatch"
            }
            last_batch_node = "20_0"
            for idx in range(2, len(images_list)):
                batch_node_id = f"20_{idx - 1}"
                prompt_graph[batch_node_id] = {
                    "inputs": {
                        "image1": [last_batch_node, 0],
                        "image2": [f"10_{idx}", 0]
                    },
                    "class_type": "ImageBatch"
                }
                last_batch_node = batch_node_id

            pulid_image_source = [last_batch_node, 0]

        prompt_graph["14"] = {
            "inputs": {
                "model": ["1", 0],
                "pulid_flux": ["11", 0],
                "eva_clip": ["13", 0],
                "face_analysis": ["12", 0],
                "image": pulid_image_source,
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


@router.get("/queue-status")
async def get_queue_status():
    """
    Returns live queue metrics and estimated wait time for new requests.
    """
    if settings.ENGINE == "azure":
        return azure_image_client.get_queue_status()
    return {
        "active_jobs": 0,
        "waiting_jobs": 0,
        "total_in_queue": 0,
        "active_workers": 0,
        "estimated_wait_seconds": 0,
        "status_text": "Ready (Local GPU)",
    }


@router.get("/today")
async def get_today_trend(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_client_token: Optional[str] = Header(None)
):
    """
    Returns today's active platform trend along with full themes catalogue and active engine metadata.
    """
    credits = current_user.credit.balance if (current_user and current_user.credit) else 0
    active_themes = await get_active_themes()
    primary_trend = active_themes[0] if active_themes else TODAY_TREND
    return {
        "trend": primary_trend,
        "themes": active_themes,
        "engine": settings.ENGINE,
        "engine_name": "Cloud Studio" if settings.ENGINE == "azure" else "Local GPU Studio",
        "max_photos": 1 if settings.ENGINE == "azure" else 5,
        "queue_enabled": True if settings.ENGINE == "azure" else False,
        "quota": {
            "remaining_generations": credits if current_user else 0,
            "reset_in_seconds": 86400,
            "limit_per_day": "credits",
            "rate_limit_enabled": False,
        },
        "user_credits": credits if current_user else None,
    }


@router.get("/quota")
async def check_quota(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_client_token: Optional[str] = Header(None)
):
    """
    Checks remaining generations / credits for the client.
    """
    client_id = get_client_fingerprint(request, x_client_token)
    credits = current_user.credit.balance if (current_user and current_user.credit) else 0
    return {
        "client_id": client_id,
        "remaining_generations": credits,
        "user_credits": credits,
        "reset_in_seconds": 86400,
        "limit_per_day": "credits",
        "rate_limit_enabled": False,
    }


@router.post("/generate", dependencies=[Depends(generation_capacity)])
async def generate_trend_image(
    request: Request,
    photos: List[UploadFile] = File(...),
    aspect_ratio: str = Form("4:5"),
    custom_caption: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    theme_id: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    engine: Optional[str] = Form(None),
    stream: Optional[bool] = Form(False),
    x_client_token: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts user photo(s), verifies user credit balance (requires >= 1 credit),
    executes the inference workflow via either local FLUX.1 (ComfyUI + PuLID)
    or cloud Azure AI Foundry (Cloud Studio), deducts 1 credit upon success,
    and returns the URL of the generated 4:5 Instagram portrait.
    Supports real-time SSE streaming for live queue position and countdown tracking.
    """
    active_engine = (engine or settings.ENGINE).lower()
    selected_theme = await resolve_theme(theme_id)

    if not current_user.credit or current_user.credit.balance < 1:
        credit_rejections.add(1, {"user_role": current_user.role, "theme_id": selected_theme["id"]})
        generation_failure.add(1, {"engine": active_engine, "error_type": "insufficient_credits"})
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. You need at least 1 credit to generate an image. Please contact an admin for trial credits.",
        )

    generation_attempts.add(1, {"engine": active_engine, "theme_id": selected_theme["id"]})

    async def deduct_user_credit(
        job_id_val: str,
        theme_id_val: str,
        image_url_val: str = "",
        thumbnail_url_val: Optional[str] = None,
        input_image_url_val: Optional[str] = None,
    ) -> int:
        with tracer.start_as_current_span("credit.deduct") as span:
            span.set_attribute("user.id", str(current_user.id))
            span.set_attribute("credit.job_id", job_id_val)
            span.set_attribute("credit.theme_id", theme_id_val)
            async with AsyncSessionLocal() as session:
                stmt = select(UserCredit).where(UserCredit.user_id == current_user.id)
                res = await session.execute(stmt)
                credit_rec = res.scalar_one_or_none()
                if not credit_rec or credit_rec.balance < 1:
                    span.set_status(Status(StatusCode.ERROR, "Insufficient credits"))
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail="Insufficient credits. You need at least 1 credit to generate a portrait.",
                    )
                credit_rec.balance -= 1
                new_balance = credit_rec.balance
                span.set_attribute("credit.balance_before", new_balance + 1)
                span.set_attribute("credit.balance_after", new_balance)
                tx = CreditTransaction(
                    user_id=current_user.id,
                    amount=-1,
                    balance_after=new_balance,
                    action="generation",
                    description=f"Generated portrait ({selected_theme.get('title', 'theme')})",
                    meta_data={"job_id": job_id_val, "theme_id": theme_id_val},
                )
                session.add(tx)

                # Persist image generation record for user's gallery
                if image_url_val:
                    storage_prov = "azure_blob" if image_url_val.startswith("http") else "local"
                    gen_rec = Generation(
                        user_id=current_user.id,
                        job_id=job_id_val,
                        theme_id=theme_id_val,
                        theme_title=selected_theme.get("title", "Portrait"),
                        prompt=final_prompt,
                        aspect_ratio="4:5",
                        engine=active_engine,
                        image_url=image_url_val,
                        thumbnail_url=thumbnail_url_val,
                        input_image_url=input_image_url_val,
                        storage_provider=storage_prov,
                    )
                    session.add(gen_rec)

                await session.commit()
                credit_deductions.add(1, {"user_role": current_user.role, "theme_id": theme_id_val})
                span.set_status(Status(StatusCode.OK))
                return new_balance


    # --- Azure AI Foundry Branch ---
    if active_engine == "azure":
        if not photos or len(photos) == 0:
            raise HTTPException(status_code=400, detail="Please upload a photo for the portrait.")

        primary_photo = photos[0]
        limit = settings.MAX_PHOTO_BYTES
        if limit and primary_photo.size is not None and primary_photo.size > limit:
            raise HTTPException(status_code=413, detail=f"Photo must be at most {limit} bytes.")
        photo_bytes = await primary_photo.read(limit + 1 if limit else -1)
        if limit and len(photo_bytes) > limit:
            raise HTTPException(status_code=413, detail=f"Photo must be at most {limit} bytes.")

        selected_theme = await resolve_theme(theme_id)
        if prompt and prompt.strip():
            base_prompt = prompt.strip()
        else:
            base_prompt = selected_theme["prompt_template"]

        if custom_caption and custom_caption.strip() and custom_caption.strip() not in base_prompt:
            base_prompt = f"{base_prompt}, {custom_caption.strip()}"

        final_prompt = apply_gender_to_prompt(base_prompt, gender)
        job_id = str(uuid.uuid4())

        is_stream = stream or request.query_params.get("stream") == "true"
        if is_stream:
            async def event_generator():
                event_queue: asyncio.Queue = asyncio.Queue()

                async def on_status_update(event_data: Dict[str, Any]):
                    await event_queue.put(event_data)

                async def run_generation():
                    with tracer.start_as_current_span("image.generate") as span:
                        span.set_attribute("gen.engine", active_engine)
                        span.set_attribute("gen.job_id", job_id)
                        span.set_attribute("gen.theme_id", selected_theme["id"])
                        span.set_attribute("gen.aspect_ratio", aspect_ratio)
                        filename = None
                        image_url = None
                        thumbnail_url = None
                        try:
                            filename, image_url, thumbnail_url = await azure_image_client.generate_portrait(
                                photo_bytes=photo_bytes,
                                prompt=final_prompt,
                                aspect_ratio=aspect_ratio,
                                job_id=job_id,
                                on_status=on_status_update,
                            )
                            # Upload input photo preview asynchronously for admin comparison
                            input_image_url = None
                            try:
                                input_image_url = await storage_service.upload_input_photo(
                                    photo_bytes=photo_bytes,
                                    base_filename=f"{job_id}.webp",
                                )
                            except Exception as in_err:
                                print(f"[Storage] Input photo upload notice: {in_err}")

                            # Generation succeeded -> Deduct credit & save to gallery
                            try:
                                remaining_credits = await deduct_user_credit(
                                    job_id_val=job_id,
                                    theme_id_val=selected_theme["id"],
                                    image_url_val=image_url,
                                    thumbnail_url_val=thumbnail_url,
                                    input_image_url_val=input_image_url,
                                )
                            except Exception:
                                revenue_integrity_anomalies.add(1, {
                                    "anomaly_type": "gen_success_no_deduct",
                                    "engine": active_engine,
                                    "theme_id": selected_theme["id"],
                                })
                                raise

                            generation_success.add(1, {"engine": active_engine, "theme_id": selected_theme["id"]})
                            span.set_status(Status(StatusCode.OK))
                            await event_queue.put({
                                "type": "completed",
                                "status": "completed",
                                "job_id": job_id,
                                "theme_id": selected_theme["id"],
                                "theme_title": selected_theme["title"],
                                "prompt_used": final_prompt,
                                "gender": gender,
                                "aspect_ratio": "4:5",
                                "engine_used": "azure_studio",
                                "photos_received": 1,
                                "image_url": image_url,
                                "thumbnail_url": thumbnail_url,
                                "queue_active": True,
                                "remaining_credits": remaining_credits,
                                "quota": {
                                    "remaining_generations": remaining_credits,
                                },
                                "message": "Successfully generated 4:5 portrait."
                            })
                        except HTTPException as http_exc:
                            err_type = "throttled_429" if http_exc.status_code == 429 else f"http_{http_exc.status_code}"
                            generation_failure.add(1, {"engine": active_engine, "error_type": err_type})
                            span.record_exception(http_exc)
                            span.set_status(Status(StatusCode.ERROR, str(http_exc.detail)))
                            await event_queue.put({
                                "type": "error",
                                "status_code": http_exc.status_code,
                                "detail": str(http_exc.detail),
                            })
                        except Exception as exc:
                            generation_failure.add(1, {"engine": active_engine, "error_type": "server_error"})
                            span.record_exception(exc)
                            span.set_status(Status(StatusCode.ERROR, str(exc)))
                            await event_queue.put({
                                "type": "error",
                                "status_code": 500,
                                "detail": f"Azure generation failed: {str(exc)}",
                            })

                gen_task = asyncio.create_task(run_generation())

                try:
                    while True:
                        try:
                            event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                            yield f"data: {json.dumps(event)}\n\n"
                            if event.get("type") in ("completed", "error"):
                                break
                        except asyncio.TimeoutError:
                            yield ": keep-alive\n\n"

                        if gen_task.done() and event_queue.empty():
                            break
                finally:
                    if not gen_task.done():
                        gen_task.cancel()

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        with tracer.start_as_current_span("image.generate") as span:
            span.set_attribute("gen.engine", active_engine)
            span.set_attribute("gen.job_id", job_id)
            span.set_attribute("gen.theme_id", selected_theme["id"])
            span.set_attribute("gen.aspect_ratio", aspect_ratio)
            output_filename = None
            image_url = None
            thumbnail_url = None
            try:
                output_filename, image_url, thumbnail_url = await azure_image_client.generate_portrait(
                    photo_bytes=photo_bytes,
                    prompt=final_prompt,
                    aspect_ratio=aspect_ratio,
                    job_id=job_id,
                )
                input_image_url = None
                try:
                    input_image_url = await storage_service.upload_input_photo(
                        photo_bytes=photo_bytes,
                        base_filename=f"{job_id}.webp",
                    )
                except Exception as in_err:
                    print(f"[Storage] Input photo upload notice: {in_err}")

                try:
                    remaining_credits = await deduct_user_credit(
                        job_id_val=job_id,
                        theme_id_val=selected_theme["id"],
                        image_url_val=image_url,
                        thumbnail_url_val=thumbnail_url,
                        input_image_url_val=input_image_url,
                    )
                except Exception:
                    revenue_integrity_anomalies.add(1, {
                        "anomaly_type": "gen_success_no_deduct",
                        "engine": active_engine,
                        "theme_id": selected_theme["id"],
                    })
                    raise

                generation_success.add(1, {"engine": active_engine, "theme_id": selected_theme["id"]})
                span.set_status(Status(StatusCode.OK))
            except HTTPException as http_exc:
                err_type = "throttled_429" if http_exc.status_code == 429 else f"http_{http_exc.status_code}"
                generation_failure.add(1, {"engine": active_engine, "error_type": err_type})
                span.record_exception(http_exc)
                span.set_status(Status(StatusCode.ERROR, str(http_exc.detail)))
                raise
            except Exception as e:
                generation_failure.add(1, {"engine": active_engine, "error_type": "server_error"})
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

        return {
            "status": "completed",
            "job_id": job_id,
            "theme_id": selected_theme["id"],
            "theme_title": selected_theme["title"],
            "prompt_used": final_prompt,
            "gender": gender,
            "aspect_ratio": "4:5",
            "engine_used": "azure_studio",
            "photos_received": 1,
            "image_url": image_url,
            "thumbnail_url": thumbnail_url,
            "queue_active": True,
            "remaining_credits": remaining_credits,
            "quota": {
                "remaining_generations": remaining_credits,
            },
            "message": "Successfully generated 4:5 portrait."
        }


    # --- Local FLUX.1 + ComfyUI Branch ---
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
        limit = settings.MAX_PHOTO_BYTES
        if limit and photo.size is not None and photo.size > limit:
            raise HTTPException(status_code=413, detail=f"Each photo must be at most {limit} bytes.")
        content = await photo.read(limit + 1 if limit else -1)
        if limit and len(content) > limit:
            raise HTTPException(status_code=413, detail=f"Each photo must be at most {limit} bytes.")
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        unique_name = f"user_{uuid.uuid4().hex[:12]}{ext}"
        dest_path = os.path.join(upload_dir, unique_name)
        async with aiofiles.open(dest_path, "wb") as buffer:
            await buffer.write(content)

        # Upload directly to ComfyUI input directory (works seamlessly in both container & native host mode)
        try:
            await comfy_client.upload_image(content, unique_name)
        except (httpx.HTTPError, RuntimeError) as upload_err:
            if settings.REQUIRE_PULID:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not upload the reference image to ComfyUI: {upload_err}",
                ) from upload_err
            print(f"[Upload Warning] Using the shared input directory after upload failed: {upload_err}")

        saved_filenames.append(unique_name)

    # 3. Resolve aspect ratio (default locked to 4:5)
    width, height = (864, 1080)
    if aspect_ratio == "4:5":
        width, height = (864, 1080)

    # 4. Resolve prompt: User-edited prompt takes precedence, falls back to selected theme template
    selected_theme = await resolve_theme(theme_id)

    if prompt and prompt.strip():
        base_prompt = prompt.strip()
    else:
        base_prompt = selected_theme["prompt_template"]

    if custom_caption and custom_caption.strip() and custom_caption.strip() not in base_prompt:
        base_prompt = f"{base_prompt}, {custom_caption.strip()}"

    # Apply gender anchoring to stop FLUX from defaulting to female when a male photo is provided
    final_prompt = apply_gender_to_prompt(base_prompt, gender)

    # 5. Build ComfyUI workflow graph passing ALL uploaded photos for multi-face vector pooling
    workflow_prompt = build_workflow_prompt(
        positive_prompt=final_prompt,
        reference_images=saved_filenames,
        width=width,
        height=height,
        use_pulid=True if saved_filenames else False,
    )

    # 6. Dispatch job to ComfyUI and await completion
    job_id = str(uuid.uuid4())
    identity_conditioning = "pulid" if saved_filenames else "none"
    try:
        try:
            prompt_id = await comfy_client.queue_prompt(workflow_prompt, client_id=job_id)
        except Exception as queue_err:
            if settings.REQUIRE_PULID:
                raise
            # If PuLID node is missing on server, automatically fallback to base UNet graph
            print(f"[Notice] PuLID node dispatch notice ({queue_err}). Retrying with baseline diffusion...")
            fallback_prompt = build_workflow_prompt(
                positive_prompt=final_prompt,
                reference_images=None,
                width=width,
                height=height,
                use_pulid=False,
            )
            prompt_id = await comfy_client.queue_prompt(fallback_prompt, client_id=job_id)
            identity_conditioning = "none"

        history = await comfy_client.wait_for_completion(
            prompt_id, client_id=job_id, timeout_seconds=settings.INFERENCE_TIMEOUT_SECONDS
        )
        output_filename = comfy_client.extract_output_filename(history)

        if not output_filename:
            generation_failure.add(1, {"engine": "flux", "error_type": "no_output_image"})
            raise RuntimeError(f"ComfyUI completed prompt {prompt_id} but returned no output image.")

        image_url = f"/api/trends/outputs/{output_filename}"
        input_image_url = None
        if saved_filenames:
            try:
                first_photo_path = os.path.join(upload_dir, saved_filenames[0])
                if os.path.exists(first_photo_path):
                    async with aiofiles.open(first_photo_path, "rb") as f:
                        input_bytes = await f.read()
                    input_image_url = await storage_service.upload_input_photo(
                        image_bytes=input_bytes,
                        base_filename=f"{job_id}.webp",
                    )
            except Exception as in_err:
                print(f"[Storage] Input photo upload notice: {in_err}")

        try:
            remaining_credits = await deduct_user_credit(
                job_id_val=job_id,
                theme_id_val=selected_theme["id"],
                image_url_val=image_url,
                input_image_url_val=input_image_url,
            )
        except Exception:
            revenue_integrity_anomalies.add(1, {
                "anomaly_type": "gen_success_no_deduct",
                "engine": "flux",
                "theme_id": selected_theme["id"],
            })
            raise

        generation_success.add(1, {"engine": "flux", "theme_id": selected_theme["id"]})

        return {
            "status": "completed",
            "job_id": job_id,
            "prompt_id": prompt_id,
            "theme_id": selected_theme["id"],
            "theme_title": selected_theme["title"],
            "prompt_used": final_prompt,
            "gender": gender,
            "aspect_ratio": "4:5",
            "dimensions": {"width": width, "height": height},
            "photos_received": len(saved_filenames),
            "identity_conditioning": identity_conditioning,
            "image_url": image_url,
            "remaining_credits": remaining_credits,
            "quota": {
                "remaining_generations": remaining_credits,
                "reset_in_seconds": 86400,
                "rate_limit_enabled": False,
            },
            "message": "Successfully generated 4:5 Instagram trend portrait."
        }


    except Exception as exc:
        generation_failure.add(1, {"engine": "flux", "error_type": "comfy_error"})
        print(f"[Generate Error] Inference failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Image generation failed: {str(exc)}"
        )


@router.get("/my-generations")
async def get_my_generations(
    current_user: User = Depends(get_current_user),
    limit: int = 50,
):
    """
    Retrieves previously generated portraits for the authenticated user,
    ordered by newest first.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Generation)
            .where(Generation.user_id == current_user.id)
            .order_by(desc(Generation.created_at))
            .limit(min(limit, 100))
        )
        res = await session.execute(stmt)
        generations = res.scalars().all()
        return {
            "generations": [
                {
                    "id": str(g.id),
                    "job_id": g.job_id,
                    "theme_id": g.theme_id,
                    "theme_title": g.theme_title,
                    "prompt": g.prompt,
                    "aspect_ratio": g.aspect_ratio,
                    "engine": g.engine,
                    "image_url": g.image_url,
                    "thumbnail_url": g.thumbnail_url or g.image_url,
                    "storage_provider": g.storage_provider,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
                for g in generations
            ]
        }


@router.delete("/my-generations/{generation_id}")
async def delete_my_generation(
    generation_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Deletes a portrait generated by the authenticated user from the database
    and removes associated assets from storage (Azure Blob and local cache).
    """
    from app.services.storage_service import storage_service

    async with AsyncSessionLocal() as session:
        try:
            gen_uuid = uuid.UUID(generation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid generation ID format.")

        stmt = select(Generation).where(
            Generation.id == gen_uuid,
            Generation.user_id == current_user.id,
        )
        res = await session.execute(stmt)
        generation = res.scalar_one_or_none()
        if not generation:
            raise HTTPException(status_code=404, detail="Portrait not found or already deleted.")

        # Clean up storage assets asynchronously
        try:
            await storage_service.delete_portrait_assets(
                image_url=generation.image_url,
                thumbnail_url=generation.thumbnail_url,
                input_image_url=generation.input_image_url,
            )
        except Exception as storage_err:
            print(f"[Storage] Failed to delete storage assets for {generation_id}: {storage_err}")

        # Delete database record
        await session.delete(generation)
        await session.commit()

        return {"status": "deleted", "id": str(generation.id)}


@router.api_route("/outputs/{filename}", methods=["GET", "HEAD"])
async def get_generated_image(filename: str):
    """
    Serves generated images from the shared outputs volume or proxies from ComfyUI.
    Automatically generates WebP thumbnails on demand if a thumbnail is requested and master exists.
    """
    import mimetypes
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(OUTPUTS_DIR, safe_filename)

    # On-demand thumbnail generation for local disk if requested thumbnail doesn't exist yet
    if not os.path.isfile(filepath) and safe_filename.endswith("_thumb.webp"):
        master_name = safe_filename.replace("_thumb.webp", ".png")
        master_path = os.path.join(OUTPUTS_DIR, master_name)
        if os.path.isfile(master_path):
            try:
                from app.services.storage_service import create_webp_thumbnail
                async with aiofiles.open(master_path, "rb") as f:
                    master_bytes = await f.read()
                thumb_bytes = create_webp_thumbnail(master_bytes)
                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(thumb_bytes)
            except Exception as e:
                print(f"[Thumbnail Error] On-demand thumbnail generation failed: {e}")

    # Direct file serving if available in mounted volume
    if os.path.isfile(filepath):
        guessed_type, _ = mimetypes.guess_type(filepath)
        media_type = guessed_type or "image/png"
        return FileResponse(filepath, media_type=media_type)

    # Fallback: proxy from ComfyUI /view endpoint
    comfy_view_url = f"{settings.COMFYUI_URL}/view?filename={safe_filename}&type=output"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(comfy_view_url)
            if resp.status_code == 200:
                guessed_type, _ = mimetypes.guess_type(safe_filename)
                return Response(content=resp.content, media_type=guessed_type or "image/png")
        except Exception as err:
            print(f"[Outputs Proxy Error] Failed to proxy {safe_filename} from ComfyUI: {err}")

    raise HTTPException(status_code=404, detail="Generated image not found.")
