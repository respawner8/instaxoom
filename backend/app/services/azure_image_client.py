import base64
import os
import time
import uuid
from typing import List, Optional
from urllib.parse import urlparse
import aiofiles
import httpx
from fastapi import HTTPException

from app.core.config import settings

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs")


class AzureImageClient:
    """
    Client for Microsoft Azure AI Foundry gpt-image-2.5-flare model
    via the OpenAI-compatible `/openai/v1` API.
    Enforces a 2 Requests-Per-Minute (RPM) rate limiter.
    """

    def __init__(self):
        self._request_timestamps: List[float] = []

    def check_rate_limit(self) -> None:
        """
        Enforces maximum RPM (default 2 images per 60 seconds).
        Raises HTTP 429 with Retry-After header if limit is exceeded.
        """
        now = time.time()
        # Keep timestamps from the last 60 seconds
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60.0]

        if len(self._request_timestamps) >= settings.AZURE_RATE_LIMIT_RPM:
            oldest = self._request_timestamps[0]
            wait_seconds = max(1, int(60.0 - (now - oldest)) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"Azure rate limit reached (max {settings.AZURE_RATE_LIMIT_RPM} images per minute). Please wait {wait_seconds} seconds before trying again.",
                headers={"Retry-After": str(wait_seconds)},
            )

    def record_request(self) -> None:
        """Records a successful request timestamp for rate limiting."""
        self._request_timestamps.append(time.time())

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

        # In Azure AI Foundry, OpenAI API endpoints are at https://<resource>.services.ai.azure.com/openai/v1
        return f"{scheme}://{host}/openai/v1"

    async def generate_portrait(
        self,
        photo_bytes: bytes,
        prompt: str,
        aspect_ratio: str = "4:5",
    ) -> str:
        """
        Submits the prompt to Azure AI Foundry gpt-image-2.5-flare model.
        Decodes the b64_json output and persists it to outputs directory.
        Returns the saved output filename.
        """
        if not settings.AZURE_AI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="AZURE_AI_API_KEY is not configured on the server. Please check your environment variables.",
            )

        # 1. Enforce 2 RPM rate limit
        self.check_rate_limit()

        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        unique_id = uuid.uuid4().hex[:12]
        output_filename = f"instaxoom_azure_{unique_id}.png"
        output_filepath = os.path.join(OUTPUTS_DIR, output_filename)

        base_url = self._normalize_base_url(settings.AZURE_AI_ENDPOINT)
        deployment_name = settings.AZURE_AI_DEPLOYMENT
        size = "1024x1024"

        # Attempt 1: Using official OpenAI async SDK
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                base_url=base_url,
                api_key=settings.AZURE_AI_API_KEY,
                timeout=90.0,
            )

            img_resp = await client.images.generate(
                model=deployment_name,
                prompt=prompt,
                n=1,
                size=size,
            )

            if not img_resp.data:
                raise RuntimeError("Azure AI returned empty image data array.")

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
                self.record_request()
                async with aiofiles.open(output_filepath, "wb") as f:
                    await f.write(image_bytes)
                return output_filename

        except HTTPException:
            raise
        except Exception as sdk_err:
            print(f"[AzureImageClient SDK Warning] Falling back to direct REST: {sdk_err}")

        # Attempt 2: Direct REST call via httpx
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
            try:
                response = await http_client.post(url, headers=headers, json=payload)

                if response.status_code in (200, 201):
                    self.record_request()
                    data = response.json().get("data", [])
                    if not data:
                        raise RuntimeError(f"Azure response contained no data: {response.text}")

                    first = data[0]
                    if "b64_json" in first and first["b64_json"]:
                        img_bytes = base64.b64decode(first["b64_json"])
                        async with aiofiles.open(output_filepath, "wb") as f:
                            await f.write(img_bytes)
                        return output_filename

                    elif "url" in first and first["url"]:
                        dl_resp = await http_client.get(first["url"])
                        if dl_resp.status_code == 200:
                            async with aiofiles.open(output_filepath, "wb") as f:
                                await f.write(dl_resp.content)
                            return output_filename

                elif response.status_code == 429:
                    self.record_request()
                    retry_after = response.headers.get("Retry-After", "30")
                    raise HTTPException(
                        status_code=429,
                        detail="Azure rate limit reached (2 images/min). Please try again shortly.",
                        headers={"Retry-After": retry_after},
                    )

                if "moderation_blocked" in response.text:
                    raise HTTPException(
                        status_code=400,
                        detail="The generated image was flagged by Azure's content safety filter (e.g. references to minors or sensitive terms). Please try Cyberpunk or another theme, or adjust the prompt wording.",
                    )

                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Azure AI generation failed ({response.status_code}): {response.text}",
                )

            except HTTPException:
                raise
            except Exception as req_err:
                raise HTTPException(
                    status_code=502,
                    detail=f"Azure AI connection error: {str(req_err)}",
                )


azure_image_client = AzureImageClient()
