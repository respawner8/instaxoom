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
    - ./models/checkpoints:/app/ComfyUI/models/checkpoints
    - ./models/clip:/app/ComfyUI/models/clip
    - ./models/pulid:/app/ComfyUI/models/pulid
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

---

## 3. Local RTX 4060 (8GB VRAM) Optimization Rules

Flux.1 is a ~12-billion parameter flow-transformer model. In full FP16 precision, it requires ~24GB+ of VRAM. To run it reliably on an 8GB RTX 4060 alongside face conditioning:

1. **Model Format:** Use **Flux.1 [schnell] NF4** or **GGUF Q4_K_S / Q4_0**.
   - Flux.1 `schnell` requires only **4 steps** of diffusion, generating an image in 12–20 seconds on an RTX 4060.
2. **Text Encoder Offload:** Use `t5xxl_fp8_e4m3fn.safetensors` instead of FP16 T5. ComfyUI automatically frees T5 from VRAM once the text conditioning phase completes before loading the diffusion transformer.
3. **Face Conditioning (Image-to-Image Likeness):**
   - Use **PuLID for Flux** or **InstantID**.
   - When a user uploads 1 to 5 images, face embedding pooling is performed on the CPU / lightweight InsightFace node before passing the merged vector into the model.
4. **ComfyUI Launch Flags:**
   ```bash
   python main.py --listen 0.0.0.0 --port 8188 --lowvram --disable-cuda-malloc
   ```
   `--lowvram` forces dynamic unloading of idle submodules to system RAM, preventing CUDA Out-Of-Memory (OOM) errors.

---

## 4. Azure Deployment

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

## 5. Licensing Summary

- **Application Code (instaXoom):** MIT License (full commercial and personal use rights).
- **Flux.1 [schnell]:** Released by Black Forest Labs under **Apache 2.0** (permissive open source, commercial use permitted).
- **Flux.1 [dev]:** Non-commercial research license only.
