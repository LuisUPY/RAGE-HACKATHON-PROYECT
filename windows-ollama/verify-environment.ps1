#Requires -Version 5.1
<#
.SYNOPSIS
  Verifica prerequisitos: Ollama, Python, uv, GPU y modelos.
#>
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== RAGE Windows + Ollama — verificacion ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

$fail = 0

function Test-CommandExists($name) {
    if (Get-Command $name -ErrorAction SilentlyContinue) { return $true }
    return $false
}

# Git
if (Test-CommandExists git) { Write-Host "[OK] git" } else { Write-Host "[WARN] git no encontrado" }

# Python
if (Test-CommandExists python) {
    $pyVer = python --version 2>&1
    Write-Host "[OK] $pyVer"
} else {
    Write-Host "[FAIL] Python no encontrado (instala 3.12+)" -ForegroundColor Red
    $fail++
}

# uv
if (Test-CommandExists uv) {
    Write-Host "[OK] uv $(uv --version)"
} else {
    Write-Host "[FAIL] uv no encontrado" -ForegroundColor Red
    $fail++
}

# Repo structure
if (Test-Path (Join-Path $RepoRoot "rage_core")) {
    Write-Host "[OK] rage_core/"
} else {
    Write-Host "[FAIL] rage_core/ no existe — ejecuta desde la raiz del repo" -ForegroundColor Red
    $fail++
}

# Ollama
if (Test-CommandExists ollama) {
    Write-Host "[OK] ollama $(ollama --version 2>&1)"
} else {
    Write-Host "[FAIL] ollama no encontrado — instala desde https://ollama.com" -ForegroundColor Red
    $fail++
}

# Ollama API
try {
    $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
    $models = @($tags.models | ForEach-Object { $_.name })
    if ($models.Count -gt 0) {
        Write-Host "[OK] Ollama API — modelos: $($models -join ', ')"
    } else {
        Write-Host "[WARN] Ollama API OK pero sin modelos — ejecuta setup.ps1"
    }
} catch {
    Write-Host "[FAIL] Ollama API no responde en localhost:11434" -ForegroundColor Red
    Write-Host "       Abre Ollama desde la bandeja del sistema e intenta de nuevo."
    $fail++
}

# NVIDIA GPU (optional)
if (Test-CommandExists nvidia-smi) {
    $gpu = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1
    Write-Host "[OK] GPU: $gpu"
} else {
    Write-Host "[WARN] nvidia-smi no en PATH — drivers NVIDIA pueden estar sin instalar"
}

# Python import smoke test
Push-Location $RepoRoot
try {
    $out = uv run python -c "from rage_core.layers.layer4_decision import DefensePipeline; print('import_ok')" 2>&1
    if ($out -match "import_ok") {
        Write-Host "[OK] rage_core importable"
    } else {
        Write-Host "[FAIL] uv run python fallo: $out" -ForegroundColor Red
        $fail++
    }
} catch {
    Write-Host "[FAIL] uv run python: $_" -ForegroundColor Red
    $fail++
} finally {
    Pop-Location
}

Write-Host ""
if ($fail -eq 0) {
    Write-Host "Verificacion OK. Puedes ejecutar:" -ForegroundColor Green
    Write-Host "  .\windows-ollama\scripts\run-demo.ps1"
    Write-Host "  .\windows-ollama\scripts\run-chat.ps1"
    exit 0
} else {
    Write-Host "Verificacion fallida ($fail errores). Corrige e intenta de nuevo." -ForegroundColor Red
    exit 1
}
