#Requires -Version 5.1
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
Write-Host "RAGE Tests (pytest)" -ForegroundColor Cyan
uv run pytest -v
