param (
    [Parameter(Mandatory = $true)]
    [ValidateSet("ComfyUI", "Backend", "Tunnel")]
    [string]$Component,
    [ValidateSet("amd", "nvidia")]
    [string]$Gpu = "amd"
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $RootDir "runtime"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

switch ($Component) {
    "ComfyUI" {
        $WorkingDir = Join-Path $RootDir "ComfyUI"
        $VenvName = if ($Gpu -eq "amd") { "venv-amd" } else { "venv" }
        $Executable = Join-Path $WorkingDir "$VenvName\Scripts\python.exe"
        $ProcessArgs = @("main.py", "--listen", "127.0.0.1", "--port", "8188")
        $Port = 8188
    }
    "Backend" {
        $WorkingDir = Join-Path $RootDir "backend"
        $Executable = Join-Path $WorkingDir "venv\Scripts\python.exe"
        $ProcessArgs = @(
            "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
            "--port", "8000", "--limit-concurrency", "8", "--timeout-keep-alive", "5"
        )
        $Port = 8000
    }
    "Tunnel" {
        $WorkingDir = $RootDir
        $Command = Get-Command cloudflared -ErrorAction SilentlyContinue
        $Executable = if ($Command) { $Command.Source } else {
            @(
                (Join-Path $env:ProgramFiles "cloudflared\cloudflared.exe"),
                (Join-Path ${env:ProgramFiles(x86)} "cloudflared\cloudflared.exe")
            ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        }
        $ProcessArgs = @(
            "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8000",
            "--metrics", "127.0.0.1:20246"
        )
        $Port = 20246
    }
}

if (-not $Executable -or -not (Test-Path -LiteralPath $Executable)) {
    throw "The executable for $Component is missing. Complete its native setup first."
}

$Listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
if ($Listeners | Where-Object { $_.Port -eq $Port }) {
    throw "Port $Port is already in use. Stop the existing $Component process before starting another."
}

$LogName = $Component.ToLowerInvariant()
$OutputLog = Join-Path $RuntimeDir "$LogName.log"
$ErrorLog = Join-Path $RuntimeDir "$LogName-error.log"
$SupervisorLog = Join-Path $RuntimeDir "$LogName-supervisor.log"
$PidFile = Join-Path $RuntimeDir "$LogName.pid"

while ($true) {
    $Process = $null
    try {
        $Process = Start-Process -FilePath $Executable -ArgumentList $ProcessArgs `
            -WorkingDirectory $WorkingDir -NoNewWindow -PassThru `
            -RedirectStandardOutput $OutputLog -RedirectStandardError $ErrorLog
        $Process.Id | Set-Content -LiteralPath $PidFile
        "$(Get-Date -Format o) Started $Component PID $($Process.Id)." | Add-Content -LiteralPath $SupervisorLog
        $Process.WaitForExit()
        "$(Get-Date -Format o) $Component exited with code $($Process.ExitCode); retrying in 10 seconds." |
            Add-Content -LiteralPath $SupervisorLog
    } finally {
        if ($Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id
        }
        if (Test-Path -LiteralPath $PidFile) {
            Remove-Item -LiteralPath $PidFile
        }
    }
    Start-Sleep -Seconds 10
}
