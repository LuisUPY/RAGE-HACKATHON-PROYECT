# Envío Global South AI Safety Hackathon — RAGE

Plantilla oficial: https://github.com/aisafetymexico/global-south-ais-template

## Equipo

| Autor |
|-------|
| Luis Gerardo Escalante Velázquez |
| Armando Alberto Rivas Quevedo |
| Juan Emiliano Quintal Chuc |
| Alette Guadalupe Martínez Juárez |

**Track:** AI Security · Prompt injection & jailbreaks

## Archivos de entrega

| Archivo | Descripción |
|---------|-------------|
| `draft_submission.md` | Fuente principal (editar aquí) |
| `submission/GlobalSouth_RAGE_Submission.md` | Copia sincronizada del paper |
| `Documentation/GlobalSouth-RAGE-Submission.pdf` | PDF final (máx. 8 páginas) |

## Generar PDF

```bash
./scripts/generate_submission_pdf.sh
# → Documentation/GlobalSouth-RAGE-Submission.pdf
```

## Checklist de envío

- [x] Autores y afiliación en `draft_submission.md`
- [x] Track: AI Security · Sub-track: Prompt injection & jailbreaks
- [x] Abstract 150–250 palabras
- [x] Sección Limitaciones + doble uso (§5)
- [x] LLM Usage Statement
- [x] Link al repo en Code and Data
- [x] PDF ≤ 8 páginas
- [ ] Subir vía botón "Enviar tu proyecto" (Apart)

## Repo y reproducibilidad

```bash
git clone https://github.com/LuisUPY/RAGE-HACKATHON-PROYECT.git
cd RAGE-HACKATHON-PROYECT
uv sync
./scripts/validate-all.sh
```
