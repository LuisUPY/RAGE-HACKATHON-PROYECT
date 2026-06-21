#Requires -Version 5.1
param(
    [string]$Severity = "medium",
    [int]$Iterations = 10,
    [switch]$Unlimited
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

# Cargar variables de entorno del preset RTX 5050
$profilePath = Join-Path $RepoRoot "windows-ollama\profiles\rtx5050.env"
if (Test-Path $profilePath) {
    Get-Content $profilePath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

Write-Host "RAGE Red-Team (headless, modelo ollama)" -ForegroundColor Cyan

$argsList = @(
    "--no-interactive",
    "--model", "ollama",
    "--severity", $Severity,
    "--objectives", "exfil", "ddl", "schema_dump", "canary", "privilege"
)

if ($Unlimited) {
    $argsList += "--unlimited"
} else {
    $argsList += "--iterations", $Iterations
}

uv run rage-redteam @argsList
