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
CLIP_DIR = MODELS_DIR / "clip"
VAE_DIR = MODELS_DIR / "vae"
PULID_DIR = MODELS_DIR / "pulid"

for d in [CHECKPOINTS_DIR, CLIP_DIR, VAE_DIR, PULID_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MODELS = [
    {
        "name": "Flux VAE (ae.safetensors)",
        "url": "https://huggingface.co/shadyman/FLUX.1-schnell_VAE/resolve/main/VAE.safetensors",
        "path": VAE_DIR / "ae.safetensors",
    },
    {
        "name": "CLIP-L Text Encoder (clip_l.safetensors)",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "path": CLIP_DIR / "clip_l.safetensors",
    },
    {
        "name": "T5-XXL FP8 Text Encoder (t5xxl_fp8_e4m3fn.safetensors)",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
        "path": CLIP_DIR / "t5xxl_fp8_e4m3fn.safetensors",
    },
    {
        "name": "Flux.1 Schnell Q4_K_S GGUF (flux1-schnell-Q4_K_S.gguf)",
        "url": "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_K_S.gguf",
        "path": CHECKPOINTS_DIR / "flux1-schnell-Q4_K_S.gguf",
    },
]


def download_models():
    print(f"[*] Target Directory: {MODELS_DIR}\n")

    for item in MODELS:
        dest = item["path"]
        if dest.exists() and dest.stat().st_size > 100 * 1024 * 1024:
            print(f"[✓] {item['name']} already exists. Skipping.")
            continue

        print(f">>> Downloading {item['name']}...")
        print(f"    URL: {item['url']}")
        try:
            # Using urllib with simple chunked copy
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
    download_models()
