# RAGE en macOS Apple Silicon + Ollama (8 GB RAM)

Kit de despliegue para ejecutar RAGE con **Ollama local** en Mac M1/M2/M3 con **8 GB de RAM unificada**.

## Requisitos

| Componente | Version minima |
|---|---|
| macOS | 12+ (Monterey) |
| CPU | Apple Silicon (arm64) recomendado |
| Ollama | Instalado desde [ollama.com](https://ollama.com) (build ARM) |
| Git | Cualquier version reciente |
| Python | 3.12+ (uv lo gestiona) |
| RAM | 8 GB (funciona con modelos 3B; 16 GB mas comodo) |

## Instalacion rapida (5 pasos)

### 1. Clonar el repositorio

```bash
cd ~
git clone https://github.com/LuisUPY/RAGE-HACKATHON-PROYECT.git
cd RAGE-HACKATHON-PROYECT
git checkout cursor/mac-ollama-setup-93a0
```

### 2. Instalar Ollama

1. Descarga desde [https://ollama.com/download](https://ollama.com/download) (Mac Apple Silicon)
2. Abre la app Ollama (icono en la barra de menu)
3. Verifica en Terminal:

```bash
ollama --version
ollama list
```

### 3. Ejecutar setup

Desde la **raiz del repo**:

```bash
chmod +x mac-ollama/setup.sh mac-ollama/verify-environment.sh mac-ollama/scripts/*.sh
./mac-ollama/setup.sh
```

El setup hace:
- Instala `uv` si falta
- `uv sync --extra openai`
- Copia `mac-ollama/.env.example` → `.env`
- Descarga `qwen2.5:3b-instruct`
- Verificacion + demo de calentamiento

### 4. Probar Ollama

```bash
ollama run qwen2.5:3b-instruct "Hola, responde en una linea"
```

### 5. Lanzar RAGE

```bash
./mac-ollama/scripts/run-chat.sh
```

## Opcion A: Sin Ollama (mas estable en 8 GB)

No necesitas LLM local para training ni red-team offline:

```bash
uv sync
uv run rage-training
uv run rage-redteam --no-interactive --model offline --severity high
uv run rage-demo --no-plot
```

## Opcion B: Con Ollama local ($0)

```bash
./mac-ollama/scripts/run-chat.sh
./mac-ollama/scripts/run-redteam.sh --severity high --iterations 10
./mac-ollama/scripts/run-redteam.sh --unlimited --severity critical
```

## Opcion C: Solo `qwen2:7b` (un modelo, sin mas descargas)

Si ya tienes `qwen2:7b` en Ollama y quieres evitar bajar `3b` u otros modelos:

```bash
chmod +x mac-ollama/scripts/run-qwen2-7b.sh
./mac-ollama/scripts/run-qwen2-7b.sh              # chat
./mac-ollama/scripts/run-qwen2-7b.sh redteam --severity high --iterations 5
./mac-ollama/scripts/run-qwen2-7b.sh test-ollama  # probar Ollama sin RAGE
```

Perfil: [`profiles/qwen2-7b.env`](profiles/qwen2-7b.env) — chat, red-team y juez L3 usan el mismo modelo. Solo descarga si `qwen2:7b` no esta en `ollama list`.

## Comandos disponibles

| Script | Que hace |
|---|---|
| `./mac-ollama/scripts/run-demo.sh` | Demo offline (sin LLM) |
| `./mac-ollama/scripts/run-chat.sh` | Chat con Ollama + defensa RAGE |
| `./mac-ollama/scripts/run-training.sh` | Campanas Training-Center |
| `./mac-ollama/scripts/run-redteam.sh` | Red-team headless con `--model ollama` |
| `./mac-ollama/scripts/run-tests.sh` | Suite pytest |
| `./mac-ollama/verify-environment.sh` | Diagnostico |

## Modelos recomendados (M1 8 GB)

| Modelo | RAM aprox. | Uso |
|---|---|---|
| `qwen2.5:3b-instruct` | ~2 GB | **Por defecto** — chat, red-team, juez L3 |
| `phi3:mini` | ~2.3 GB | Fallback si hay swap o lentitud |
| `qwen2.5:7b-instruct` | ~4.7 GB | Solo si cierras todo lo demas |

En 8 GB usa **un solo modelo 3B** para todo. El preset esta en [`profiles/m1-8gb.env`](profiles/m1-8gb.env).

## Variables de entorno

Los scripts cargan automaticamente `profiles/m1-8gb.env`. Para cargar manualmente:

```bash
set -a
source mac-ollama/profiles/m1-8gb.env
set +a
```

Plantilla completa: [`mac-ollama/.env.example`](.env.example)

## Metal vs CUDA

Ollama en Mac usa **Metal** (GPU Apple) automaticamente. No necesitas drivers NVIDIA ni `nvidia-smi`.

## Solucion de problemas

| Problema | Solucion |
|---|---|
| Sistema lento / swap | Cierra Safari y Chrome; usa `phi3:mini` |
| `Ollama API no responde` | Abre la app Ollama desde la barra de menu |
| Red-team cuelga | Usa `--no-interactive` (los scripts ya lo hacen) |
| `uv: command not found` | Reinicia Terminal tras setup o `export PATH="$HOME/.local/bin:$PATH"` |
| Campana larga se suspende | `caffeinate -i ./mac-ollama/scripts/run-redteam.sh --unlimited` |
| Juez L3 consume RAM extra | `export RAGE_USE_LLM_JUDGE=0` antes de ejecutar |

## Enlaces

- Kit Windows + RTX 5050: [windows-ollama/README.md](../windows-ollama/README.md)
- Diagramas Training-Center: [Manuales/training-center-diagramas.md](../Manuales/training-center-diagramas.md)
- Manual PDF: [Manuales/training-center-manual.pdf](../Manuales/training-center-manual.pdf)

## Notas

- **No uses red-team interactivo (curses)** en Terminal si se cuelga; los scripts usan modo headless.
- **Embeddings**: TF-IDF offline por defecto (`RAGE_EMBEDDER=tfidf`).
- **Sin API key OpenAI**: todo funciona con Ollama local.
