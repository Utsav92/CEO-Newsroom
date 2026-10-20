$ErrorActionPreference = 'Stop'
$newsroomRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $newsroomRoot
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Run scripts\setup_windows.ps1 first to build the frontend.' }
$newsroomPython = if (Test-Path -LiteralPath '.venv\Scripts\python.exe') { Join-Path $newsroomRoot '.venv\Scripts\python.exe' } else { 'python' }
& $newsroomPython -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8788 --no-server-header --limit-concurrency 64 --timeout-keep-alive 5
