import asyncio
import base64
import os
import time
import uuid
from typing import Optional, Callable, Dict, Any, List
from urllib.parse import urlparse
import aiofiles
import httpx
from fastapi import HTTPException
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.core.config import settings
from app.core.app_metrics import azure_duration_histogram, azure_queue_wait_histogram
from app.services.storage_service import storage_service

tracer = trace.get_tracer("instaxoom.azure")

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


def get_base_duration_for_model(name: str) -> float:
    name_lower = name.lower()
    if "1.5" in name_lower:
        return 15.0
    return 25.0


class DeploymentWorker:
    """
    Represents an individual model deployment worker in Azure AI Foundry.
    Enforces independent rate-limiting (min_interval), concurrency locking,
    and adaptive latency tracking per model.
    """
    def __init__(self, name: str, rpm: float, priority: int):
        self.name = name
        self.rpm = max(0.1, float(rpm))
        self.priority = priority
        self.min_interval = 60.0 / self.rpm
        self.base_duration: float = get_base_duration_for_model(name)
        self.avg_duration: float = self.base_duration
        self.lock = asyncio.Lock()
        self.last_dispatch_time: float = 0.0
        self.active_job_id: Optional[str] = None
        self.active_job_start: float = 0.0
        self.cooldown_until: float = 0.0

    @property
    def is_locked(self) -> bool:
        return self.lock.locked()

    def record_completion(self, actual_duration: float):
        """Updates exponential moving average latency, safely bounded [10s, 40s]."""
        self.avg_duration = max(10.0, min(40.0, 0.8 * self.avg_duration + 0.2 * actual_duration))

    def cooldown_remaining(self) -> float:
        return max(0.0, self.cooldown_until - time.time())

    def spacing_remaining(self) -> float:
        if self.last_dispatch_time <= 0:
            return 0.0
        return max(0.0, self.min_interval - (time.time() - self.last_dispatch_time))

    def ready_in_seconds(self) -> float:
        if self.is_locked:
            elapsed = time.time() - self.active_job_start if self.active_job_start > 0 else 0.0
            return max(1.0, self.avg_duration - elapsed)
        return max(self.cooldown_remaining(), self.spacing_remaining())

    def is_immediately_ready(self) -> bool:
        return not self.is_locked and self.ready_in_seconds() <= 0.0


class AzureImageClient:
    """
    Client for Microsoft Azure AI Foundry image generation models
    supporting a multi-deployment priority pool (e.g. Flare -> Sunburst -> Image-2 -> Image-1.5).
    """

    def __init__(self):
        self.DEFAULT_DURATION: float = 25.0
        self._pool_lock = asyncio.Lock()
        self._waiting_jobs: List[Dict[str, Any]] = []
        self._init_workers()

    def _init_workers(self):
        self.workers: List[DeploymentWorker] = []
        deployments = settings.azure_deployments_list
        for idx, (name, rpm) in enumerate(deployments):
            self.workers.append(DeploymentWorker(name=name, rpm=rpm, priority=idx + 1))
        print(
            f"[Azure Pool] Initialized {len(self.workers)} deployment workers: "
            + ", ".join([f"#{w.priority} {w.name} ({w.rpm} RPM, est {int(w.base_duration)}s)" for w in self.workers])
        )

    def calculate_estimated_wait(self, position: int) -> int:
        if position <= 0:
            return int(self.DEFAULT_DURATION)
        total_rpm = sum(w.rpm for w in self.workers) or 2.0
        avg_slot_interval = 60.0 / total_rpm
        est = (position - 1) * avg_slot_interval + self.DEFAULT_DURATION
        return max(3, int(est))

    def get_queue_status(self) -> Dict[str, Any]:
        waiting_count = len(self._waiting_jobs)
        active_workers = [w.name for w in self.workers if w.is_locked or w.active_job_id]
        active_count = len(active_workers)
        total_workers = len(self.workers)

        if waiting_count == 0 and active_count < total_workers:
            available_slots = total_workers - active_count
            status_text = f"Ready ({available_slots}/{total_workers} slots available)"
            est_seconds = 0
        elif waiting_count == 0:
            min_wait = min((w.ready_in_seconds() for w in self.workers), default=15.0)
            est_seconds = max(1, int(min_wait))
            status_text = f"Active ({active_count}/{total_workers} generating, next in ~{est_seconds}s)"
        else:
            total_rpm = sum(w.rpm for w in self.workers) or 2.0
            avg_interval = 60.0 / total_rpm
            est_seconds = max(3, int(waiting_count * avg_interval + 15))
            status_text = f"{waiting_count} in queue ({active_count}/{total_workers} active, ~{est_seconds}s wait)"

        return {
            "active_jobs": active_count,
            "waiting_jobs": waiting_count,
            "total_in_queue": waiting_count + active_count,
            "total_workers": total_workers,
            "active_workers": active_count,
            "estimated_wait_seconds": est_seconds,
            "status_text": status_text,
        }

    async def _broadcast_queue_updates(self):
        for idx, item in enumerate(list(self._waiting_jobs)):
            cb = item.get("on_status")
            if cb:
                pos = idx + 1
                est = self.calculate_estimated_wait(pos)
                try:
                    res = cb({
                        "type": "queue_update",
                        "job_id": item["job_id"],
                        "position": pos,
                        "estimated_seconds": est,
                        "message": f"In queue (#{pos} in line) — Est. wait: ~{est}s",
                    })
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as b_err:
                    print(f"[Azure Pool] Broadcast error: {b_err}")

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
        output_filename: str,
    ) -> Optional[tuple[str, str]]:
        start_time = time.time()
        with tracer.start_as_current_span("azure.gpt_image_flare") as span:
            span.set_attribute("azure.deployment", deployment_name)
            span.set_attribute("azure.size", size)
            span.set_attribute("azure.prompt_length", len(prompt))
            try:
                gen_result = await self._do_execute_attempt(
                    base_url, deployment_name, photo_bytes, prompt, size, output_filename
                )
                duration = time.time() - start_time
                azure_duration_histogram.record(duration, {"deployment": deployment_name, "status": "success"})
                span.set_attribute("azure.duration_seconds", duration)
                span.set_status(Status(StatusCode.OK))
                return gen_result
            except Exception as exc:
                duration = time.time() - start_time
                azure_duration_histogram.record(duration, {"deployment": deployment_name, "status": "error"})
                span.set_attribute("azure.duration_seconds", duration)
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

    async def _do_execute_attempt(
        self,
        base_url: str,
        deployment_name: str,
        photo_bytes: bytes,
        prompt: str,
        size: str,
        output_filename: str,
    ) -> Optional[tuple[str, str]]:
        """
        Executes a single API call to Azure AI Foundry via images.edit (or fallback to images.generate).
        Uploads master lossless image and WebP thumbnail via storage_service (Azure Blob or local fallback).
        Returns a tuple of (public_image_url, thumbnail_url).
        Raises HTTPException or Exception on failure.
        """
        clean_prompt = prompt.strip().rstrip(".")
        edit_prompt = (
            f"Preserve the exact face, facial features, bone structure, eye shape, nose, mouth contours, skin tone, and authentic likeness of the person in the photo with 100% fidelity. "
            f"Do not alter or beautify their natural facial geometry. "
            f"Only modify the wardrobe, background setting, and lighting aesthetic to match: {clean_prompt}."
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
                    return await storage_service.upload_portrait_with_thumbnail(image_bytes, output_filename)

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
                    return await storage_service.upload_portrait_with_thumbnail(img_bytes, output_filename)

                elif "url" in first and first["url"]:
                    dl_resp = await http_client.get(first["url"])
                    if dl_resp.status_code == 200:
                        return await storage_service.upload_portrait_with_thumbnail(dl_resp.content, output_filename)

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

    async def _acquire_worker(
        self,
        waiting_item: Dict[str, Any],
        on_status: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> DeploymentWorker:
        """
        Acquires an available worker in priority order.
        If all workers are busy or cooling down, queues the request and waits until
        a worker becomes available.
        """
        unique_id = waiting_item["job_id"]

        while True:
            # 1. Under pool lock, check for an immediately ready worker in priority order
            async with self._pool_lock:
                # Add to waiting jobs if not present
                if waiting_item not in self._waiting_jobs:
                    self._waiting_jobs.append(waiting_item)

                # Check workers in strict priority order (0 = highest priority)
                for candidate in self.workers:
                    if candidate.is_immediately_ready():
                        await candidate.lock.acquire()
                        if waiting_item in self._waiting_jobs:
                            self._waiting_jobs.remove(waiting_item)
                        await self._broadcast_queue_updates()
                        return candidate

                # If no worker is immediately ready, check if any unlocked worker has lowest spacing
                # Only front-of-queue job may wait on spacing
                if self._waiting_jobs and self._waiting_jobs[0]["job_id"] == unique_id:
                    unlocked_workers = [w for w in self.workers if not w.is_locked and w.cooldown_remaining() <= 0.0]
                    if unlocked_workers:
                        best = min(unlocked_workers, key=lambda w: w.ready_in_seconds())
                        if best.ready_in_seconds() <= 2.5:
                            await best.lock.acquire()
                            if waiting_item in self._waiting_jobs:
                                self._waiting_jobs.remove(waiting_item)
                            await self._broadcast_queue_updates()
                            return best

            # 2. Notify queue position while waiting
            pos = self._waiting_jobs.index(waiting_item) + 1 if waiting_item in self._waiting_jobs else 1
            est_wait = self.calculate_estimated_wait(pos)
            if on_status:
                try:
                    res = on_status({
                        "type": "queued",
                        "job_id": unique_id,
                        "position": pos,
                        "estimated_seconds": est_wait,
                        "message": f"In queue (#{pos} in line) — Est. wait: ~{est_wait}s",
                    })
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as cb_err:
                    print(f"[Azure Pool] on_status error: {cb_err}")

            # 3. Sleep briefly before checking pool availability again
            min_ready = min((w.ready_in_seconds() for w in self.workers), default=1.0)
            sleep_time = min(max(0.5, min_ready), 2.5)
            await asyncio.sleep(sleep_time)

    async def generate_portrait(
        self,
        photo_bytes: bytes,
        prompt: str,
        aspect_ratio: str = "4:5",
        max_retries: int = 3,
        job_id: Optional[str] = None,
        on_status: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> tuple[str, str, str]:
        """
        Dispatches image generation to the highest-priority available worker in the pool
        (e.g., Flare -> Sunburst -> Image-2 -> Image-1.5).
        Emits live status updates (queued, spacing_wait, processing, retrying, completed).
        Automatically fails over to the next priority worker on 429 rate limit errors.
        Returns (output_filename, public_image_url, thumbnail_url).
        """
        if not settings.AZURE_AI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="AZURE_AI_API_KEY is not configured on the server. Please check your environment variables.",
            )

        unique_id = job_id or uuid.uuid4().hex[:12]
        output_filename = f"instaxoom_azure_{unique_id}.png"
        base_url = self._normalize_base_url(settings.AZURE_AI_ENDPOINT)
        size = "1024x1024"

        waiting_item = {"job_id": unique_id, "on_status": on_status}
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            worker: Optional[DeploymentWorker] = None
            try:
                # 1. Acquire an available worker channel from the priority pool
                worker = await self._acquire_worker(waiting_item, on_status)

                # 2. Enforce worker-specific rate-limit spacing if needed
                spacing_wait = worker.spacing_remaining()
                if spacing_wait > 0:
                    azure_queue_wait_histogram.record(spacing_wait, {"reason": "rate_limit_spacing", "worker": worker.name})
                    with tracer.start_as_current_span("azure.queue_spacing_wait") as wait_span:
                        wait_span.set_attribute("queue.wait_seconds", spacing_wait)
                        wait_span.set_attribute("queue.worker", worker.name)
                        print(f"[Azure Pool] Request waiting {spacing_wait:.1f}s on {worker.name} for rate-limit spacing...")
                        if on_status:
                            try:
                                res = on_status({
                                    "type": "spacing_wait",
                                    "job_id": unique_id,
                                    "wait_seconds": int(spacing_wait),
                                    "message": f"Optimal quality pacing — Starting in {int(spacing_wait)}s...",
                                })
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception as cb_err:
                                print(f"[Azure Pool] on_status error: {cb_err}")

                    await asyncio.sleep(spacing_wait)

                worker.active_job_id = unique_id
                worker.active_job_start = time.time()
                worker.last_dispatch_time = time.time()

                # 3. Notify user of processing without leaking internal model names
                est_duration = int(worker.base_duration)
                print(f"[Azure Pool] Dispatching image request to #{worker.priority} {worker.name} (attempt {attempt}/{max_retries}, est: ~{est_duration}s)...")
                if on_status:
                    try:
                        res = on_status({
                            "type": "processing",
                            "job_id": unique_id,
                            "attempt": attempt,
                            "position": 0,
                            "estimated_seconds": est_duration,
                            "message": f"Generating portrait in studio quality... (~{est_duration}s)",
                        })
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as cb_err:
                        print(f"[Azure Pool] on_status error: {cb_err}")

                # 4. Execute inference attempt
                gen_result = await self._execute_single_attempt(
                    base_url=base_url,
                    deployment_name=worker.name,
                    photo_bytes=photo_bytes,
                    prompt=prompt,
                    size=size,
                    output_filename=output_filename,
                )
                if gen_result:
                    image_url, thumb_url = gen_result
                    actual_dur = time.time() - worker.active_job_start
                    worker.record_completion(actual_dur)
                    print(f"[Azure Pool] Generation succeeded on {worker.name} in {actual_dur:.1f}s (attempt {attempt})! URL: {image_url}")
                    return output_filename, image_url, thumb_url

            except HTTPException as http_exc:
                last_error = http_exc
                # Do not retry non-transient content moderation blocks
                if http_exc.status_code == 400 and "content safety filter" in str(http_exc.detail):
                    raise

                if worker and http_exc.status_code == 429:
                    worker.cooldown_until = time.time() + 30.0
                    print(f"[Azure Pool] Worker {worker.name} rate-limited (429). Setting 30s cooldown and failing over...")

                if attempt < max_retries:
                    failover_msg = (
                        f"High server load detected. Rerouting to next available studio engine "
                        f"(Attempt {attempt + 1}/{max_retries})..."
                    )
                    print(f"[Azure Pool] {failover_msg}")
                    if on_status:
                        try:
                            res = on_status({
                                "type": "retrying",
                                "job_id": unique_id,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "wait_seconds": 2,
                                "message": failover_msg,
                            })
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception as cb_err:
                            print(f"[Azure Pool] on_status error: {cb_err}")

                    await asyncio.sleep(2.0)
                    continue
                raise

            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    err_msg = (
                        f"Encountered temporary error. Retrying with next available studio engine "
                        f"(Attempt {attempt + 1}/{max_retries})..."
                    )
                    print(f"[Azure Pool] Encountered temporary error ({exc}). Retrying (Attempt {attempt + 1}/{max_retries})...")
                    if on_status:
                        try:
                            res = on_status({
                                "type": "retrying",
                                "job_id": unique_id,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "wait_seconds": 2,
                                "message": err_msg,
                            })
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception as cb_err:
                            print(f"[Azure Pool] on_status error: {cb_err}")

                    await asyncio.sleep(2.0)
                    continue
                print(f"[Azure Pool] Generation failed after {max_retries} attempts: {exc}")
                raise HTTPException(
                    status_code=502,
                    detail="Studio portrait generation failed after maximum retries. Please try again shortly.",
                )

            finally:
                if worker:
                    worker.active_job_id = None
                    worker.active_job_start = 0.0
                    if worker.lock.locked():
                        worker.lock.release()
                if waiting_item in self._waiting_jobs:
                    self._waiting_jobs.remove(waiting_item)
                await self._broadcast_queue_updates()

        if last_error:
            raise last_error

        raise HTTPException(status_code=500, detail="Azure generation ended without result.")


azure_image_client = AzureImageClient()
