import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import init_db
from app.core.telemetry import configure_telemetry
from app.api.trends import router as trends_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.telemetry import router as telemetry_router
from app.api.analytics import router as analytics_router

logger = logging.getLogger(__name__)
SERVER_START_TIME = datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure OpenTelemetry FIRST — before DB init or any IO.
    # This is a no-op when OTEL_ENDPOINT is not set in .env.
    configure_telemetry(app)

    # Startup: Initialize PostgreSQL tables if configured
    try:
        await init_db()
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.warning(f"Database initialization deferred or skipped: {e}")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    description="Fullstack AI Image Generation for Instagram Trends",
    lifespan=lifespan,
)

# CORS configuration - Allow localhost and all deployed frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(trends_router)
app.include_router(telemetry_router)
app.include_router(analytics_router)


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "commit_sha": settings.COMMIT_SHA,
        "build_time": settings.BUILD_TIME,
    }


@app.get("/health")
@app.get("/api/status")
async def health():
    now = datetime.now(timezone.utc)
    uptime_seconds = round((now - SERVER_START_TIME).total_seconds(), 2)
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "commit_sha": settings.COMMIT_SHA,
        "build_time": settings.BUILD_TIME,
        "started_at": SERVER_START_TIME.isoformat(),
        "checked_at": now.isoformat(),
        "uptime_seconds": uptime_seconds,
        "engine": settings.ENGINE,
        "telemetry_enabled": bool(settings.OTEL_EXPORTER_OTLP_ENDPOINT),
    }

