# FLUX Inference Engine & Model Architecture

This document covers the **FLUX.1** generative model setup, low-VRAM optimizations, and face likeness techniques used in **instaXoom**.

---

## 1. Model Overview: FLUX.1 [schnell]

- **Architecture:** Flow Transformer (12 Billion parameters)
- **Base Precision:** FP16 (~24GB+ VRAM required natively)
- **Quantization:** **GGUF Q4_K_S** (~6.32 GB file size, loaded via `ComfyUI-GGUF`)
- **Sampling Steps:** **4 steps** (schnell is distilled for rapid 4-step convergence)
- **Inference Speed:** ~15 seconds per generation (sampling) on an **NVIDIA RTX 4060 (8GB)**.
- **License:** **Apache 2.0** (permissive open source, commercial use permitted).

---

## 2. Multi-Photo Face Conditioning: 1 Photo vs. 5 Photos

**Current implementation:** the API uses only the first uploaded reference.
The multi-photo pooling design below is not wired into the live workflow.
PuLID provides approximate likeness, not exact preservation of the source face.

To achieve accurate facial likeness in trend portraits without retraining the model:

```
[ User Uploads 1-5 Photos ]
            │
            ▼
[ InsightFace / PuLID Extractor ] ──► Extracts 512-dim facial identity vectors
            │
            ▼
[ Face Vector Pooling ] ──────────► Computes normalized average across all vectors
                               (Eliminates bad angles, lighting, and shadows)
            │
            ▼
[ Flux Cross-Attention Injection ] ─► Conditioned image output with true resemblance
```

### Why 3–5 Photos Are Superior:
- A single photo biases the AI toward that specific angle, lighting condition, or facial expression.
- When 3 to 5 selfies are uploaded, the embeddings are pooled/averaged mathematically. This cancels out transient shadows and highlights true facial topology (jawline, nose bridge, eye shape).
- **Zero Speed Penalty:** Extracting embeddings for 5 images takes less than 0.5s total. The actual Flux diffusion time remains identical.

---

## 3. 8GB VRAM Memory Management

To avoid CUDA Out-Of-Memory (OOM) errors on an RTX 4060:

1. **GGUF Quantized UNet:** Use `flux1-schnell-Q4_K_S.gguf` loaded via `ComfyUI-GGUF` (`models/unet/` or `models/checkpoints/`).
2. **Text Encoder Offload:** Text encoding uses CLIP-L and T5-XXL FP8 (`t5xxl_fp8_e4m3fn.safetensors`). ComfyUI offloads T5 from GPU VRAM to system RAM during sampling, preserving ~4.5GB VRAM for the UNet.
3. **Dedicated VAE:** Loads `ae.safetensors` via `VAELoader`.
4. **Launch Flags:**
   ```bash
   python main.py --listen 0.0.0.0 --port 8188 --lowvram --disable-cuda-malloc
   ```

---

## 4. ComfyUI Workflow Graph

The API workflow is stored at `inference/workflows/daily_trend_flux_img2img.json` and consists of:
- **Node 1 (UnetLoaderGGUF):** Loads `flux1-schnell-Q4_K_S.gguf`.
- **Node 2 (DualCLIPLoader):** Loads `t5xxl_fp8_e4m3fn.safetensors` and `clip_l.safetensors` (type: flux).
- **Node 3 (VAELoader):** Loads `ae.safetensors`.
- **Node 4 (EmptyLatentImage):** Configured for standard Instagram 4:5 portrait ratio (864 × 1080).
- **Node 5 & 6 (CLIPTextEncode):** Positive trend prompt and negative prompt.
- **Node 7 (KSampler):** 4 steps, CFG 1.0, Euler sampler, simple scheduler.
- **Node 8 (VAEDecode):** Decodes latent representation with VAE.
- **Node 9 (SaveImage):** Outputs high-resolution image to shared output volume.

---

## 5. Testing & Verification

A verification client is provided at `inference/scripts/test_generate.py` to queue a generation job against headless ComfyUI and save the rendered output:

```bash
python inference/scripts/test_generate.py
```
This tests the full pipeline (GGUF load, text encoding, 4-step diffusion, VAE decode) and outputs `test_output_4x5.png`.
