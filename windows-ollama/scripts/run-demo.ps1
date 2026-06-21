#Requires -Version 5.1
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
Write-Host "RAGE Demo (offline, sin LLM)" -ForegroundColor Cyan
uv run rage-demo --no-plot
