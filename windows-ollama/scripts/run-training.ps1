#Requires -Version 5.1
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
Write-Host "RAGE Training-Center" -ForegroundColor Cyan
uv run rage-training @args
