# Manuales — RAGE

Documentación en español del proyecto.

| Archivo | Formato | Descripción |
|---------|---------|-------------|
| [training-center-manual.md](training-center-manual.md) | Markdown | Fuente editable del manual |
| [training-center-manual.pdf](training-center-manual.pdf) | PDF | Manual listo para imprimir o compartir |

## Regenerar el PDF

Tras editar el `.md`:

```bash
python3 scripts/generate_manual_pdf.py
```

Requisito: `fpdf2` (`pip install fpdf2`).

## Contenido del manual

- Setup y errores comunes
- `rage-training` — campañas con escenarios fijos y ASR
- `rage-redteam` v3 — modo ilimitado, gravedad, panel interactivo
- `rage-training-apply` — aplicar parches al KB
- `rage-demo` — demo visual turno a turno
- Flujos de trabajo, métricas y cheat sheet
