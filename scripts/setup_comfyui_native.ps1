# ==============================================================================
# instaXoom: Native ComfyUI Setup & Launcher (Windows)
# Configures an isolated NVIDIA or AMD gfx1151 runtime and PuLID dependencies.
# ==============================================================================

param (
    [string]$InstallDir = "",
    [ValidateSet("dev", "schnell", "all")][string]$Preset = "dev",
    [ValidateSet("nvidia", "amd")][string]$Gpu = "nvidia",
    [string]$ComfyRef = "v0.35.0",
    [switch]$SkipModelDownload,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir

function Invoke-Checked {
    param ([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

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
    if ($LASTEXITCODE -ne 0) { throw "Failed to clone ComfyUI." }
} else {
    Write-Host "`n[OK] ComfyUI directory already exists at $InstallDir" -ForegroundColor Green
}

if (-not [string]::IsNullOrWhiteSpace($ComfyRef)) {
    $TrackedChanges = & git -C "$InstallDir" status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the ComfyUI checkout." }
    if ($TrackedChanges) { throw "ComfyUI has tracked modifications; refusing to change its revision." }
    Invoke-Checked "git" @("-C", $InstallDir, "checkout", "--detach", $ComfyRef)
}

# 3. Setup Python virtual environment
$VenvName = if ($Gpu -eq "amd") { "venv-amd" } else { "venv" }
$VenvDir = Join-Path $InstallDir $VenvName
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvDir)) {
    Write-Host "`n[*] Creating Python virtual environment in $VenvDir..." -ForegroundColor Yellow
    Invoke-Checked $pythonCmd.Source @("-m", "venv", $VenvDir)
} else {
    Write-Host "[OK] Virtual environment found at $VenvDir" -ForegroundColor Green
}

Invoke-Checked $VenvPython @("-m", "pip", "install", "--upgrade", "pip")
$ConstraintArgs = @()
if ($Gpu -eq "amd") {
    $AmdRequirements = Join-Path $RootDir "inference\requirements-amd-windows.txt"
    $ConstraintArgs = @("-c", (Join-Path $RootDir "inference\constraints-amd-windows.txt"))
    Write-Host "[*] Installing ROCm PyTorch for Radeon gfx1151..." -ForegroundColor Yellow
    Invoke-Checked $VenvPython @("-m", "pip", "install", "-r", $AmdRequirements)
} else {
    Write-Host "[*] Installing NVIDIA PyTorch..." -ForegroundColor Yellow
    Invoke-Checked $VenvPython @("-m", "pip", "install", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu130")
}

Write-Host "[*] Installing ComfyUI base dependencies..." -ForegroundColor Yellow
Invoke-Checked $VenvPython (@("-m", "pip", "install", "-r", (Join-Path $InstallDir "requirements.txt")) + $ConstraintArgs)

# 4. Install PuLID-Flux custom node and face embedding dependencies
$CustomNodesDir = Join-Path $InstallDir "custom_nodes"
$PulidNodeDir = Join-Path $CustomNodesDir "ComfyUI_PuLID_Flux_ll"
$PulidRef = "7c7362b806c2c0f4bde8742ada9e7cb05b44d249"

if (-not (Test-Path $PulidNodeDir)) {
    Write-Host "`n[*] Cloning ComfyUI-PuLID-Flux-ll custom node..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $CustomNodesDir | Out-Null
    & git clone https://github.com/lldacing/ComfyUI_PuLID_Flux_ll.git "$PulidNodeDir"
    if ($LASTEXITCODE -ne 0) { throw "Failed to clone PuLID." }
} else {
    Write-Host "[OK] PuLID custom node is installed." -ForegroundColor Green
}

$PulidHead = & git -C "$PulidNodeDir" rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw "Could not inspect the PuLID checkout." }
if ($PulidHead -ne $PulidRef) {
    $PulidChanges = & git -C "$PulidNodeDir" status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect PuLID modifications." }
    if ($PulidChanges) { throw "PuLID has tracked modifications; refusing to change its revision." }
    Invoke-Checked "git" @("-C", $PulidNodeDir, "checkout", "--detach", $PulidRef)
}

$PulidPatch = Join-Path $RootDir "inference\patches\pulid-native-comfy.patch"
& git -C "$PulidNodeDir" apply --reverse --check "$PulidPatch" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] PuLID native ComfyUI patch is already applied." -ForegroundColor Green
} else {
    Invoke-Checked "git" @("-C", $PulidNodeDir, "apply", "--check", $PulidPatch)
    Invoke-Checked "git" @("-C", $PulidNodeDir, "apply", $PulidPatch)
}

Write-Host "[*] Installing PuLID dependencies..." -ForegroundColor Yellow
$NodeRequirements = Join-Path $PulidNodeDir "requirements.txt"
if ($Gpu -eq "amd") {
    # ONNX Runtime's CUDA package does not provide native Windows ROCm support.
    Invoke-Checked $VenvPython @("-m", "pip", "uninstall", "-y", "onnxruntime-gpu")
    $CpuRequirements = [System.IO.Path]::GetTempFileName()
    try {
        $CpuLines = Get-Content $NodeRequirements | Where-Object { $_ -notmatch "^\s*onnxruntime-gpu\b" }
        [System.IO.File]::WriteAllLines($CpuRequirements, $CpuLines, [System.Text.UTF8Encoding]::new($false))
        Invoke-Checked $VenvPython (@("-m", "pip", "install", "-r", $CpuRequirements) + $ConstraintArgs)
        Invoke-Checked $VenvPython @("-m", "pip", "install", "--force-reinstall", "--no-deps", "onnxruntime")
    } finally {
        Remove-Item -LiteralPath $CpuRequirements
    }
} else {
    Invoke-Checked $VenvPython @("-m", "pip", "install", "-r", $NodeRequirements)
}
# The PuLID fork imports FaceNet, but FaceNet's legacy dependency pins replace PyTorch.
Invoke-Checked $VenvPython @("-m", "pip", "install", "--no-deps", "facenet-pytorch==2.6.0")

# 5. Download model weights
$DownloadScript = Join-Path $RootDir "inference\scripts\download_models.ps1"
$ModelsDir = Join-Path $InstallDir "models"

if (-not $SkipModelDownload -and (Test-Path $DownloadScript)) {
    Write-Host "`n[*] Verifying / Downloading model weights into $ModelsDir..." -ForegroundColor Yellow
    & powershell.exe -ExecutionPolicy Bypass -File "$DownloadScript" -Preset "$Preset" -ModelsDir "$ModelsDir"
    if ($LASTEXITCODE -ne 0) { throw "Model download failed." }
} elseif (-not $SkipModelDownload) {
    throw "Download script not found at $DownloadScript."
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " [OK] ComfyUI Native Setup Complete!                    " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

if ($NoStart) {
    Write-Host "Launch command:" -ForegroundColor Cyan
    Write-Host "  cd `"$InstallDir`"" -ForegroundColor Yellow
    Write-Host "  & `"$VenvPython`" main.py --listen 127.0.0.1 --port 8188`n" -ForegroundColor Yellow
    exit 0
}

Write-Host "`n[*] Starting ComfyUI on http://127.0.0.1:8188 (Press Ctrl+C to stop)...`n" -ForegroundColor Green
Set-Location $InstallDir
Invoke-Checked $VenvPython @("main.py", "--listen", "127.0.0.1", "--port", "8188")
