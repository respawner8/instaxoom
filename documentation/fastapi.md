# Backend & API Gateway Guide (FastAPI)

This document details the backend architecture, rate limiting, and API specifications for **instaXoom**.

---

## 1. Tech Stack

- **Framework:** FastAPI 0.111+
- **ASGI Server:** Uvicorn (standard)
- **Validation & Settings:** Pydantic v2 & Pydantic Settings
- **Cache & Rate Limiting:** Redis 7 (via `redis.asyncio`)
- **Database:** PostgreSQL 16 (via SQLAlchemy + Asyncpg)
- **Inference Integration:** HTTP Client (`httpx`) & WebSocket Client (`websockets`)

---

## 2. API Endpoints

### `GET /api/trends/today`
Returns the active daily trend details, photography tips, and current client generation quota.

**Response:**
```json
{
  "trend": {
    "id": "trend-retro-90s-yearbook",
    "date": "2026-09-13",
    "title": "90s Retro High School Yearbook",
    "tagline": "Transform your portrait into an authentic 1994 vintage yearbook portrait...",
    "aspect_ratios": [
      {"label": "Instagram Feed (4:5)", "value": "4:5", "width": 864, "height": 1080},
      {"label": "Stories / Reels (9:16)", "value": "9:16", "width": 768, "height": 1344},
      {"label": "Square (1:1)", "value": "1:1", "width": 1024, "height": 1024}
    ],
    "default_aspect_ratio": "4:5",
    "hashtags": ["#90sYearbook", "#VintageAesthetic", "#instaXoom"],
    "preview_image_url": "https://..."
  },
  "quota": {
    "remaining_generations": 3,
    "reset_in_seconds": 86400,
    "limit_per_day": 3
  }
}
```

---

### `GET /api/trends/quota`
Returns remaining quota for the requesting client without consuming it.

---

### `POST /api/trends/generate`
Submits 1 to 5 user photos, verifies rate limits, and triggers the ComfyUI inference generation.

**Request:** `multipart/form-data`
- `photos`: Array of 1–5 image files.
- `aspect_ratio`: Target ratio (`4:5`, `9:16`, or `1:1`).
- `custom_caption`: Optional string.
- `x-client-token`: Header identifying client session.

**Response (HTTP 200):**
```json
{
  "status": "completed",
  "job_id": "053fbd29-151d-4cc7-8f51-ee3117c00fb7",
  "prompt_id": "13e915f7-bb7c-4bdd-852f-0f4d1a7011d3",
  "trend_id": "trend-retro-90s-yearbook",
  "aspect_ratio": "4:5",
  "dimensions": {"width": 864, "height": 1080},
  "photos_received": 1,
  "image_url": "/api/trends/outputs/instaXoom_trend_4x5_00002_.png",
  "quota": {
    "remaining_generations": 999,
    "reset_in_seconds": 86400,
    "rate_limit_enabled": false
  },
  "message": "Successfully generated 4:5 Instagram trend portrait."
}
```

---

### `GET /api/trends/outputs/{filename}`
Serves the rendered 4:5 Instagram image file directly from the mounted volume with proxy fallback to ComfyUI. Supports `GET` and `HEAD` requests.

---

## 3. Rate Limiting Logic

- **Local Development:** Rate limiting is bypassed to allow unlimited iterations while testing.
- **Production (Azure):** Sliding window token bucket using Redis key TTLs (`rate_limit:unauth:{client_id}`) granting 3 free generations/day before returning `HTTP 429 Too Many Requests`.

---

## 4. ComfyUI Client (`comfy_client.py`)

- **Prompt Submission:** Converts trend parameters into ComfyUI GGUF graph syntax and posts to `http://inference:8188/prompt`.
- **WebSocket & Polling Tracking:** Tracks node execution progress via WebSockets with an automatic polling fallback on `/history/{prompt_id}`.
- **Output Fetching:** Parses node output filenames from history and serves them via `/api/trends/outputs/{filename}`.
