#Requires -Version 5.1
<#
.SYNOPSIS
  RAGE + Ollama con un solo modelo: qwen2:7b (sin descargar 3b/phi3).

.EXAMPLE
  .\windows-ollama\scripts\run-qwen2-7b.ps1
  .\windows-ollama\scripts\run-qwen2-7b.ps1 -Mode redteam -Severity high -Iterations 5
  .\windows-ollama\scripts\run-qwen2-7b.ps1 -Mode test-ollama
#>
param(
    [ValidateSet("chat", "redteam", "demo", "training", "test-ollama")]
    [string]$Mode = "chat",
    [string]$Severity = "medium",
    [int]$Iterations = 10,
    [switch]$Unlimited
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

$Model = "qwen2:7b"
$profilePath = Join-Path $RepoRoot "windows-ollama\profiles\qwen2-7b.env"
if (Test-Path $profilePath) {
    Get-Content $profilePath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

function Ensure-OllamaModel {
    param([string]$Name)
    $list = ollama list 2>&1 | Out-String
    if ($list -match "(?m)^$([regex]::Escape($Name))\s") {
        Write-Host "[OK] Modelo ya instalado: $Name (sin descarga)"
        return
    }
    Write-Host "Modelo no encontrado — descargando solo: $Name"
    ollama pull $Name
}

Ensure-OllamaModel -Name $Model

switch ($Mode) {
    "chat" {
        Write-Host "RAGE Chat — modelo único: $Model"
        uv run rage-chat --model $Model
    }
    "redteam" {
        Write-Host "RAGE Red-Team — modelo único: $Model"
        $argsList = @(
            "--no-interactive", "--model", "ollama",
            "--severity", $Severity,
            "--objectives", "exfil", "ddl", "schema_dump", "canary", "privilege"
        )
        if ($Unlimited) { $argsList += "--unlimited" }
        else { $argsList += "--iterations", $Iterations }
        uv run rage-redteam @argsList
    }
    "demo" {
        uv run rage-demo --no-plot
    }
    "training" {
        uv run rage-training @args
    }
    "test-ollama" {
        ollama run $Model "Responde en una sola linea: Ollama OK con qwen2 7b"
    }
}
