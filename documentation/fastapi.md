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
  "status": "queued",
  "job_id": "8f3b23c9-d23b-4f91-88f1-c5de736a4392",
  "trend_id": "trend-retro-90s-yearbook",
  "aspect_ratio": "4:5",
  "dimensions": {"width": 864, "height": 1080},
  "photos_received": 3,
  "quota": {
    "remaining_generations": 2,
    "reset_in_seconds": 86340
  },
  "estimated_duration_seconds": 15
}
```

---

## 3. Unauthenticated Rate Limiting Logic

To enable guest usage while preventing API abuse:
1. **Client Identification:** The system inspects `X-Client-Token` (UUID stored in the user's browser) with a fallback to `X-Forwarded-For` / client IP.
2. **Sliding Window with Redis:**
   - Keys are formatted as `rate_limit:unauth:{client_id}`.
   - On the first request, Redis stores count `1` with a TTL of `86400` seconds (24 hours).
   - Subsequent requests increment the counter until the daily limit (default: 3) is hit.
   - Once exhausted, the API returns `HTTP 429 Too Many Requests` with the remaining seconds until reset.

---

## 4. ComfyUI Client (`comfy_client.py`)

- **Prompt Submission:** Converts trend parameters and uploaded user photos into ComfyUI graph syntax and posts to `http://inference:8188/prompt`.
- **WebSocket Tracking:** Listens to `ws://inference:8188/ws` for real-time node execution progress.
- **Output Fetching:** Retrieves the rendered image filename and exposes it via public CDN or MinIO storage.
