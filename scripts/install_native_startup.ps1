param (
    [switch]$IncludeTunnel,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "run_native_process.ps1"
$StartupDir = [Environment]::GetFolderPath("Startup")
if ([string]::IsNullOrWhiteSpace($StartupDir)) {
    throw "The current user's Windows Startup directory is unavailable."
}

# Store-installed PowerShell paths include a version and can disappear after an update.
$PowerShellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$Components = @("ComfyUI", "Backend")
if ($IncludeTunnel) { $Components += "Tunnel" }

$Shell = New-Object -ComObject WScript.Shell
foreach ($Component in $Components) {
    $ShortcutPath = Join-Path $StartupDir "instaXoom-$Component.lnk"
    if ($Remove) {
        if (Test-Path -LiteralPath $ShortcutPath) {
            Remove-Item -LiteralPath $ShortcutPath
            Write-Host "Removed $ShortcutPath"
        }
        continue
    }
    if (Test-Path -LiteralPath $ShortcutPath) {
        throw "$ShortcutPath already exists. Remove it explicitly before replacing it."
    }
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PowerShellPath
    $Shortcut.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File `"$Runner`" -Component $Component"
    $Shortcut.WorkingDirectory = $RootDir
    $Shortcut.WindowStyle = 7
    $Shortcut.Description = "Run native instaXoom $Component with restart handling and logs."
    $Shortcut.Save()
    Write-Host "Created $ShortcutPath"
}

Write-Host "Startup entries run after this Windows user signs in; no reboot was requested."
