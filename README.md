# instaXoom 📸⚡

> **Daily Trend-Driven AI Image Generation for Instagram**

instaXoom is a full-stack platform designed to transform user selfies into trending aesthetic portraits (e.g., 90s vintage yearbook, cyberpunk, polaroids) optimized for the high-engagement Instagram feed portrait format (4:5).

---

## Documentation

Comprehensive architecture, setup, and deployment guides are available in the [`documentation/`](documentation/) directory:

- 🔐 **[Auth & Credit System Architecture](documentation/auth_and_credit_system.md)**: Google OAuth 2.0, Neon PostgreSQL ER schema, credit deduction rules, and pricing economics ($0.50/credit).
- ☁️ **[Azure Cloud Deployment Guide](documentation/azure_deployment.md)**: Azure Cloud Shell, ACR container builds, Azure Container Apps deployment, and Vercel configuration.
- 📖 **[Deployment & Platform Guide](documentation/deployment.md)**: Docker gotchas, WSL2 vs. Linux GPU passthrough, 8GB RTX 4060 VRAM tuning, and HP Workstation setup.
- 🎨 **[Frontend Architecture](documentation/frontend.md)**: Next.js 15 client, Daily Trend UX, Admin Portal (`/admin`), and 4:5 Instagram portrait framing.
- ⚙️ **[FastAPI & Backend Guide](documentation/fastapi.md)**: API specifications, auth endpoints, admin credit assignment, and ComfyUI client.
- 🧠 **[FLUX Inference & Likeness](documentation/flux.md)**: Flux.1 Schnell NF4/GGUF quantization, 1 vs. 5 photos face pooling, and ComfyUI workflow graphs.

---

## Key Features

- **Google Authentication & Role Authorization:** Seamless sign-in via Google OAuth with automatic admin role detection and redirection to `/admin`.
- **Neon Serverless PostgreSQL:** Managed persistence for user accounts, credit balances, pending invitations, and immutable transaction audit logs.
- **Credit & Licensing System:** 1 image = 1 credit. Admins can assign trial credits to any email (even prior to signup with automatic activation on first login).
- **Daily Curated Trends:** Each day features a unified aesthetic drop (custom prompt tuning, style LoRAs, and framing).
- **Dual Inference Engines:** Supports local **FLUX.1 [schnell] / [dev]** via ComfyUI with PuLID face likeness and cloud **Azure AI Foundry** (`gpt-image-2.5-flare`).
- **Instagram-First Export:** Pre-configured 4:5 feed portrait format (maximizing mobile screen area) and native Web Share API integration to post directly to Instagram.
- **Fully Containerized:** Docker Compose orchestration across Next.js, FastAPI, ComfyUI, Redis, PostgreSQL, and MinIO.

---

## Tech Stack

- **Frontend:** Next.js 15 (App Router), React 19, Tailwind CSS, `@react-oauth/google`, Lucide Icons
- **Backend Gateway:** Python 3.11, FastAPI, Pydantic, SQLAlchemy 2.0 (asyncpg), PyJWT, Google Auth
- **Database:** Neon Serverless PostgreSQL (cloud) / PostgreSQL 16 (local Docker)
- **Inference Engines:** Headless ComfyUI (FLUX.1 + PuLID) & Azure AI Foundry (`gpt-image-2.5-flare`)

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

The steps below use Docker and NVIDIA. For a Docker-free deployment on AMD
Radeon 8060S, follow the [native Windows AMD guide](documentation/deployment.md#9-native-windows-on-amd-ryzen-ai-max--radeon-8060s).

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
