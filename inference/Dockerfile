FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3.10 \
    python3-pip \
    python3.10-venv \
    curl \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3.10 /usr/bin/python

WORKDIR /app

# Clone ComfyUI core
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI

WORKDIR /app/ComfyUI

# Install PyTorch with CUDA 12.1 support
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install ComfyUI requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install dependencies for Flux & PuLID / InsightFace
RUN pip install --no-cache-dir \
    huggingface-hub \
    onnxruntime-gpu \
    insightface \
    facexlib

# Clone custom nodes for Flux, GGUF & PuLID
RUN git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager.git /app/ComfyUI/custom_nodes/ComfyUI-Manager && \
    git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git /app/ComfyUI/custom_nodes/ComfyUI-GGUF && \
    git clone --depth 1 https://github.com/balazsb/ComfyUI-PuLID-Flux.git /app/ComfyUI/custom_nodes/ComfyUI-PuLID-Flux || true

EXPOSE 8188

# Launch with --lowvram to fit on 8GB RTX 4060
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--lowvram", "--disable-cuda-malloc"]
