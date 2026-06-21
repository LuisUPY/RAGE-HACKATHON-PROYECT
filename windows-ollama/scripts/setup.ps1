#Requires -Version 5.1
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
& (Join-Path $RepoRoot "windows-ollama\setup.ps1") @args
