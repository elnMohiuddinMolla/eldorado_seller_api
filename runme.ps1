<#
.SYNOPSIS
    One-click start for the Eldorado Seller API Tool.

.DESCRIPTION
    1. Creates .venv (Python 3.11+) if it is missing.
    2. Installs / updates the tool into .venv when pyproject.toml changed.
    3. Creates .env from .env.example if it is missing, and stops so you can fill it in.
    4. Starts the app: settings page + bot (bot starts PAUSED), or the page only with -Mode ui.

    Nothing is sent to Eldorado until you press RUN on the settings page.
    The script never prints the contents of .env.

.EXAMPLE
    .\runme.ps1                  # page + bot (eldorado app)
    .\runme.ps1 -Mode ui         # page only, no bot
    .\runme.ps1 -Port 9000 -NoBrowser
    .\runme.ps1 -Reinstall       # force pip install again
#>
[CmdletBinding()]
param(
    [ValidateSet('app', 'ui')]
    [string]$Mode = 'app',
    [ValidateRange(1024, 65535)]
    [int]$Port = 0,
    [switch]$NoBrowser,
    [switch]$Reinstall
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Stop-WithError([string]$msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
    if ($Host.Name -eq 'ConsoleHost') { Read-Host 'Press Enter to close' | Out-Null }
    exit 1
}

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$eldoradoExe = Join-Path $PSScriptRoot '.venv\Scripts\eldorado.exe'
$stampFile = Join-Path $PSScriptRoot '.venv\.installed-stamp'

# --- 1. Virtual environment -------------------------------------------------
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Step 'Creating virtual environment (.venv)'
    $basePython = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $basePython = @('py', '-3')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $basePython = @('python')
    } else {
        Stop-WithError 'Python 3.11+ not found. Install it from https://www.python.org/downloads/'
    }
    $exe = $basePython[0]
    $pyArgs = @($basePython | Select-Object -Skip 1)

    & $exe @pyArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Python 3.11 or newer is required.' }

    & $exe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Could not create .venv' }
    $Reinstall = $true
}

# --- 2. Install / update ----------------------------------------------------
$pyprojectTime = (Get-Item -LiteralPath (Join-Path $PSScriptRoot 'pyproject.toml')).LastWriteTimeUtc
$needInstall = $Reinstall -or -not (Test-Path -LiteralPath $eldoradoExe) -or -not (Test-Path -LiteralPath $stampFile)
if (-not $needInstall) {
    $needInstall = (Get-Item -LiteralPath $stampFile).LastWriteTimeUtc -lt $pyprojectTime
}
if ($needInstall) {
    Write-Step 'Installing the tool into .venv'
    & $venvPython -m pip install --disable-pip-version-check -q --upgrade pip
    & $venvPython -m pip install --disable-pip-version-check -q -e '.[dev]'
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'pip install failed (see output above).' }
    Set-Content -LiteralPath $stampFile -Value (Get-Date -Format o) -Encoding ascii
}

# --- 3. .env ----------------------------------------------------------------
$envFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Destination $envFile
    Write-Host ''
    Write-Host 'Created .env from .env.example.' -ForegroundColor Yellow
    Write-Host 'Open .env, put in ELDORADO_CLIENT_ID and ELDORADO_CLIENT_SECRET, then run this script again.' -ForegroundColor Yellow
    Start-Process notepad.exe -ArgumentList "`"$envFile`""
    exit 0
}
# Check only that the values are present. Never print them.
$envText = Get-Content -LiteralPath $envFile -Raw
foreach ($key in 'ELDORADO_CLIENT_ID', 'ELDORADO_CLIENT_SECRET') {
    if ($envText -notmatch "(?m)^\s*$key\s*=\s*\S+") {
        Stop-WithError "$key is empty in .env. Fill it in and run again."
    }
}

# --- 4. Start ---------------------------------------------------------------
$cliArgs = @($Mode)
if ($Port -gt 0) { $cliArgs += @('--port', "$Port") }
if ($NoBrowser) { $cliArgs += '--no-browser' }

if ($Mode -eq 'app') {
    Write-Step 'Starting settings page + bot (bot starts PAUSED; press RUN on the page)'
} else {
    Write-Step 'Starting settings page only (no bot)'
}
& $eldoradoExe @cliArgs
$code = $LASTEXITCODE
if ($code -ne 0 -and $Host.Name -eq 'ConsoleHost') { Read-Host 'Press Enter to close' | Out-Null }
exit $code
