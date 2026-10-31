from pydantic_settings import BaseSettings
from typing import List, Literal, Optional
from pathlib import Path
from pydantic import Field


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "instaXoom"
    APP_VERSION: str = "1.0.0"
    COMMIT_SHA: str = "local"
    BUILD_TIME: str = "unknown"
    SECRET_KEY: str = "change-this-to-a-secure-random-secret-key-in-production"

    # OpenTelemetry — Grafana Cloud OTLP export
    # Use the exact env var names Grafana Cloud provides on their OTel setup page.
    # Leave empty to disable (safe for local dev — app starts normally without them).
    # OTEL_EXPORTER_OTLP_ENDPOINT: e.g. "https://otlp-gateway-prod-us-east-0.grafana.net/otlp"
    # OTEL_EXPORTER_OTLP_HEADERS:  e.g. "Authorization=Basic eyJ..."
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_EXPORTER_OTLP_HEADERS: str = ""

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://instaxoom:instaxoom_secret_password@db:5432/instaxoom_db"

    # Authentication & Admin
    GOOGLE_CLIENT_ID: Optional[str] = None
    ADMIN_EMAILS: str = "admin@instaxoom.com"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    @property
    def admin_emails_list(self) -> List[str]:
        return [email.strip().lower() for email in self.ADMIN_EMAILS.split(",") if email.strip()]

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL.strip()
        # Normalize postgres / postgresql schemes to asyncpg
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Redis & Rate Limiting
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    RATE_LIMIT_GENERATIONS_PER_DAY: int = 3
    RATE_LIMIT_WINDOW_SECONDS: int = 86400

    # Storage
    STORAGE_PROVIDER: Literal["local", "azure_blob", "s3"] = "local"
    STORAGE_ENDPOINT: str = "http://storage:9000"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_BUCKET_NAME: str = "instaxoom-images"
    STORAGE_PUBLIC_URL: str = "http://localhost:9000/instaxoom-images"

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = None
    AZURE_STORAGE_ACCOUNT_KEY: Optional[str] = None
    AZURE_STORAGE_CONTAINER_NAME: str = "instaxoom-images"
    AZURE_STORAGE_CUSTOM_DOMAIN: Optional[str] = None

    # ComfyUI
    COMFYUI_HOST: str = "inference"
    COMFYUI_PORT: int = 8188
    COMFYUI_URL: str = "http://inference:8188"
    COMFYUI_WS_URL: str = "ws://inference:8188/ws"
    INFERENCE_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0)
    PULID_PROVIDER: Literal["CPU", "CUDA", "ROCM"] = "CUDA"
    REQUIRE_PULID: bool = False
    SINGLE_GENERATION_AT_A_TIME: bool = False
    MAX_PHOTO_BYTES: int = Field(default=0, ge=0)

    # Model defaults
    FLUX_MODEL_NAME: str = "flux1-schnell-Q4_K_S.gguf"
    FLUX_UNET_NAME: str = "flux1-schnell-Q4_K_S.gguf"
    DEFAULT_STEPS: int = 4
    DEFAULT_GUIDANCE: float = 3.5

    # Engine & Cloud Provider ("flux" or "azure")
    ENGINE: Literal["flux", "azure"] = "flux"

    # Azure AI Foundry / OpenAI Image Settings
    AZURE_AI_ENDPOINT: str = "https://imageeastus2-resource.services.ai.azure.com/openai/v1"
    AZURE_AI_API_KEY: Optional[str] = None
    AZURE_AI_DEPLOYMENT: str = "gpt-image-2.5-flare"
    AZURE_AI_DEPLOYMENTS: Optional[str] = "gpt-image-2.5-flare:2,gpt-image-2.5-sunburst:2,gpt-image-2:2,gpt-image-1.5:9"
    AZURE_AI_API_VERSION: str = "2024-02-01"
    AZURE_RATE_LIMIT_RPM: int = 2

    @property
    def azure_deployments_list(self) -> List[tuple[str, float]]:
        """
        Parses AZURE_AI_DEPLOYMENTS into a priority-ordered list of (deployment_name, rpm).
        Index 0 is highest priority.
        """
        raw = self.AZURE_AI_DEPLOYMENTS or self.AZURE_AI_DEPLOYMENT
        results: List[tuple[str, float]] = []
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            if ":" in item:
                parts = item.split(":", 1)
                name = parts[0].strip()
                try:
                    rpm = float(parts[1].strip())
                except ValueError:
                    rpm = float(self.AZURE_RATE_LIMIT_RPM)
                results.append((name, rpm))
            else:
                results.append((item, float(self.AZURE_RATE_LIMIT_RPM)))
        if not results:
            results.append((self.AZURE_AI_DEPLOYMENT, float(self.AZURE_RATE_LIMIT_RPM)))
        return results

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = [
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ]
        extra = "ignore"


settings = Settings()
