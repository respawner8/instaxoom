from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.trends import router as trends_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Fullstack AI Image Generation for Instagram Trends",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(trends_router)


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
