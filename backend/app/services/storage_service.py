import asyncio
import io
import logging
import os
from typing import Optional, Tuple
import aiofiles
from PIL import Image
from app.core.config import settings

logger = logging.getLogger(__name__)

OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs")


def create_webp_thumbnail(image_bytes: bytes, max_dim: int = 400, quality: int = 85) -> bytes:
    """
    Creates an optimized WebP thumbnail from image bytes.
    The longest dimension will not exceed max_dim.
    Quality 85 provides crisp visual quality at ~25-35 KB.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        rgb_img = img.convert("RGB")
        rgb_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        rgb_img.save(out_buf, format="WEBP", quality=quality, method=4)
        return out_buf.getvalue()


class StorageService:
    """
    Unified Storage Service for instaXoom.
    Uploads generated images to Azure Blob Storage with long-term CDN cache headers
    when configured, and gracefully falls back to local disk storage for development.
    """

    def __init__(self):
        self._blob_service_client = None
        self._container_client = None
        self._initialized = False

    def _init_azure_client(self):
        if self._initialized:
            return self._container_client

        conn_str = settings.AZURE_STORAGE_CONNECTION_STRING
        account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
        account_key = settings.AZURE_STORAGE_ACCOUNT_KEY
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME or "instaxoom-images"

        if not conn_str and not (account_name and account_key):
            self._initialized = True
            logger.info("[Storage] Azure Blob Storage not configured; using local disk storage.")
            return None

        try:
            from azure.storage.blob import BlobServiceClient, PublicAccess

            if conn_str:
                self._blob_service_client = BlobServiceClient.from_connection_string(conn_str)
            else:
                account_url = f"https://{account_name}.blob.core.windows.net"
                self._blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=account_key,
                )

            # Ensure container exists
            self._container_client = self._blob_service_client.get_container_client(container_name)
            try:
                if not self._container_client.exists():
                    self._container_client.create_container(public_access=PublicAccess.Blob)
                    logger.info(f"[Storage] Created Azure Blob container '{container_name}' with public blob access.")
            except Exception as create_err:
                logger.debug(f"[Storage] Container check/create notice: {create_err}")

            self._initialized = True
            logger.info(f"[Storage] Azure Blob Storage initialized for container '{container_name}'.")
            return self._container_client
        except Exception as init_err:
            logger.warning(f"[Storage] Failed to initialize Azure Blob Storage: {init_err}. Falling back to local storage.")
            self._initialized = True
            return None

    def is_azure_configured(self) -> bool:
        """Returns True if Azure Blob Storage is active."""
        container_client = self._init_azure_client()
        return container_client is not None

    async def upload_image(
        self,
        image_bytes: bytes,
        filename: str,
        content_type: str = "image/png",
    ) -> str:
        """
        Saves image bytes and returns the public URL.
        If Azure Blob Storage is configured, uploads the blob with immutable CDN caching
        and returns the full HTTPS blob URL.
        Also persists a local copy in outputs/ for local fallback/development.
        """
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        local_filepath = os.path.join(OUTPUTS_DIR, filename)

        # 1. Always write to local disk as cache/fallback
        try:
            async with aiofiles.open(local_filepath, "wb") as f:
                await f.write(image_bytes)
        except Exception as write_err:
            logger.warning(f"[Storage] Local disk write error: {write_err}")

        # 2. Upload to Azure Blob Storage if available
        container_client = self._init_azure_client()
        if container_client is not None:
            try:
                def _do_upload() -> str:
                    from azure.storage.blob import ContentSettings

                    blob_client = container_client.get_blob_client(filename)
                    # Set immutable 1-year cache headers so CDNs and browsers cache permanently
                    content_settings = ContentSettings(
                        content_type=content_type,
                        cache_control="public, max-age=31536000, immutable",
                    )
                    blob_client.upload_blob(
                        image_bytes,
                        overwrite=True,
                        content_settings=content_settings,
                    )

                    if settings.AZURE_STORAGE_CUSTOM_DOMAIN:
                        domain = settings.AZURE_STORAGE_CUSTOM_DOMAIN.rstrip("/")
                        container = settings.AZURE_STORAGE_CONTAINER_NAME
                        return f"{domain}/{container}/{filename}"
                    return blob_client.url

                blob_url = await asyncio.to_thread(_do_upload)
                logger.info(f"[Storage] Successfully uploaded to Azure Blob: {blob_url}")
                return blob_url
            except Exception as azure_err:
                logger.error(f"[Storage] Azure Blob upload failed: {azure_err}. Using local URL fallback.")

        # 3. Fallback: return relative URL served by FastAPI
        return f"/api/trends/outputs/{filename}"

    async def upload_portrait_with_thumbnail(
        self,
        image_bytes: bytes,
        base_filename: str,
    ) -> Tuple[str, str]:
        """
        Saves the master image in its original lossless format (e.g. PNG) and creates
        a lightweight WebP thumbnail (max 400px, ~30KB) for high-performance gallery views.
        Returns a tuple: (master_image_url, thumbnail_url).
        """
        name_root, _ = os.path.splitext(base_filename)
        thumb_filename = f"{name_root}_thumb.webp"

        # Generate thumbnail off the main event loop
        thumb_bytes = await asyncio.to_thread(create_webp_thumbnail, image_bytes)

        # Upload both in parallel
        master_url, thumb_url = await asyncio.gather(
            self.upload_image(image_bytes, base_filename, content_type="image/png"),
            self.upload_image(thumb_bytes, thumb_filename, content_type="image/webp"),
        )
        return master_url, thumb_url


# Global singleton instance
storage_service = StorageService()
