# Backend & API Gateway Guide (FastAPI)

This document details the backend architecture, authentication flows, credit management, and API specifications for **instaXoom**.

---

## 1. Tech Stack

- **Framework:** FastAPI 0.111+
- **ASGI Server:** Uvicorn (standard)
- **Validation & Settings:** Pydantic v2 & Pydantic Settings
- **Database:** Neon Serverless PostgreSQL (via SQLAlchemy 2.0 + Asyncpg + SSL)
- **Authentication:** Google OAuth 2.0 (Google Identity Services) + PyJWT
- **Inference Integration:** 
  - Azure AI Foundry (`gpt-image-2.5-flare` via `azure_image_client.py`)
  - Local Headless ComfyUI (`FLUX.1 [schnell]` / `dev` via `comfy_client.py`)
- **Storage:** Shared local volume / MinIO S3 emulation / Azure Cloud

---

## 2. API Endpoints

### 2.1 Authentication & User Profile (`/api/auth`)

#### `POST /api/auth/google`
Verifies a Google ID token from `@react-oauth/google`, registers or logs in the user, claims any pending admin-assigned trial credits, and issues an internal JWT session token.

**Request Body:**
```json
{
  "credential": "<GOOGLE_ID_TOKEN_JWT>"
}
```

**Response (HTTP 200):**
```json
{
  "access_token": "<APP_JWT_ACCESS_TOKEN>",
  "token_type": "bearer",
  "user": {
    "id": "c88f12a3-9b87-4321-9eef-417281bc8901",
    "email": "creator@example.com",
    "name": "Jane Creator",
    "avatar_url": "https://lh3.googleusercontent.com/...",
    "role": "user",
    "credits": 5
  }
}
```

#### `GET /api/auth/me`
Returns the profile and live credit balance of the currently authenticated user.
- **Headers:** `Authorization: Bearer <APP_JWT_ACCESS_TOKEN>`

---

### 2.2 Admin Portal Endpoints (`/api/admin`)
*All admin endpoints require an authenticated user with `role="admin"` (matching `ADMIN_EMAILS`). Non-admins receive `HTTP 403 Forbidden`.*

#### `POST /api/admin/credits/assign`
Grants credits to any user email. If the user has not signed up yet, credits are reserved in `pending_credits` and automatically claimed upon their first Google sign-in.

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "credits": 10,
  "description": "VIP Creator Trial Grant"
}
```

**Response (Existing User):**
```json
{
  "status": "credited_directly",
  "message": "Successfully credited 10 credits to newuser@example.com.",
  "email": "newuser@example.com",
  "new_balance": 15
}
```

**Response (Pre-Signup Invitation):**
```json
{
  "status": "pending_signup",
  "message": "10 trial credits reserved for newuser@example.com. They will automatically receive the credits upon their first Google sign-in.",
  "email": "newuser@example.com",
  "credits": 10
}
```

#### `GET /api/admin/users`
Lists all registered users, roles, credit balances, joined timestamps, and last login dates.

#### `GET /api/admin/pending-credits`
Lists all unclaimed trial credit grants waiting for user signup.

#### `GET /api/admin/transactions`
Returns recent credit transactions across all users for auditing (includes generations and admin grants).

---

### 2.3 Image Generation & Daily Trends (`/api/trends`)

#### `GET /api/trends/today`
Returns the active platform trend, themes catalogue, active engine metadata, and the authenticated user's credit balance.

#### `POST /api/trends/generate`
Submits portrait photo(s) for inference.
- **Requirement:** Authenticated user with `credit.balance >= 1` (returns `HTTP 402 Payment Required` if 0 credits).
- **Credit Deduction:** Deducts **1 credit** upon successful completion and logs a `CreditTransaction`.

**Request (`multipart/form-data`):**
- `photos`: Array of 1 (Azure) or 1–5 (FLUX) image files.
- `aspect_ratio`: `4:5` (locked for Instagram feed).
- `theme_id`: Selected theme ID (e.g. `trend-retro-90s-yearbook`).
- `prompt`: Custom prompt (overrides theme default if modified).
- `gender`: Detected or chosen subject gender (`male` or `female`).
- `engine`: `azure` or `flux`.
- `stream`: `true` for SSE streaming (Azure mode).
- **Headers:** `Authorization: Bearer <APP_JWT_ACCESS_TOKEN>`

**Response (HTTP 200):**
```json
{
  "status": "completed",
  "job_id": "053fbd29-151d-4cc7-8f51-ee3117c00fb7",
  "theme_id": "trend-retro-90s-yearbook",
  "theme_title": "1990s High School Yearbook",
  "aspect_ratio": "4:5",
  "photos_received": 1,
  "image_url": "/api/trends/outputs/instaxoom_azure_a1b2c3d4e5f6.png",
  "remaining_credits": 4,
  "quota": {
    "remaining_generations": 4
  },
  "message": "Successfully generated 4:5 portrait via Azure AI Foundry."
}
```

#### `GET /api/trends/outputs/{filename}`
Serves the generated 4:5 Instagram image file directly from the outputs directory or proxies from ComfyUI. Supports `GET` and `HEAD` requests.
