# ==============================================================================
# instaXoom: Native ComfyUI Setup & Launcher (Windows)
# Clones ComfyUI, configures Python CUDA venv, installs PuLID, downloads models,
# and starts ComfyUI with 32GB VRAM optimization (--highvram --fast).
# ==============================================================================

param (
    [string]$InstallDir = "",
    [ValidateSet("dev", "schnell", "all")][string]$Preset = "dev",
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Join-Path $RootDir "ComfyUI"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " instaXoom: ComfyUI Native Setup (Windows)              " -ForegroundColor Cyan
Write-Host " Target Directory: $InstallDir" -ForegroundColor Cyan
Write-Host " Selected Preset:  $Preset (Flux.1 Dev FP8 + PuLID)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Check prerequisites: Python and Git
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Host "`n[X] Error: Python was not found in PATH." -ForegroundColor Red
    Write-Host "    Please install Python 3.10 or 3.11 from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    Ensure 'Add python.exe to PATH' is checked during installation.`n" -ForegroundColor Yellow
    exit 1
}

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Host "`n[X] Error: Git was not found in PATH." -ForegroundColor Red
    Write-Host "    Please install Git for Windows from https://git-scm.com/download/win`n" -ForegroundColor Yellow
    exit 1
}

# 2. Clone ComfyUI repository if not already present
if (-not (Test-Path $InstallDir)) {
    Write-Host "`n[*] Cloning ComfyUI repository to $InstallDir..." -ForegroundColor Yellow
    & git clone https://github.com/comfyanonymous/ComfyUI.git "$InstallDir"
} else {
    Write-Host "`n[OK] ComfyUI directory already exists at $InstallDir" -ForegroundColor Green
}

# 3. Setup Python virtual environment
$VenvDir = Join-Path $InstallDir "venv"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvDir)) {
    Write-Host "`n[*] Creating Python virtual environment in $VenvDir..." -ForegroundColor Yellow
    & $pythonCmd.Source -m venv "$VenvDir"
    
    Write-Host "[*] Upgrading pip..." -ForegroundColor Yellow
    & "$VenvPython" -m pip install --upgrade pip

    Write-Host "[*] Installing PyTorch with CUDA 12.4..." -ForegroundColor Yellow
    & "$VenvPip" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

    Write-Host "[*] Installing ComfyUI base dependencies..." -ForegroundColor Yellow
    & "$VenvPip" install -r (Join-Path $InstallDir "requirements.txt")
} else {
    Write-Host "[OK] Virtual environment already exists." -ForegroundColor Green
}

# 4. Install PuLID-Flux custom node and face embedding dependencies
$CustomNodesDir = Join-Path $InstallDir "custom_nodes"
$PulidNodeDir = Join-Path $CustomNodesDir "ComfyUI_PuLID_Flux_ll"

if (-not (Test-Path $PulidNodeDir)) {
    Write-Host "`n[*] Cloning ComfyUI-PuLID-Flux-ll custom node..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $CustomNodesDir | Out-Null
    & git clone https://github.com/lldacing/ComfyUI_PuLID_Flux_ll.git "$PulidNodeDir"

    Write-Host "[*] Installing insightface and onnxruntime-gpu for face likeness..." -ForegroundColor Yellow
    & "$VenvPip" install insightface onnxruntime-gpu
} else {
    Write-Host "[OK] PuLID custom node is installed." -ForegroundColor Green
}

# 5. Download model weights
$DownloadScript = Join-Path $RootDir "inference\scripts\download_models.ps1"
$ModelsDir = Join-Path $InstallDir "models"

if (Test-Path $DownloadScript) {
    Write-Host "`n[*] Verifying / Downloading model weights into $ModelsDir..." -ForegroundColor Yellow
    & powershell.exe -ExecutionPolicy Bypass -File "$DownloadScript" -Preset "$Preset" -ModelsDir "$ModelsDir"
} else {
    Write-Host "[!] Download script not found at $DownloadScript. Skipping model download." -ForegroundColor DarkYellow
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " [OK] ComfyUI Native Setup Complete!                    " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

if ($NoStart) {
    Write-Host "Launch command:" -ForegroundColor Cyan
    Write-Host "  & `"$VenvPython`" `"$InstallDir\main.py`" --listen 127.0.0.1 --port 8188 --highvram --fast`n" -ForegroundColor Yellow
    exit 0
}

Write-Host "`n[*] Starting ComfyUI on http://127.0.0.1:8188 (Press Ctrl+C to stop)...`n" -ForegroundColor Green
Set-Location $InstallDir
& "$VenvPython" main.py --listen 127.0.0.1 --port 8188 --highvram --fast
