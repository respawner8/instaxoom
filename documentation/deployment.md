# Deployment & Platform Architecture Guide

This guide documents platform-specific configurations, GPU orchestration, Docker setup, and critical gotchas when deploying **instaXoom** across local machines and cloud environments.

---

## 1. Architecture Overview

```
[ Frontend: Next.js 15 ] (Port 3000)
       │
       ▼ REST / SSE
[ Backend: FastAPI ] (Port 8000) ───► [ Redis ] (Port 6379) ───► Rate Limiter
       │                                  │
       │                                  ▼
       ├──► [ Storage: MinIO / S3 ] ◄─── [ PostgreSQL 16 ] (Port 5432)
       │
       ▼ HTTP / WebSocket
[ Inference: ComfyUI Headless ] (Port 8188)
       │ (GPU Passthrough)
  [ NVIDIA GPU: RTX 4060 8GB / Azure GPU ]
```

---

## 2. Docker & GPU Orchestration Gotchas

### Gotcha #1: Never Bake Model Weights into Docker Images
- **The Mistake:** Copying `.safetensors` or `.gguf` model weights (15GB–25GB) during `docker build`.
- **The Consequence:** Builds take 30+ minutes, docker daemon runs out of disk space, and transferring container images across networks or registries becomes practically impossible.
- **The Rule:** Always mount model weights as host directories via Docker volumes:
  ```yaml
  volumes:
    - ./models:/app/ComfyUI/models
    - shared_uploads:/app/ComfyUI/input
    - shared_outputs:/app/ComfyUI/output
  ```

### Gotcha #2: GPU Passthrough Differences (Windows WSL2 vs. Linux/Azure)

#### Local Windows 10/11 (with Docker Desktop):
- Docker Desktop uses WSL2 (Windows Subsystem for Linux).
- Ensure your host Windows machine has the latest NVIDIA Game Ready or Studio Driver installed.
- **Do NOT** install Linux NVIDIA display drivers inside WSL2; the Windows NVIDIA driver automatically forwards CUDA calls to WSL2.
- In `docker-compose.yml`, the `deploy.resources.reservations.devices` block with `driver: nvidia` and `capabilities: [gpu]` handles passthrough natively.

#### Linux / Azure GPU VM:
- Linux hosts require the **NVIDIA Container Toolkit** to expose the GPU to Docker:
  ```bash
  # 1. Configure the repository
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  # 2. Install and restart docker
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
  ```

### Gotcha #3: PyTorch 2.5 vs. `comfy-kitchen` Typing Annotations
- In PyTorch 2.5+, `torch.library.custom_op` strictly rejects Python 3.9 type annotations formatted as `list[int]` inside custom kernel registrations (`na.py` and `sol_attn.py` in `comfy-kitchen`).
- **Fix:** We include `inference/scripts/patch_comfy_kitchen.py` which converts `list[int]` to `typing.List[int]`. This runs automatically during `docker build` in `inference/Dockerfile`.

---

## 3. Local RTX 4060 (8GB VRAM) Optimization Rules

Flux.1 is a ~12-billion parameter flow-transformer model. In full FP16 precision, it requires ~24GB+ of VRAM. To run it reliably on an 8GB RTX 4060:

1. **Model Format:** Use **Flux.1 [schnell] GGUF Q4_K_S** (`flux1-schnell-Q4_K_S.gguf`, ~6.32 GB).
   - Distilled for **4 steps** of diffusion, generating an image in ~15 seconds on an RTX 4060.
2. **Text Encoders & VAE:**
   - Text encoder: `t5xxl_fp8_e4m3fn.safetensors` (~4.56 GB) + `clip_l.safetensors` (~230 MB).
   - VAE: `ae.safetensors` (~335 MB).
   - ComfyUI automatically offloads T5 from GPU VRAM to system RAM during sampling.
3. **Launch Flags:**
   ```bash
   python main.py --listen 0.0.0.0 --port 8188 --lowvram --disable-cuda-malloc
   ```
   `--lowvram` dynamically manages submodules between GPU VRAM and system RAM, preventing CUDA Out-Of-Memory (OOM) errors.

4. **Inference Verification:**
   Verify the inference container standalone before running the full stack:
   ```bash
   python inference/scripts/test_generate.py
   ```
   Outputs an authentic Instagram 4:5 portrait (`test_output_4x5.png`, 864×1080).

## 4. HP Workstation (32GB VRAM & 128GB RAM) Setup

The HP Workstation has 32GB of dedicated VRAM, eliminating memory bottlenecks and allowing uncompressed full-precision model execution:

1. **Recommended Model:** **Flux.1 [dev] FP8** (`flux1-dev-fp8.safetensors`, ~11.9 GB) with 20 diffusion steps and `FluxGuidance` at 3.5.
2. **Download Full Models:**
   ```powershell
   # PowerShell (Native)
   .\inference\scripts\download_models.ps1 -Preset dev

   # Or Python
   python inference/scripts/download_models.py --preset dev
   ```
3. **Configure Backend:**
   In `.env`:
   ```bash
   FLUX_UNET_NAME=flux1-dev-fp8.safetensors
   DEFAULT_STEPS=20
   DEFAULT_GUIDANCE=3.5
   ```
4. **ComfyUI Launch on HP Workstation:**
   Because 32GB VRAM holds the entire model without CPU offloading:
   ```bash
   python main.py --listen 0.0.0.0 --port 8188 --highvram --fast
   ```
   Generates a full 20-step dev portrait in ~5–8 seconds!

---

## 5. Azure Cloud Deployment

### 1. Azure GPU VM Instance Selection
- **Recommended VM:** `Standard_NC4as_T4_v3` (1x NVIDIA Tesla T4, 16GB VRAM, 4 vCPUs, 28GB RAM) or `Standard_NV4as_v4` / `Standard_NC6s_v3`.
- **Hourly Cost:** Roughly $0.50 – $0.90 per hour.

### 2. Critical Azure Caveat: GPU Core Quotas
- New Azure subscriptions start with a default **quota of 0 GPU vCPUs**.
- **Action Required Before Deploying:**
  1. Go to **Azure Portal** $\rightarrow$ **Subscriptions** $\rightarrow$ **Usage + quotas**.
  2. Filter by your target region (e.g., *East US* or *West US 2*).
  3. Search for `Standard NCasT4_v3 Family vCPUs` or `Standard NVSv4 Family`.
  4. Submit a **Request Quota Increase** to at least 4 vCPUs.

### 3. Idle Cost Protection
- Compute charges accrue as long as the VM is in `Running` state, even if no requests are coming in.
- Set up an **Auto-Shutdown schedule** in Azure Portal (`VM -> Operations -> Auto-shutdown`) to turn off the VM at a set time daily.
- When not actively developing or running campaigns, stop the VM using `Deallocate` so compute billing stops.

---

## 6. Recommended 2-Tier Architecture (Vercel Frontend + HP Workstation Backend & Inference)

Deploying **both Backend (FastAPI) and Inference (ComfyUI) directly on your HP Workstation** is the recommended setup:

```
[ Tier 1: Frontend ] ──────── (Vercel Free Tier Global Edge CDN)
          │
          │ HTTPS (REST API calls)
          ▼
========================================================================
[ HP WORKSTATION (32GB GPU, 128GB RAM) ]
  ├── [ Cloudflare Tunnel (cloudflared) ] ──► Exposes Port 8000 Only
  │
  ├── [ Tier 2: FastAPI Backend Gateway ] (Port 8000)
  │         │
  │         │ Internal Local Communication (Zero Latency / Shared NVMe Volumes)
  │         ▼
  └── [ Inference: ComfyUI Headless ] (Port 8188 - Private, Not Exposed)
            │ (32GB VRAM Passthrough)
            ▼
      [ NVIDIA GPU: Flux.1 [dev] FP8 + PuLID + InsightFace ]
========================================================================
```

### Why This is the Superior Architecture:
1. **$0 / Month Cloud Bill:** Zero compute charges. No need to rent Azure VMs or request GPU quota expansions.
2. **Gigabytes/sec Disk Transfer:** Uploaded selfies and output portraits are read/written directly to the local NVMe drive (`shared_uploads` and `shared_outputs`), avoiding multiple internet file transfers.
3. **Hardened Security:** ComfyUI (Port 8188) is **never exposed to the public internet**; only the FastAPI gateway (Port 8000) is accessible through Cloudflare Tunnel.
4. **Single Tunnel Command:** You only need to run one tunnel command for the entire stack.

### Step-by-Step Setup on HP Workstation:

1. **Clone Repo & Download Models on Workstation:**
   ```powershell
   git clone <repo-url>
   cd instaXoom
   .\inference\scripts\download_models.ps1 -Preset dev
   ```

2. **Launch Backend & ComfyUI with Docker Compose:**
   ```powershell
   docker compose up -d backend inference redis db storage
   ```
   *(Frontend is not started locally because it runs on Vercel).*

3. **Expose the Backend via Cloudflare Tunnel:**
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
   Cloudflare outputs a public HTTPS address (e.g., `https://instaxoom-api.trycloudflare.com`).

4. **Connect Vercel Frontend:**
   - Deploy `frontend/` to Vercel.
   - In Vercel Project Settings $\rightarrow$ **Environment Variables**, set:
     ```bash
     NEXT_PUBLIC_API_URL=https://instaxoom-api.trycloudflare.com
     ```
   - Done! Your Vercel web app now runs on global CDN, while all heavy AI inference and database operations run on your local 32GB GPU.

---

## 7. Alternative: Hybrid 3-Tier Architecture (Vercel + Azure VM + HP Workstation)

If you prefer to keep the FastAPI backend running in the cloud 24/7 on an Azure CPU VM (`Standard_B2s`), you can tunnel ComfyUI on port 8188 to Azure:
```powershell
cloudflared tunnel --url http://127.0.0.1:8188
```
And set `COMFYUI_URL=https://<subdomain>.trycloudflare.com` in the Azure VM `.env`.

---

## 8. Licensing Summary

- **Application Code (instaXoom):** MIT License (full commercial and personal use rights).
- **Flux.1 [schnell]:** Released by Black Forest Labs under **Apache 2.0** (permissive open source, commercial use permitted).
- **Flux.1 [dev]:** Non-commercial research license only.

---

## 9. Native Windows on AMD Ryzen AI Max / Radeon 8060S

This deployment does not require Docker. Radeon 8060S is a `gfx1151` integrated
GPU using shared system memory, not a dedicated NVIDIA GPU. Do not use CUDA
wheels, `nvidia-smi`, or the NVIDIA inference container on this machine.

Use an AMD graphics driver supported by the selected
[ROCm release](https://rocm.docs.amd.com/en/docs-10.0.0/compatibility/compatibility-matrix.html).
The pinned native Windows ROCm packages support Python 3.11. The AMD environment
is created in `ComfyUI\venv-amd`, leaving `ComfyUI\venv` and model files intact.
Do not mix ROCm releases or replace their PyTorch packages with generic wheels.

From the repository root:

```powershell
.\scripts\setup_comfyui_native.ps1 -Gpu amd -Preset dev -ComfyRef v0.35.0 -NoStart
.\scripts\setup_backend_native.ps1 -FaceProvider CPU -AllowedOrigins "https://app.example.com" -NoStart
```

For an existing complete model installation, pass `-SkipModelDownload` to the
ComfyUI setup script. PuLID also needs the RetinaFace and BiSeNet weights in
`ComfyUI\models\facexlib`; both model downloaders include these files.
The release pin avoids unavailable dependencies from a moving development
checkout. Revision changes refuse to overwrite tracked edits.
PuLID is pinned to `7c7362b806c2c0f4bde8742ada9e7cb05b44d249` and receives
`inference\patches\pulid-native-comfy.patch`, which uses ComfyUI's native
block-replacement interface instead of replacing the entire FLUX forward method.

The backend's native `.env` uses these settings:

```dotenv
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_WS_URL=ws://127.0.0.1:8188/ws
PULID_PROVIDER=CPU
REQUIRE_PULID=true
INFERENCE_TIMEOUT_SECONDS=600
SINGLE_GENERATION_AT_A_TIME=true
MAX_PHOTO_BYTES=10485760
FLUX_UNET_NAME=flux1-dev-fp8.safetensors
DEFAULT_STEPS=20
DEFAULT_GUIDANCE=3.5
ALLOWED_ORIGINS=https://app.example.com
```

CPU ONNX Runtime is used for InsightFace. FLUX and the PyTorch portions of
PuLID use the AMD GPU. Do not install `onnxruntime-gpu` alongside `onnxruntime`.
The PuLID fork imports FaceNet even for InsightFace workflows, so setup installs
`facenet-pytorch` without its legacy dependency pins.

Generation uses FLUX-dev FP8 with 20 steps, guidance 3.5, one Euler/simple
sampling pass, PuLID weight 0.85, and an 864 x 1080 output. The API accepts
1 to 5 photos but uses only the first as the reference. It synthesizes a new
image; it does not preserve the original facial pixels.

`REQUIRE_PULID=true` prevents a rejected identity-conditioned prompt from silently
falling back to text-only generation. Responses include `identity_conditioning`
(`pulid` or `none`). The timeout controls the backend's wait only, not a proxy's
timeout. Concurrent generation is limited to one request per API process
(additional requests receive HTTP 429), with a 10 MiB per-photo limit.

Run each process in a separate terminal:

```powershell
.\scripts\run_native_process.ps1 -Component ComfyUI
.\scripts\run_native_process.ps1 -Component Backend
```

These launchers set working directories, bind the servers to loopback, log to
the ignored `runtime` directory, and restart a process after it exits.
Stop the launcher to stop its child. Do not start duplicate launchers.

Optional per-user Windows logon startup:

```powershell
.\scripts\install_native_startup.ps1
```

Pass `-IncludeTunnel` only when automatic public exposure is intended. Remove
all three shortcuts with `.\scripts\install_native_startup.ps1 -IncludeTunnel -Remove`.
Startup requires the Windows user to sign in after a reboot.

For an explicitly unauthenticated tester endpoint, install the official
`cloudflared` Windows package, then run:

```powershell
.\scripts\run_native_process.ps1 -Component Tunnel
```

Only FastAPI is published. The temporary HTTPS hostname appears in
`runtime\tunnel-error.log` and changes when the tunnel restarts. Set the
externally hosted frontend's `NEXT_PUBLIC_API_URL` to that URL before building,
and set backend `ALLOWED_ORIGINS` to the exact frontend origin.

CORS and a temporary URL are not authentication. Anyone with the URL can consume
inference resources; daily quotas remain disabled. Public production use needs
authentication, enforceable quotas and appropriate job/timeout handling.
