from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "instaXoom"
    SECRET_KEY: str = "change-this-to-a-secure-random-secret-key-in-production"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://instaxoom:instaxoom_secret_password@db:5432/instaxoom_db"

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

    # Model defaults
    FLUX_MODEL_NAME: str = "flux1-schnell-nf4.safetensors"
    DEFAULT_STEPS: int = 4
    DEFAULT_GUIDANCE: float = 3.5

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
