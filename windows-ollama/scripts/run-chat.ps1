#Requires -Version 5.1
param(
    [string]$Model = ""
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

$profilePath = Join-Path $RepoRoot "windows-ollama\profiles\rtx5050.env"
if (Test-Path $profilePath) {
    Get-Content $profilePath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

Write-Host "RAGE Chat (Ollama local)" -ForegroundColor Cyan

if ($Model) {
    uv run rage-chat --model $Model
} else {
    uv run rage-chat
}
