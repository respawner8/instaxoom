# FLUX Inference Engine & Model Architecture

This document covers the **FLUX.1** generative model setup, low-VRAM optimizations, and face likeness techniques used in **instaXoom**.

---

## 1. Model Overview: FLUX.1 [schnell]

- **Architecture:** Flow Transformer (12 Billion parameters)
- **Base Precision:** FP16 (~24GB+ VRAM required natively)
- **Quantization:** **NF4 (BitsAndBytes)** or **GGUF Q4_K_S** (~11GB file size)
- **Sampling Steps:** **4 steps** (schnell is distilled for rapid 4-step convergence)
- **Inference Speed:** ~12–20 seconds per generation on an **NVIDIA RTX 4060 (8GB)**.
- **License:** **Apache 2.0** (permissive open source, commercial use permitted).

---

## 2. Multi-Photo Face Conditioning: 1 Photo vs. 5 Photos

To achieve accurate facial likeness in trend portraits without retraining the model:

```
[ User Uploads 1-5 Photos ]
            │
            ▼
[ InsightFace / PuLID Extractor ] ──► Extracts 512-dim facial identity vectors
            │
            ▼
[ Face Vector Pooling ] ──────────► Computes normalized average across all vectors
            │                        (Eliminates bad angles, lighting, and shadows)
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

1. **Quantized Checkpoint:** Use `flux1-schnell-bnb-nf4.safetensors` loaded via ComfyUI.
2. **Text Encoder Offload:** Text encoding requires CLIP-L and T5-XXL. We use `t5xxl_fp8_e4m3fn.safetensors`. ComfyUI keeps T5 in VRAM only during text encoding and offloads it before loading the transformer blocks.
3. **Launch Flags:**
   ```bash
   python main.py --listen 0.0.0.0 --port 8188 --lowvram --disable-cuda-malloc
   ```

---

## 4. ComfyUI Workflow Graph

The API workflow is stored at `inference/workflows/daily_trend_flux_img2img.json` and consists of:
- **Node 4 (CheckpointLoaderSimple):** Loads Flux.1 Schnell NF4.
- **Node 5 (EmptyLatentImage):** Configured for the standard Instagram 4:5 portrait ratio (864 × 1080).
- **Node 6 & 7 (CLIPTextEncode):** Positive trend prompt and negative prompt.
- **Node 3 (KSampler):** 4 steps, CFG 1.0, Euler sampler, simple scheduler.
- **Node 8 & 9 (VAEDecode & SaveImage):** Decodes latents to high-resolution JPEG and saves to shared output volume.
