import asyncio
import base64
import os
import time
import uuid
from typing import Optional
from urllib.parse import urlparse
import aiofiles
import httpx
from fastapi import HTTPException

from app.core.config import settings

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs")


def _is_rate_limited(err: Exception) -> bool:
    status = getattr(err, "status_code", None)
    if status == 429:
        return True
    err_str = str(err).lower()
    return (
        "429" in err_str
        or "rate limit" in err_str
        or "throttl" in err_str
        or "too many requests" in err_str
    )


def _is_moderation_blocked(err: Exception) -> bool:
    status = getattr(err, "status_code", None)
    err_str = str(err).lower()
    return (
        "moderation_blocked" in err_str
        or "safety system" in err_str
        or "content safety" in err_str
        or (status == 400 and ("safety" in err_str or "moderation" in err_str or "categories" in err_str))
    )


class AzureImageClient:
    """
    Client for Microsoft Azure AI Foundry gpt-image-2.5-flare model
    via the OpenAI-compatible `/openai/v1` API.

    Maintains a sequential queue ensuring requests are spaced by at least 30 seconds
    (or starts immediately if the previous request took >= 30 seconds).
    Automatically retries with a 30-second backoff if the model returns a failure
    or is throttled.
    """

    def __init__(self):
        self._queue_lock = asyncio.Lock()
        self._last_dispatch_time: float = 0.0
        self.MIN_INTERVAL_SECONDS: float = 30.0

    def _normalize_base_url(self, raw_endpoint: str) -> str:
        """
        Ensures the endpoint is in the format expected by Azure AI Foundry OpenAI API:
        e.g. 'https://imageeastus2-resource.services.ai.azure.com/openai/v1'
        """
        clean = raw_endpoint.strip().rstrip("/")
        if clean.endswith("/openai/v1"):
            return clean

        parsed = urlparse(clean)
        scheme = parsed.scheme or "https"
        host = parsed.netloc or parsed.path.split("/")[0]

        return f"{scheme}://{host}/openai/v1"

    async def _execute_single_attempt(
        self,
        base_url: str,
        deployment_name: str,
        photo_bytes: bytes,
        prompt: str,
        size: str,
        output_filepath: str,
    ) -> bool:
        """
        Executes a single API call to Azure AI Foundry via images.edit (or fallback to images.generate).
        Writes output to output_filepath and returns True on success.
        Raises HTTPException or Exception on failure.
        """
        edit_prompt = (
            f"Transform the person in the photo into this portrait aesthetic while strictly preserving their face, "
            f"facial structure, and likeness: {prompt}"
        )

        # 1. Try using OpenAI AsyncOpenAI SDK
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                base_url=base_url,
                api_key=settings.AZURE_AI_API_KEY,
                timeout=90.0,
            )

            # Try images.edit with photo
            try:
                img_resp = await client.images.edit(
                    model=deployment_name,
                    image=("user_face.png", photo_bytes, "image/png"),
                    prompt=edit_prompt,
                    size=size,
                )
            except Exception as edit_err:
                if _is_rate_limited(edit_err):
                    raise HTTPException(
                        status_code=429,
                        detail=f"Azure rate limit reached (429): {str(edit_err)}",
                    )
                if _is_moderation_blocked(edit_err):
                    raise HTTPException(
                        status_code=400,
                        detail="The generated image was flagged by Azure's content safety filter (e.g. references to minors or sensitive terms). Please try Cyberpunk or another theme, or adjust the prompt wording.",
                    )

                print(f"[Azure Queue] images.edit failed ({edit_err}), trying images.generate...")
                try:
                    img_resp = await client.images.generate(
                        model=deployment_name,
                        prompt=prompt,
                        n=1,
                        size=size,
                    )
                except Exception as gen_err:
                    if _is_rate_limited(gen_err):
                        raise HTTPException(
                            status_code=429,
                            detail=f"Azure rate limit reached (429): {str(gen_err)}",
                        )
                    if _is_moderation_blocked(gen_err):
                        raise HTTPException(
                            status_code=400,
                            detail="The generated image was flagged by Azure's content safety filter (e.g. references to minors or sensitive terms). Please try Cyberpunk or another theme, or adjust the prompt wording.",
                        )
                    raise gen_err

            if img_resp and img_resp.data:
                first_item = img_resp.data[0]
                image_bytes: Optional[bytes] = None

                if hasattr(first_item, "b64_json") and first_item.b64_json:
                    image_bytes = base64.b64decode(first_item.b64_json)
                elif hasattr(first_item, "url") and first_item.url:
                    async with httpx.AsyncClient(timeout=60.0) as dl_client:
                        dl_resp = await dl_client.get(first_item.url)
                        if dl_resp.status_code == 200:
                            image_bytes = dl_resp.content

                if image_bytes:
                    async with aiofiles.open(output_filepath, "wb") as f:
                        await f.write(image_bytes)
                    return True

        except HTTPException:
            raise
        except Exception as sdk_err:
            print(f"[Azure Queue] SDK call warning: {sdk_err}. Trying direct REST...")

        # 2. Direct REST fallback via httpx
        url = f"{base_url}/images/generations"
        headers = {
            "api-key": settings.AZURE_AI_API_KEY,
            "Authorization": f"Bearer {settings.AZURE_AI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": deployment_name,
            "prompt": prompt,
            "n": 1,
            "size": size,
        }

        async with httpx.AsyncClient(timeout=90.0) as http_client:
            response = await http_client.post(url, headers=headers, json=payload)

            if response.status_code in (200, 201):
                data = response.json().get("data", [])
                if not data:
                    raise RuntimeError(f"Azure response contained no data: {response.text}")

                first = data[0]
                if "b64_json" in first and first["b64_json"]:
                    img_bytes = base64.b64decode(first["b64_json"])
                    async with aiofiles.open(output_filepath, "wb") as f:
                        await f.write(img_bytes)
                    return True

                elif "url" in first and first["url"]:
                    dl_resp = await http_client.get(first["url"])
                    if dl_resp.status_code == 200:
                        async with aiofiles.open(output_filepath, "wb") as f:
                            await f.write(dl_resp.content)
                        return True

            if response.status_code == 429:
                raise HTTPException(
                    status_code=429,
                    detail=f"Azure rate limit reached (429): {response.text}",
                )

            if "moderation_blocked" in response.text or "safety system" in response.text:
                raise HTTPException(
                    status_code=400,
                    detail="The generated image was flagged by Azure's content safety filter (e.g. references to minors or sensitive terms). Please try Cyberpunk or another theme, or adjust the prompt wording.",
                )

            raise HTTPException(
                status_code=response.status_code,
                detail=f"Azure AI generation failed ({response.status_code}): {response.text}",
            )

    async def generate_portrait(
        self,
        photo_bytes: bytes,
        prompt: str,
        aspect_ratio: str = "4:5",
        max_retries: int = 3,
    ) -> str:
        """
        Enters the sequential queue, waits until at least 30s have passed since the last
        request started (or starts immediately if the last request took >=30s).
        If the model returns a failure or is throttled, waits 30s and retries.
        """
        if not settings.AZURE_AI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="AZURE_AI_API_KEY is not configured on the server. Please check your environment variables.",
            )

        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        unique_id = uuid.uuid4().hex[:12]
        output_filename = f"instaxoom_azure_{unique_id}.png"
        output_filepath = os.path.join(OUTPUTS_DIR, output_filename)

        base_url = self._normalize_base_url(settings.AZURE_AI_ENDPOINT)
        deployment_name = settings.AZURE_AI_DEPLOYMENT
        size = "1024x1024"

        # Serialize requests via queue lock
        async with self._queue_lock:
            # Enforce 30-second spacing between request dispatches
            now = time.time()
            elapsed = now - self._last_dispatch_time
            if self._last_dispatch_time > 0 and elapsed < self.MIN_INTERVAL_SECONDS:
                wait_time = self.MIN_INTERVAL_SECONDS - elapsed
                print(f"[Azure Queue] Request waiting {wait_time:.1f}s in queue to respect 30s spacing...")
                await asyncio.sleep(wait_time)

            last_error: Optional[Exception] = None

            # Retry loop: if failure or throttled, wait 30 seconds and retry
            for attempt in range(1, max_retries + 1):
                self._last_dispatch_time = time.time()
                try:
                    print(f"[Azure Queue] Dispatching image request to Azure (attempt {attempt}/{max_retries})...")
                    success = await self._execute_single_attempt(
                        base_url=base_url,
                        deployment_name=deployment_name,
                        photo_bytes=photo_bytes,
                        prompt=prompt,
                        size=size,
                        output_filepath=output_filepath,
                    )
                    if success:
                        print(f"[Azure Queue] Generation succeeded on attempt {attempt}!")
                        return output_filename

                except HTTPException as http_exc:
                    last_error = http_exc
                    # Never retry non-transient 400 moderation blocks (prompt text needs to be changed by user)
                    if http_exc.status_code == 400 and "content safety filter" in str(http_exc.detail):
                        raise

                    if attempt < max_retries:
                        print(
                            f"[Azure Queue] Model throttled or failed (HTTP {http_exc.status_code}). "
                            f"Waiting 30 seconds before retry (attempt {attempt + 1}/{max_retries})..."
                        )
                        await asyncio.sleep(30.0)
                        continue
                    raise

                except Exception as exc:
                    last_error = exc
                    if attempt < max_retries:
                        print(
                            f"[Azure Queue] Request encountered error ({exc}). "
                            f"Waiting 30 seconds before retry (attempt {attempt + 1}/{max_retries})..."
                        )
                        await asyncio.sleep(30.0)
                        continue
                    raise HTTPException(
                        status_code=502,
                        detail=f"Azure AI generation failed after {max_retries} attempts: {str(exc)}",
                    )

            if last_error:
                raise last_error

            raise HTTPException(status_code=500, detail="Azure generation ended without result.")


azure_image_client = AzureImageClient()
