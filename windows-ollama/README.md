# RAGE en Windows 11 + Ollama + NVIDIA RTX 5050

Kit de despliegue para ejecutar RAGE con **Ollama local** y GPU NVIDIA (8 GB VRAM).

## Requisitos

| Componente | Version minima |
|---|---|
| Windows 11 | 22H2+ |
| Ollama | Instalado desde [ollama.com](https://ollama.com) |
| Git | Cualquier version reciente |
| Python | 3.12+ (uv lo gestiona) |
| uv | Se instala automaticamente en setup |
| GPU | RTX 5050 (8 GB) o similar |
| RAM | 16 GB recomendado |

## Instalacion rapida (5 pasos)

### 1. Clonar el repositorio

```powershell
cd $HOME
git clone https://github.com/LuisUPY/RAGE-HACKATHON-PROYECT.git
cd RAGE-HACKATHON-PROYECT
git checkout cursor/windows-ollama-setup-93a0
```

### 2. Instalar Ollama

1. Descarga el instalador desde [https://ollama.com/download](https://ollama.com/download)
2. Ejecuta el instalador y deja que Ollama quede en la bandeja del sistema
3. Verifica en PowerShell:

```powershell
ollama --version
ollama list
```

### 3. Permitir scripts PowerShell

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 4. Ejecutar setup

Desde la **raiz del repo**:

```powershell
.\windows-ollama\setup.ps1
```

El setup hace:
- Instala `uv` si falta
- `uv sync --extra openai`
- Copia `windows-ollama/.env.example` → `.env`
- Descarga modelos (`qwen2.5:7b-instruct`, `qwen2.5:3b-instruct`)
- Ejecuta verificacion y un demo de calentamiento

### 5. Verificar GPU

```powershell
nvidia-smi
ollama run qwen2.5:7b-instruct "Hola, responde en una linea"
```

## Comandos disponibles

| Script | Que hace |
|---|---|
| `.\windows-ollama\scripts\run-demo.ps1` | Demo offline (sin LLM) — validacion rapida |
| `.\windows-ollama\scripts\run-chat.ps1` | Chat interactivo con Ollama + defensa RAGE |
| `.\windows-ollama\scripts\run-training.ps1` | Campanas Crescendo del Training-Center |
| `.\windows-ollama\scripts\run-redteam.ps1` | Red-team adaptativo (headless, modelo ollama) |
| `.\windows-ollama\scripts\run-tests.ps1` | Suite pytest |
| `.\windows-ollama\verify-environment.ps1` | Diagnostico de prerequisitos |

### Ejemplos

```powershell
# Chat con el agente local
.\windows-ollama\scripts\run-chat.ps1

# Red-team 10 iteraciones, severidad alta
.\windows-ollama\scripts\run-redteam.ps1 -Severity high -Iterations 10

# Red-team indefinido (Ctrl+C para parar)
.\windows-ollama\scripts\run-redteam.ps1 -Unlimited -Severity critical

# Training con escenarios concretos
.\windows-ollama\scripts\run-training.ps1 --scenarios drop_table_escalation crescendo_escalation
```

### Solo `qwen2:7b` (un modelo, sin mas descargas)

```powershell
.\windows-ollama\scripts\run-qwen2-7b.ps1
.\windows-ollama\scripts\run-qwen2-7b.ps1 -Mode redteam -Severity high -Iterations 5
.\windows-ollama\scripts\run-qwen2-7b.ps1 -Mode test-ollama
```

Perfil: [`profiles/qwen2-7b.env`](profiles/qwen2-7b.env). Solo descarga `qwen2:7b` si no esta instalado.

## Modelos recomendados (RTX 5050, 8 GB)

| Rol | Modelo | VRAM aprox. |
|---|---|---|
| Chat / red-team | `qwen2.5:7b-instruct` | ~4.7 GB |
| Juez L3 (opcional) | `qwen2.5:3b-instruct` | ~2 GB |
| Fallback ligero | `phi3:mini` | ~2.3 GB |

Si ves **CUDA out of memory**:
1. Cierra juegos y apps que usen GPU
2. Cambia en `.env`: `OLLAMA_MODEL=phi3:mini`
3. Reinicia Ollama desde la bandeja del sistema

## Variables de entorno

Archivo `.env` en la raiz del repo (plantilla en `windows-ollama/.env.example`):

```env
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:7b-instruct
RAGE_LLM_BASE_URL=http://localhost:11434/v1
RAGE_USE_LLM_JUDGE=1
RAGE_EMBEDDER=tfidf
```

Los scripts de `run-chat.ps1` y `run-redteam.ps1` cargan automaticamente `profiles/rtx5050.env`.

## Arquitectura

```
Usuario → DefensePipeline (L1-L4) → [ALLOW] → Ollama (localhost:11434)
                                              ↓
                                    SalesAgent + ActionGateway → SQLite
```

- **L1-L4**: defensa multi-capa (regex, RAG, drift semantico, decision)
- **Gateway**: bloquea SQL destructivo y exfiltracion
- **Ollama**: LLM local via API compatible OpenAI

## Solucion de problemas

| Problema | Solucion |
|---|---|
| `Ollama API no responde` | Abre Ollama desde la bandeja; reinicia el servicio |
| `uv: command not found` | Cierra y abre PowerShell tras setup; o reinstala uv |
| Red-team cuelga | Usa siempre `--no-interactive` (los scripts ya lo hacen) |
| `rage_core` no encontrado | Asegurate de estar en la raiz del repo, no en una subcarpeta |
| Encoding raro en consola | `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` |
| Campanas largas se suspenden | `powercfg /change standby-timeout-ac 0` |

## Manual completo

Ver [Manuales/training-center-manual.pdf](../Manuales/training-center-manual.pdf) para `rage-training`, `rage-redteam` v3 y flujos de hardening.

## Notas

- **No uses modo interactivo curses** en Windows para red-team; usa los scripts headless.
- **Embeddings**: TF-IDF offline por defecto (sin descargas grandes). Opcional: `uv sync --extra transformers`.
- **Sin API key de OpenAI**: todo funciona con Ollama local ($0).

## Mac Apple Silicon

Para Mac M1/M2/M3 con 8 GB RAM, ver [mac-ollama/README.md](../mac-ollama/README.md).
