import base64
import os
import time
import uuid
from typing import Optional, List, Tuple
from urllib.parse import urlparse
import aiofiles
import httpx
from fastapi import HTTPException

from app.core.config import settings

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs")


class AzureImageClient:
    """
    Client for Microsoft Azure AI Foundry / Azure OpenAI image models
    (such as gpt-image-2.5-flare).
    Enforces a strict 2 Requests-Per-Minute (RPM) rate limiter.
    """

    def __init__(self):
        self._request_timestamps: List[float] = []

    def check_rate_limit(self) -> None:
        """
        Enforces maximum RPM (default 2 images per 60 seconds).
        Raises HTTP 429 with Retry-After header if limit exceeded.
        """
        now = time.time()
        # Prune timestamps older than 60 seconds
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60.0]

        if len(self._request_timestamps) >= settings.AZURE_RATE_LIMIT_RPM:
            oldest = self._request_timestamps[0]
            wait_seconds = max(1, int(60.0 - (now - oldest)) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"Azure rate limit exceeded (max {settings.AZURE_RATE_LIMIT_RPM} images per minute). Please wait {wait_seconds} seconds before trying again.",
                headers={"Retry-After": str(wait_seconds)},
            )

    def record_request(self) -> None:
        """Records a successful or in-flight request timestamp for rate limiting."""
        self._request_timestamps.append(time.time())

    def _get_candidate_endpoints(self) -> List[Tuple[str, str]]:
        """
        Derives prioritized endpoint URLs from settings.AZURE_AI_ENDPOINT.
        Supports Azure AI Foundry project URLs, models endpoints, and Azure OpenAI paths.
        Returns a list of tuples: (endpoint_url, type: 'edits' | 'generations')
        """
        endpoint = settings.AZURE_AI_ENDPOINT.rstrip("/")
        deployment = settings.AZURE_AI_DEPLOYMENT
        api_version = settings.AZURE_AI_API_VERSION

        parsed = urlparse(endpoint)
        hostname = parsed.hostname or ""
        # e.g. "imageeastus2-resource" from "imageeastus2-resource.services.ai.azure.com"
        resource_name = hostname.split(".")[0]

        candidates = []

        # 1. Direct project / models endpoints
        candidates.append((f"{endpoint}/images/edits", "edits"))
        candidates.append((f"{endpoint}/models/images/edits", "edits"))
        candidates.append((f"https://{resource_name}.services.ai.azure.com/models/images/edits", "edits"))

        # 2. Azure OpenAI standard deployments endpoint
        candidates.append((
            f"https://{resource_name}.openai.azure.com/openai/deployments/{deployment}/images/edits?api-version={api_version}",
            "edits",
        ))

        # 3. Fallbacks to text-to-image generations if edits is unsupported on a specific tier
        candidates.append((f"{endpoint}/images/generations", "generations"))
        candidates.append((f"{endpoint}/models/images/generations", "generations"))
        candidates.append((
            f"https://{resource_name}.openai.azure.com/openai/deployments/{deployment}/images/generations?api-version={api_version}",
            "generations",
        ))

        return candidates

    async def generate_portrait(
        self,
        photo_bytes: bytes,
        prompt: str,
        aspect_ratio: str = "4:5",
    ) -> str:
        """
        Submits the user headshot and prompt to Azure AI Foundry gpt-image-2.5-flare.
        Downloads or decodes the generated image and persists it to the outputs directory.
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

        headers = {
            "api-key": settings.AZURE_AI_API_KEY,
        }

        # Size mapping
        size = "1024x1024"

        last_error = "No endpoints attempted"
        candidate_endpoints = self._get_candidate_endpoints()

        async with httpx.AsyncClient(timeout=120.0) as client:
            for url, call_type in candidate_endpoints:
                try:
                    if call_type == "edits":
                        # Form-data with image file and prompt
                        files = {
                            "image": ("input.png", photo_bytes, "image/png"),
                        }
                        data = {
                            "model": settings.AZURE_AI_DEPLOYMENT,
                            "prompt": prompt,
                            "size": size,
                            "n": "1",
                        }
                        response = await client.post(url, headers=headers, files=files, data=data)
                    else:
                        # JSON payload for generations
                        json_body = {
                            "model": settings.AZURE_AI_DEPLOYMENT,
                            "prompt": prompt,
                            "size": size,
                            "n": 1,
                        }
                        response = await client.post(url, headers=headers, json=json_body)

                    if response.status_code == 401:
                        # Try Authorization: Bearer fallback
                        auth_headers = {"Authorization": f"Bearer {settings.AZURE_AI_API_KEY}"}
                        if call_type == "edits":
                            response = await client.post(url, headers=auth_headers, files=files, data=data)
                        else:
                            response = await client.post(url, headers=auth_headers, json=json_body)

                    if response.status_code in (200, 201):
                        self.record_request()
                        result = response.json()
                        image_data = result.get("data", [])
                        if not image_data:
                            raise RuntimeError("Azure AI returned empty image data array.")

                        first_item = image_data[0]
                        if "b64_json" in first_item:
                            image_bytes = base64.b64decode(first_item["b64_json"])
                            async with aiofiles.open(output_filepath, "wb") as f:
                                await f.write(image_bytes)
                            return output_filename

                        elif "url" in first_item:
                            img_url = first_item["url"]
                            # Download remote image so it doesn't expire
                            dl_resp = await client.get(img_url)
                            if dl_resp.status_code == 200:
                                async with aiofiles.open(output_filepath, "wb") as f:
                                    await f.write(dl_resp.content)
                                return output_filename
                            else:
                                raise RuntimeError(f"Failed to download image from Azure URL: {dl_resp.status_code}")

                    elif response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "30")
                        self.record_request()
                        raise HTTPException(
                            status_code=429,
                            detail=f"Azure model rate limit reached: {response.text}",
                            headers={"Retry-After": retry_after},
                        )
                    else:
                        last_error = f"Status {response.status_code} from {url}: {response.text}"
                        # If 404 or 400 with path error, try next candidate endpoint
                        continue

                except HTTPException:
                    raise
                except Exception as attempt_err:
                    last_error = str(attempt_err)
                    continue

        raise HTTPException(
            status_code=502,
            detail=f"Azure AI generation failed across all attempted endpoints. Last error: {last_error}",
        )


azure_image_client = AzureImageClient()
