"""
Model downloader script for instaXoom inference engine.
Downloads Flux.1 Schnell GGUF (low VRAM friendly), text encoders, and VAE
directly to the host ./models folder.
"""

import os
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"

CHECKPOINTS_DIR = MODELS_DIR / "checkpoints"
UNET_DIR = MODELS_DIR / "unet"
CLIP_DIR = MODELS_DIR / "clip"
VAE_DIR = MODELS_DIR / "vae"
PULID_DIR = MODELS_DIR / "pulid"
INSIGHTFACE_DIR = MODELS_DIR / "insightface" / "models" / "antelopev2"

for d in [CHECKPOINTS_DIR, UNET_DIR, CLIP_DIR, VAE_DIR, PULID_DIR, INSIGHTFACE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MODELS = [
    {
        "name": "Flux VAE (ae.safetensors)",
        "url": "https://huggingface.co/shadyman/FLUX.1-schnell_VAE/resolve/main/VAE.safetensors",
        "path": VAE_DIR / "ae.safetensors",
        "min_size_mb": 100,
    },
    {
        "name": "CLIP-L Text Encoder (clip_l.safetensors)",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "path": CLIP_DIR / "clip_l.safetensors",
        "min_size_mb": 100,
    },
    {
        "name": "T5-XXL FP8 Text Encoder (t5xxl_fp8_e4m3fn.safetensors)",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
        "path": CLIP_DIR / "t5xxl_fp8_e4m3fn.safetensors",
        "min_size_mb": 1000,
    },
    {
        "name": "Flux.1 [dev] FP8 Full Model (flux1-dev-fp8.safetensors)",
        "url": "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors",
        "path": UNET_DIR / "flux1-dev-fp8.safetensors",
        "min_size_mb": 10000,
        "preset": "dev",
    },
    {
        "name": "Flux.1 Schnell Q4_K_S GGUF (flux1-schnell-Q4_K_S.gguf)",
        "url": "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_K_S.gguf",
        "path": UNET_DIR / "flux1-schnell-Q4_K_S.gguf",
        "min_size_mb": 1000,
        "preset": "schnell",
    },
    {
        "name": "PuLID-Flux Model (pulid_flux_v0.9.1.safetensors)",
        "url": "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors",
        "path": PULID_DIR / "pulid_flux_v0.9.1.safetensors",
        "min_size_mb": 500,
    },
    {
        "name": "EVA02 CLIP Model (EVA02_CLIP_L_336_psz14_s6B.pt)",
        "url": "https://huggingface.co/QuanSun/EVA-CLIP/resolve/main/EVA02_CLIP_L_336_psz14_s6B.pt",
        "path": CLIP_DIR / "EVA02_CLIP_L_336_psz14_s6B.pt",
        "min_size_mb": 500,
    },
    # InsightFace AntelopeV2 models
    {
        "name": "InsightFace AntelopeV2 1k3d68.onnx",
        "url": "https://huggingface.co/Aitrepreneur/insightface/resolve/main/models/antelopev2/1k3d68.onnx",
        "path": INSIGHTFACE_DIR / "1k3d68.onnx",
        "min_size_mb": 5,
    },
    {
        "name": "InsightFace AntelopeV2 2d106det.onnx",
        "url": "https://huggingface.co/Aitrepreneur/insightface/resolve/main/models/antelopev2/2d106det.onnx",
        "path": INSIGHTFACE_DIR / "2d106det.onnx",
        "min_size_mb": 1,
    },
    {
        "name": "InsightFace AntelopeV2 genderage.onnx",
        "url": "https://huggingface.co/Aitrepreneur/insightface/resolve/main/models/antelopev2/genderage.onnx",
        "path": INSIGHTFACE_DIR / "genderage.onnx",
        "min_size_mb": 1,
    },
    {
        "name": "InsightFace AntelopeV2 glintr100.onnx",
        "url": "https://huggingface.co/Aitrepreneur/insightface/resolve/main/models/antelopev2/glintr100.onnx",
        "path": INSIGHTFACE_DIR / "glintr100.onnx",
        "min_size_mb": 50,
    },
    {
        "name": "InsightFace AntelopeV2 scrfd_10g_bnkps.onnx",
        "url": "https://huggingface.co/Aitrepreneur/insightface/resolve/main/models/antelopev2/scrfd_10g_bnkps.onnx",
        "path": INSIGHTFACE_DIR / "scrfd_10g_bnkps.onnx",
        "min_size_mb": 5,
    },
]


import argparse


def download_models(preset: str = "dev"):
    print(f"[*] Target Directory: {MODELS_DIR}")
    print(f"[*] Selected Preset:  {preset} (options: dev, schnell, all)\n")

    for item in MODELS:
        item_preset = item.get("preset", "common")
        if item_preset not in ("common", preset) and preset != "all":
            continue

        dest = item["path"]
        min_bytes = item.get("min_size_mb", 1) * 1024 * 1024
        if dest.exists() and dest.stat().st_size >= min_bytes:
            print(f"[✓] {item['name']} already exists. Skipping.")
            continue

        print(f">>> Downloading {item['name']}...")
        print(f"    URL: {item['url']}")
        try:
            req = urllib.request.Request(item["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response, open(dest, "wb") as out_file:
                total_size = int(response.info().get("Content-Length", 0))
                downloaded = 0
                chunk_size = 1024 * 1024 * 4  # 4MB chunks
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r    Progress: {percent:.1f}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)", end="")
            print(f"\n[✓] Finished {item['name']}\n")
        except Exception as e:
            print(f"\n[X] Error downloading {item['name']}: {e}\n")

    print("[✓] Model setup process finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="instaXoom Model Downloader")
    parser.add_argument(
        "--preset",
        choices=["dev", "schnell", "all"],
        default="dev",
        help="Select model preset: 'dev' (Full Flux.1 Dev FP8 for HP Workstation 32GB), 'schnell' (4-bit GGUF for 8GB GPU), or 'all'",
    )
    args = parser.parse_args()
    download_models(preset=args.preset)
