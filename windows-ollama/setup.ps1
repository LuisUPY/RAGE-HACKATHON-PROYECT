#Requires -Version 5.1
<#
.SYNOPSIS
  Setup completo para RAGE + Ollama en Windows 11 (RTX 5050).
#>
param(
    [switch]$SkipModelPull,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== RAGE Windows + Ollama — setup ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

Set-Location $RepoRoot

# 1. Instalar uv si falta
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Instalando uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
}

# 2. Verificar Ollama
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Error "Ollama no instalado. Descarga desde https://ollama.com e instala antes de continuar."
}

Write-Host "Esperando API de Ollama..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    Write-Warning "Ollama API no responde. Abre la app Ollama desde la bandeja e ejecuta setup de nuevo."
}

# 3. Dependencias Python
Write-Host "Instalando dependencias (uv sync --extra openai)..."
uv sync --extra openai

# 4. Copiar .env si no existe
$envExample = Join-Path $RepoRoot "windows-ollama\.env.example"
$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "Creado .env desde windows-ollama/.env.example"
} else {
    Write-Host ".env ya existe — no sobrescrito"
}

# 5. Descargar modelos
if (-not $SkipModelPull) {
    $modelsJson = Get-Content (Join-Path $RepoRoot "windows-ollama\config\models.json") | ConvertFrom-Json
    foreach ($model in $modelsJson.pull_order) {
        Write-Host "Descargando modelo: $model ..."
        ollama pull $model
    }
} else {
    Write-Host "Skip model pull (--SkipModelPull)"
}

# 6. Verificacion
Write-Host ""
& (Join-Path $PSScriptRoot "verify-environment.ps1") -RepoRoot $RepoRoot

# 7. Warm-up demo
Write-Host ""
Write-Host "Warm-up: rage-demo (escenario benigno)..."
uv run rage-demo --scenario benign_conversation --no-plot

Write-Host ""
Write-Host "Setup completo." -ForegroundColor Green
Write-Host "Siguiente paso: .\windows-ollama\scripts\run-chat.ps1"
