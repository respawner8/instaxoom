# ==============================================================================
# instaXoom Model Downloader (PowerShell / Windows Native)
# Downloads Flux.1 Schnell GGUF (Q4_K_S), text encoders, and VAE directly to ./models
# No Python or HuggingFace account/token required.
# ==============================================================================

param (
    [ValidateSet("dev", "schnell", "all")]
    [string]$Preset = "dev"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ModelsDir = Join-Path $RootDir "models"

$CheckpointsDir = Join-Path $ModelsDir "checkpoints"
$UnetDir        = Join-Path $ModelsDir "unet"
$ClipDir        = Join-Path $ModelsDir "clip"
$VaeDir         = Join-Path $ModelsDir "vae"
$PulidDir       = Join-Path $ModelsDir "pulid"
$InsightfaceDir = Join-Path $ModelsDir "insightface\models\antelopev2"

# Ensure target directories exist
New-Item -ItemType Directory -Force -Path $CheckpointsDir, $UnetDir, $ClipDir, $VaeDir, $PulidDir, $InsightfaceDir | Out-Null

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " instaXoom: Downloading Flux.1 + PuLID Face Models      " -ForegroundColor Cyan
Write-Host " Target Directory: $ModelsDir" -ForegroundColor Cyan
Write-Host " Selected Preset:  $Preset (dev, schnell, all)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

function Download-ModelFile {
    param (
        [string]$Name,
        [string]$Url,
        [string]$DestinationPath,
        [string]$ApproxSize,
        [long]$MinBytes = 1048576 # Default 1MB
    )

    if (Test-Path $DestinationPath) {
        $fileSize = (Get-Item $DestinationPath).Length
        if ($fileSize -ge $MinBytes) {
            $displaySize = if ($fileSize -gt 1GB) { "$([math]::round($fileSize / 1GB, 2)) GB" } else { "$([math]::round($fileSize / 1MB, 2)) MB" }
            Write-Host "[✓] $Name already exists ($displaySize). Skipping download." -ForegroundColor Green
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

# 4. UNet Models (Preset: dev, schnell, or all)
if ($Preset -in @("dev", "all")) {
    Download-ModelFile `
        -Name "Flux.1 [dev] FP8 Full Model (flux1-dev-fp8.safetensors)" `
        -Url "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors" `
        -DestinationPath (Join-Path $UnetDir "flux1-dev-fp8.safetensors") `
        -ApproxSize "11.9 GB" `
        -MinBytes 10737418240
}

if ($Preset -in @("schnell", "all")) {
    Download-ModelFile `
        -Name "Flux.1 Schnell Q4_K_S GGUF (flux1-schnell-Q4_K_S.gguf)" `
        -Url "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_K_S.gguf" `
        -DestinationPath (Join-Path $UnetDir "flux1-schnell-Q4_K_S.gguf") `
        -ApproxSize "6.31 GB" `
        -MinBytes 1073741824
}

# 5. PuLID-Flux Model (1.14 GB)
Download-ModelFile `
    -Name "PuLID-Flux Model (pulid_flux_v0.9.1.safetensors)" `
    -Url "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors" `
    -DestinationPath (Join-Path $PulidDir "pulid_flux_v0.9.1.safetensors") `
    -ApproxSize "1.14 GB" `
    -MinBytes 524288000

# 6. EVA02 CLIP Model (1.68 GB)
Download-ModelFile `
    -Name "EVA02 CLIP Model (EVA02_CLIP_L_336_psz14_s6B.pt)" `
    -Url "https://huggingface.co/QuanSun/EVA-CLIP/resolve/main/EVA02_CLIP_L_336_psz14_s6B.pt" `
    -DestinationPath (Join-Path $ClipDir "EVA02_CLIP_L_336_psz14_s6B.pt") `
    -ApproxSize "1.68 GB" `
    -MinBytes 524288000

# 7. InsightFace AntelopeV2 Models
$AntelopeFiles = @(
    @{ Name = "1k3d68.onnx"; Size = "14 MB"; Min = 5242880 },
    @{ Name = "2d106det.onnx"; Size = "5 MB"; Min = 1048576 },
    @{ Name = "genderage.onnx"; Size = "1.3 MB"; Min = 1048576 },
    @{ Name = "glintr100.onnx"; Size = "207 MB"; Min = 52428800 },
    @{ Name = "scrfd_10g_bnkps.onnx"; Size = "17 MB"; Min = 5242880 }
)

foreach ($f in $AntelopeFiles) {
    Download-ModelFile `
        -Name "InsightFace AntelopeV2 $($f.Name)" `
        -Url "https://huggingface.co/Aitrepreneur/insightface/resolve/main/models/antelopev2/$($f.Name)" `
        -DestinationPath (Join-Path $InsightfaceDir $f.Name) `
        -ApproxSize $f.Size `
        -MinBytes $f.Min
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " [✓] All Flux.1, PuLID, and InsightFace models are ready! " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
