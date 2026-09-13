"""
Model downloader script for instaXoom inference engine.
Downloads Flux.1 Schnell NF4 (low VRAM friendly) and text encoders directly
to the host ./models folder.
"""

import os
from pathlib import Path
from huggingface_hub import hf_hub_download

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"

CHECKPOINTS_DIR = MODELS_DIR / "checkpoints"
CLIP_DIR = MODELS_DIR / "clip"
VAE_DIR = MODELS_DIR / "vae"
PULID_DIR = MODELS_DIR / "pulid"

for d in [CHECKPOINTS_DIR, CLIP_DIR, VAE_DIR, PULID_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def download_models():
    print(f"[*] Downloading Flux & Face models into: {MODELS_DIR}")

    # 1. Flux.1 Schnell NF4 (Quantized, ~11GB, fits in 8GB VRAM)
    print("\n[1/3] Downloading Flux.1 Schnell NF4 Checkpoint...")
    try:
        hf_hub_download(
            repo_id="lllyasviel/flux1-schnell-bnb-nf4",
            filename="flux1-schnell-bnb-nf4.safetensors",
            local_dir=str(CHECKPOINTS_DIR),
        )
        print("[+] Checkpoint downloaded successfully.")
    except Exception as e:
        print(f"[-] Note: If access is restricted, login via `huggingface-cli login`: {e}")

    # 2. Text Encoders: Clip-L and T5xxl FP8
    print("\n[2/3] Downloading Text Encoders (Clip-L & T5 FP8)...")
    try:
        hf_hub_download(
            repo_id="comfyanonymous/flux_text_encoders",
            filename="t5xxl_fp8_e4m3fn.safetensors",
            local_dir=str(CLIP_DIR),
        )
        hf_hub_download(
            repo_id="comfyanonymous/flux_text_encoders",
            filename="clip_l.safetensors",
            local_dir=str(CLIP_DIR),
        )
        print("[+] Text encoders downloaded successfully.")
    except Exception as e:
        print(f"[-] Download error: {e}")

    # 3. Flux VAE
    print("\n[3/3] Downloading Flux VAE...")
    try:
        hf_hub_download(
            repo_id="black-forest-labs/FLUX.1-schnell",
            filename="ae.safetensors",
            local_dir=str(VAE_DIR),
        )
        print("[+] VAE downloaded successfully.")
    except Exception as e:
        print(f"[-] Download error: {e}")

    print("\n[✓] Model setup script finished.")


if __name__ == "__main__":
    download_models()
