# instaXoom 📸⚡

> **Daily Trend-Driven AI Image Generation for Instagram**

instaXoom is a full-stack platform designed to transform user selfies into trending aesthetic portraits (e.g., 90s vintage yearbook, cyberpunk, polaroids) optimized for the high-engagement Instagram feed portrait format (4:5).

---

## Documentation

Comprehensive architecture, setup, and deployment guides are available in the [`documentation/`](documentation/) directory:

- 📖 **[Deployment & Platform Guide](documentation/deployment.md)**: Docker gotchas, WSL2 vs. Linux GPU passthrough, 8GB RTX 4060 VRAM tuning, and Azure deployment.
- 🎨 **[Frontend Architecture](documentation/frontend.md)**: Next.js 15 client, Daily Trend UX, 4:5 Instagram portrait framing, and native Web Share API export.
- ⚙️ **[FastAPI & Backend Guide](documentation/fastapi.md)**: API endpoints, Redis sliding-window unauthenticated rate limiting, and ComfyUI client.
- 🧠 **[FLUX Inference & Likeness](documentation/flux.md)**: Flux.1 Schnell NF4/GGUF quantization, 1 vs. 5 photos face pooling, and ComfyUI workflow graphs.

---

## Key Features

- **Daily Curated Trends:** Each day features a unified aesthetic drop (custom prompt tuning, style LoRAs, and framing).
- **Multi-Photo Face Likeness:** Accepts 1 to 5 photos. Uploading 3–5 selfies utilizes face-embedding pooling to cancel lighting inconsistencies and produce high-resemblance results.
- **Instagram-First Export:** Pre-configured 4:5 feed portrait format (maximizing mobile screen area) and native Web Share API integration to post directly to Instagram.
- **Low-VRAM AI Engine:** Headless ComfyUI microservice powered by **Flux.1 [schnell] Q4_K_S GGUF** (~6.3 GB) with CPU-offload optimizations to fit comfortably within an **8GB RTX 4060** or cloud GPU instances.
- **Unauthenticated Rate Limiting:** Sliding-window Redis token bucket granting users 3 free daily generations without requiring upfront signup.
- **Fully Containerized:** Docker Compose orchestration across Next.js, FastAPI, ComfyUI, Redis, PostgreSQL, and MinIO.

---

## Tech Stack

- **Frontend:** Next.js 15 (App Router), React 19, Tailwind CSS, Lucide Icons
- **Backend Gateway:** Python 3.11, FastAPI, Pydantic, WebSockets
- **Inference Engine:** Headless ComfyUI, Flux.1 [schnell] GGUF, ComfyUI-GGUF, PuLID / InsightFace
- **Database & Queue:** PostgreSQL 16, Redis 7 (sliding-window rate limiter)
- **Object Storage:** MinIO (local S3 emulation) / Cloudflare R2 (production)
- **Containerization:** Docker & Docker Compose with NVIDIA GPU passthrough

---

## Project Structure

```
instaXoom/
├── documentation/      # Component-wise technical documentation
│   ├── deployment.md   # GPU setup, Docker gotchas & Azure guide
│   ├── fastapi.md      # Backend endpoints & rate limiting
│   ├── flux.md         # Model specs, face likeness & workflows
│   └── frontend.md     # Web client, aspect ratios & Instagram export
├── backend/            # FastAPI API gateway & rate limiting
├── frontend/           # Next.js 15 web client
├── inference/          # Headless ComfyUI Docker service & workflows
│   └── scripts/        # Model downloader scripts (PowerShell & Python)
├── models/             # Host directory for AI weights (volume mounted)
├── docker-compose.yml  # Multi-service container orchestrator
├── README.md           # Project overview & documentation index
└── LICENSE             # MIT License
```

---

## Quickstart (Local Development)

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/) with WSL2 backend (on Windows)
- NVIDIA GPU with CUDA support (e.g. RTX 4060 8GB) and updated drivers

### 2. Download Model Weights
Download the Flux.1 Schnell GGUF model, text encoders, and VAE (~11.4 GB total) into your `./models` directory:

**On Windows (PowerShell):**
```powershell
.\inference\scripts\download_models.ps1
```

**On Linux / WSL (Python):**
```bash
python inference/scripts/download_models.py
```

### 3. Start the Platform
```bash
docker compose up --build
```

- **Web App:** `http://localhost:3000`
- **Backend API:** `http://localhost:8000`
- **Inference Engine:** `http://localhost:8188`
- **MinIO Storage Console:** `http://localhost:9001`

---

## License

This project is licensed under the [MIT License](LICENSE).
Model weights are subject to their respective licenses (Flux.1 [schnell] is Apache 2.0).
