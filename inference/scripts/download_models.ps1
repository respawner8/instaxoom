# ==============================================================================
# instaXoom Model Downloader (PowerShell / Windows Native)
# Downloads Flux.1 Schnell GGUF (Q4_K_S), text encoders, and VAE directly to ./models
# No Python or HuggingFace account/token required.
# ==============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ModelsDir = Join-Path $RootDir "models"

$CheckpointsDir = Join-Path $ModelsDir "checkpoints"
$UnetDir        = Join-Path $ModelsDir "unet"
$ClipDir        = Join-Path $ModelsDir "clip"
$VaeDir         = Join-Path $ModelsDir "vae"
$PulidDir       = Join-Path $ModelsDir "pulid"

# Ensure target directories exist
New-Item -ItemType Directory -Force -Path $CheckpointsDir, $UnetDir, $ClipDir, $VaeDir, $PulidDir | Out-Null

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " instaXoom: Downloading Flux.1 Models for 8GB RTX 4060 " -ForegroundColor Cyan
Write-Host " Target Directory: $ModelsDir" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

function Download-ModelFile {
    param (
        [string]$Name,
        [string]$Url,
        [string]$DestinationPath,
        [string]$ApproxSize
    )

    if (Test-Path $DestinationPath) {
        $fileSize = (Get-Item $DestinationPath).Length
        if ($fileSize -gt 100MB) {
            Write-Host "[✓] $Name already exists ($([math]::round($fileSize / 1GB, 2)) GB). Skipping download." -ForegroundColor Green
            return
        }
    }

    Write-Host "`n>>> Downloading $Name ($ApproxSize)..." -ForegroundColor Yellow
    Write-Host "    Source: $Url" -ForegroundColor DarkGray
    Write-Host "    Dest:   $DestinationPath" -ForegroundColor DarkGray

    # Use curl.exe with follow-redirects (-L) and resume support (-C -)
    & curl.exe -L -C - --progress-bar -o "$DestinationPath" "$Url"

    if ($LASTEXITCODE -eq 0 -and (Test-Path $DestinationPath)) {
        $finalSize = (Get-Item $DestinationPath).Length
        Write-Host "[✓] Successfully downloaded $Name ($([math]::round($finalSize / 1GB, 2)) GB)" -ForegroundColor Green
    } else {
        Write-Host "[X] Download failed for $Name. You can re-run this script to resume." -ForegroundColor Red
    }
}

# 1. Flux VAE (335 MB)
Download-ModelFile `
    -Name "Flux VAE (ae.safetensors)" `
    -Url "https://huggingface.co/shadyman/FLUX.1-schnell_VAE/resolve/main/VAE.safetensors" `
    -DestinationPath (Join-Path $VaeDir "ae.safetensors") `
    -ApproxSize "335 MB"

# 2. CLIP-L Text Encoder (234 MB)
Download-ModelFile `
    -Name "CLIP-L Text Encoder (clip_l.safetensors)" `
    -Url "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" `
    -DestinationPath (Join-Path $ClipDir "clip_l.safetensors") `
    -ApproxSize "234 MB"

# 3. T5-XXL FP8 Text Encoder (4.55 GB)
Download-ModelFile `
    -Name "T5-XXL FP8 Text Encoder (t5xxl_fp8_e4m3fn.safetensors)" `
    -Url "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" `
    -DestinationPath (Join-Path $ClipDir "t5xxl_fp8_e4m3fn.safetensors") `
    -ApproxSize "4.55 GB"

# 4. Flux.1 Schnell Q4_K_S GGUF (6.31 GB)
Download-ModelFile `
    -Name "Flux.1 Schnell Q4_K_S (flux1-schnell-Q4_K_S.gguf)" `
    -Url "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_K_S.gguf" `
    -DestinationPath (Join-Path $UnetDir "flux1-schnell-Q4_K_S.gguf") `
    -ApproxSize "6.31 GB"

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " [✓] All Flux.1 Schnell models and encoders are ready! " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
