param([switch]$Run)
$ErrorActionPreference = 'Stop'
$newsroomRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $newsroomRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' } }
& '.\.venv\Scripts\python.exe' -m pip install -r backend\requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed' }
Push-Location -LiteralPath frontend
try {
    npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
Write-Host 'CEO Newsroom is ready. Run .\scripts\run.ps1 to open the app at http://127.0.0.1:8788/'
if ($Run) { & "$PSScriptRoot\run.ps1" }
