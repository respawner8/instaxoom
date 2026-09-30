from pydantic_settings import BaseSettings
from typing import List, Literal, Optional
from pydantic import Field


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "instaXoom"
    SECRET_KEY: str = "change-this-to-a-secure-random-secret-key-in-production"

    # OpenTelemetry — Grafana Cloud OTLP export
    # Set both to enable telemetry. Leave empty to disable (safe for local dev).
    # OTEL_ENDPOINT: e.g. "https://otlp-gateway-prod-us-east-0.grafana.net/otlp"
    # OTEL_AUTH_TOKEN: base64("<grafanaInstanceId>:<grafanaApiKey>")
    OTEL_ENDPOINT: str = ""
    OTEL_AUTH_TOKEN: str = ""

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
    STORAGE_PROVIDER: str = "local"
    STORAGE_ENDPOINT: str = "http://storage:9000"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_BUCKET_NAME: str = "instaxoom-images"
    STORAGE_PUBLIC_URL: str = "http://localhost:9000/instaxoom-images"

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
    AZURE_AI_API_VERSION: str = "2024-02-01"
    AZURE_RATE_LIMIT_RPM: int = 2


    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
