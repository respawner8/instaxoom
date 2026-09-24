# ==============================================================================
# instaXoom: Native FastAPI Backend Setup & Launcher (Windows)
# Configures Python venv, installs requirements, sets up .env, and starts FastAPI.
# ==============================================================================

param (
    [int]$Port = 8000,
    [string]$BindAddress = "127.0.0.1",
    [string]$AllowedOrigins = "http://localhost:3000,http://127.0.0.1:3000",
    [ValidateSet("CPU", "CUDA", "ROCM")][string]$FaceProvider = "CPU",
    [int]$InferenceTimeoutSeconds = 600,
    [switch]$Reload,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RootDir "backend"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " instaXoom: Backend Native Setup (Windows)              " -ForegroundColor Cyan
Write-Host " Backend Directory: $BackendDir" -ForegroundColor Cyan
Write-Host " Target Port:       $Port" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Check Python
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

# 2. Virtual environment setup
$VenvDir = Join-Path $BackendDir "venv"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvUvicorn = Join-Path $VenvDir "Scripts\uvicorn.exe"

if (-not (Test-Path $VenvDir)) {
    Write-Host "`n[*] Creating Python virtual environment in $VenvDir..." -ForegroundColor Yellow
    & $pythonCmd.Source -m venv "$VenvDir"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the backend virtual environment." }
} else {
    Write-Host "`n[OK] Backend virtual environment already exists." -ForegroundColor Green
}

Write-Host "[*] Installing backend dependencies from requirements.txt..." -ForegroundColor Yellow
& "$VenvPython" -m pip install -r (Join-Path $BackendDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Failed to install backend dependencies." }

# 3. Create or verify .env configuration for native mode
$EnvFile = Join-Path $BackendDir ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "`n[*] Creating default native .env file..." -ForegroundColor Yellow
    $envLines = @(
        "# Native Windows Local Configuration",
        "ENVIRONMENT=development",
        "PROJECT_NAME=instaXoom",
        "BACKEND_HOST=$BindAddress",
        "BACKEND_PORT=$Port",
        "ALLOWED_ORIGINS=$AllowedOrigins",
        "",
        "# Local ComfyUI Connection (Native Windows)",
        "COMFYUI_HOST=127.0.0.1",
        "COMFYUI_PORT=8188",
        "COMFYUI_URL=http://127.0.0.1:8188",
        "COMFYUI_WS_URL=ws://127.0.0.1:8188/ws",
        "PULID_PROVIDER=$FaceProvider",
        "REQUIRE_PULID=true",
        "INFERENCE_TIMEOUT_SECONDS=$InferenceTimeoutSeconds",
        "SINGLE_GENERATION_AT_A_TIME=true",
        "MAX_PHOTO_BYTES=10485760",
        "",
        "# Model Configuration",
        "FLUX_UNET_NAME=flux1-dev-fp8.safetensors",
        "DEFAULT_STEPS=20",
        "DEFAULT_GUIDANCE=3.5"
    )
    [System.IO.File]::WriteAllLines($EnvFile, $envLines, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[OK] Created $EnvFile configured for local ComfyUI (127.0.0.1:8188)" -ForegroundColor Green
} else {
    Write-Host "[OK] Found existing .env file." -ForegroundColor Green
}

# 4. Ensure local upload and output folders exist
New-Item -ItemType Directory -Force -Path (Join-Path $BackendDir "uploads"), (Join-Path $BackendDir "outputs") | Out-Null

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " [OK] Backend Native Setup Complete!                    " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

$ServerArgs = @("app.main:app", "--host", $BindAddress, "--port", "$Port")
if ($Reload) { $ServerArgs += "--reload" }

if ($NoStart) {
    Write-Host "Launch command:" -ForegroundColor Cyan
    Write-Host "  cd `"$BackendDir`"" -ForegroundColor Yellow
    Write-Host "  & `"$VenvUvicorn`" $($ServerArgs -join ' ')`n" -ForegroundColor Yellow
    exit 0
}

Write-Host "`n[*] Starting instaXoom Backend on http://127.0.0.1:$Port (Press Ctrl+C to stop)...`n" -ForegroundColor Green
Set-Location $BackendDir
& "$VenvUvicorn" @ServerArgs
if ($LASTEXITCODE -ne 0) { throw "The backend server exited with code $LASTEXITCODE." }
