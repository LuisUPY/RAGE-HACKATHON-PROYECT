"""Genera el PDF de arquitectura de RAGE (docs/RAGE-Arquitectura-v2.pdf).

Requiere el extra `docs`:  uv sync --extra docs   (instala reportlab)
Uso:                       uv run python docs/generate_architecture_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --- Paleta -----------------------------------------------------------------
NAVY = colors.HexColor("#0F2A4A")
BLUE = colors.HexColor("#1F6FEB")
TEAL = colors.HexColor("#0E7C7B")
LIGHT = colors.HexColor("#EAF2FB")
GREY = colors.HexColor("#5B6470")
RED = colors.HexColor("#C0392B")
AMBER = colors.HexColor("#B9770E")
GREEN = colors.HexColor("#1E8449")
ROWALT = colors.HexColor("#F4F7FB")

OUT = Path(__file__).parent / "RAGE-Arquitectura-v2.pdf"

# --- Estilos ----------------------------------------------------------------
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=NAVY, fontSize=16,
                    spaceBefore=14, spaceAfter=6, leading=20)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=BLUE, fontSize=12.5,
                    spaceBefore=10, spaceAfter=4, leading=16)
BODY = ParagraphStyle("BODY", parent=ss["BodyText"], fontSize=9.7, leading=14,
                      alignment=TA_JUSTIFY, spaceAfter=5)
BULLET = ParagraphStyle("BULLET", parent=BODY, alignment=TA_LEFT, spaceAfter=2)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.3, textColor=GREY, leading=11)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.5, leading=11, alignment=TA_LEFT,
                      spaceAfter=0)
CELLH = ParagraphStyle("CELLH", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")
COVER_T = ParagraphStyle("COVER_T", parent=ss["Title"], textColor=NAVY, fontSize=30, leading=34)
COVER_S = ParagraphStyle("COVER_S", parent=ss["Title"], textColor=TEAL, fontSize=14,
                         leading=18, spaceBefore=8)
BOXLABEL = ParagraphStyle("BOXLABEL", parent=BODY, textColor=colors.white,
                          fontName="Helvetica-Bold", fontSize=10.5, alignment=TA_CENTER,
                          leading=13, spaceAfter=0)
BOXSUB = ParagraphStyle("BOXSUB", parent=BODY, textColor=colors.white, fontSize=7.8,
                        alignment=TA_CENTER, leading=10, spaceAfter=0)
ARROW = ParagraphStyle("ARROW", parent=BODY, alignment=TA_CENTER, fontSize=12,
                       textColor=GREY, spaceAfter=0, spaceBefore=0)

story: list = []


def p(text, style=BODY):
    story.append(Paragraph(text, style))


def h1(text):
    story.append(Spacer(1, 4))
    story.append(Paragraph(text, H1))
    story.append(HRFlowable(width="100%", thickness=1.1, color=LIGHT, spaceAfter=6))


def h2(text):
    story.append(Paragraph(text, H2))


def bullets(items, style=BULLET):
    flow = [ListItem(Paragraph(it, style), leftIndent=6) for it in items]
    story.append(ListFlowable(flow, bulletType="bullet", start="•", leftIndent=12,
                              bulletColor=BLUE, bulletFontSize=8))


def table(data, col_widths, header=True, font=8.5, align_first_left=True):
    rows = []
    for r, row in enumerate(data):
        cells = []
        for c, val in enumerate(row):
            style = CELLH if (header and r == 0) else CELL
            cells.append(Paragraph(str(val), style))
        rows.append(cells)
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D6E5")),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, ROWALT]),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 6))


def pipeline_box(label, sub, color):
    inner = Table([[Paragraph(label, BOXLABEL)], [Paragraph(sub, BOXSUB)]], colWidths=[14 * cm])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(inner)


def arrow():
    story.append(Paragraph("&#8595;", ARROW))


# ============================================================================
# PORTADA
# ============================================================================
story.append(Spacer(1, 3.2 * cm))
p("RAGE", COVER_T)
p("Retrieval-Augmented Governance Engine", COVER_S)
story.append(Spacer(1, 0.5 * cm))
p("Capa de gobernanza explicable contra prompt injection y jailbreaks en "
  "sistemas basados en LLM", ParagraphStyle("ct", parent=BODY, alignment=TA_CENTER,
                                            fontSize=11, textColor=GREY))
story.append(Spacer(1, 1.2 * cm))
story.append(HRFlowable(width="55%", thickness=1.2, color=TEAL))
story.append(Spacer(1, 0.5 * cm))
p("Documento de arquitectura del sistema — v2", ParagraphStyle("cv", parent=BODY,
  alignment=TA_CENTER, fontSize=12, textColor=NAVY, fontName="Helvetica-Bold"))
p("Rehecho con feedback de asesores, mapeo a OWASP Top 10 LLM 2025, "
  "estado del arte y diferenciadores métricos", ParagraphStyle("cv2", parent=SMALL,
  alignment=TA_CENTER))
story.append(Spacer(1, 2.4 * cm))
p("Proyecto de hackathon · AI Safety", ParagraphStyle("cv3", parent=SMALL,
  alignment=TA_CENTER))
story.append(PageBreak())

# ============================================================================
# 1. RESUMEN EJECUTIVO
# ============================================================================
h1("1. Resumen ejecutivo")
p("<b>RAGE</b> es una capa de seguridad que se coloca <b>delante de un LLM</b> "
  "(chatbots, asistentes y especialmente <b>agentes conectados a APIs y bases de "
  "datos</b>) para detectar y contener ataques de <b>prompt injection</b> y "
  "<b>jailbreak</b> — el riesgo nº1 del OWASP Top 10 para LLM 2025.")
p("A diferencia de un guardrail que solo cuenta cuántos prompts bloqueó, RAGE aporta: "
  "(a) una <b>arquitectura en capas con motor de decisión explicable</b>, (b) una "
  "<b>base de conocimiento de amenazas actualizable sin reentrenar</b>, (c) una "
  "<b>métrica científica de degradación multi-turno (AUC)</b>, y (d) un "
  "<b>harness de medición reproducible</b> que cuantifica el riesgo antes/después.")
p("<b>Honestidad técnica:</b> la idea de detección por <i>retrieval</i> ya existe en la "
  "literatura (RAD, Vigil, Rebuff). El aporte de RAGE es de <b>integración, gobernanza, "
  "explicabilidad y medición</b>, no un algoritmo nuevo.")

# ============================================================================
# 2. EL PROBLEMA
# ============================================================================
h1("2. El problema")
p("Los LLM <b>no distinguen de forma fiable instrucciones de datos</b>: cualquier texto "
  "en su contexto puede actuar como orden. Esto hace que el prompt injection sea un "
  "fallo <b>arquitectónico</b>, no un bug que se parchea.")
bullets([
    "Sistemas <b>sin defensa</b>: tasa de éxito de ataque (ASR) <b>&gt; 90%</b>.",
    "<b>Ninguna defensa es perfecta</b>: el estudio <i>“The Attacker Moves Second”</i> "
    "(OpenAI/Anthropic/DeepMind, 2025) rompió 12 defensas publicadas (&gt;90% ASR con "
    "ataques adaptativos).",
    "El consenso del campo es <b>defensa en profundidad</b> (varias capas), monitoreo y "
    "testing adversarial continuo.",
])

# ============================================================================
# 3. VISIÓN
# ============================================================================
h1("3. Visión de RAGE")
p("Convertir la detección por retrieval en una <b>capa de gobernanza</b>: explicable "
  "(traza al ataque conocido), <b>medible</b> (ASR, severidad, AUC, falsos positivos, "
  "costo), <b>actualizable en caliente</b> (nuevas amenazas al KB sin reentrenar) e "
  "<b>independiente del modelo y del proveedor</b> (desplegable on-prem, delante de "
  "cualquier LLM).")

story.append(PageBreak())

# ============================================================================
# 4. ARQUITECTURA
# ============================================================================
h1("4. Arquitectura del sistema")
p("RAGE se implementa como una <b>cascada con salida temprana (early-exit)</b>, ordenada "
  "de lo más barato/preciso a lo más caro. La mayoría del tráfico se resuelve en etapas "
  "baratas; el clasificador LLM solo se invoca en casos ambiguos. Esto mantiene el "
  "sobrecosto bajo (~+1–15%).")
story.append(Spacer(1, 4))

pipeline_box("Entrada del usuario / contenido recuperado (RAG)",
             "Prompt + historial de conversación + documentos/tool-outputs (no confiables)", GREY)
arrow()
pipeline_box("Capa 1 · Pre-filtro determinista",
             "Reglas, firmas, denylist, regex · costo ~0 · atrapa lo obvio y sale temprano", TEAL)
arrow()
pipeline_box("Capa 2 · RAG de amenazas (KB)",
             "Embeddings + similitud contra ataques conocidos (OWASP, jailbreaks) · barato", BLUE)
arrow()
pipeline_box("Capa 3 · Filtro semántico dinámico (intención, con estado)",
             "Micro-resumen del turno previo: ¿cambio de rol / intento de ignorar reglas? · LLM condicional", NAVY)
arrow()
pipeline_box("Capa 4 · Motor de decisión",
             "Fusiona señales → score 0–100 · bandas: permitir / advertir / bloquear (umbral ajustable)", RED)
arrow()
pipeline_box("Gateway de acciones + verificación de salida",
             "Gatea tool-calls (allowlist, solo SELECT param.) y valida la respuesta antes de entregarla", AMBER)

story.append(Spacer(1, 8))
p("<b>Notas de diseño clave:</b>")
bullets([
    "El <b>contenido recuperado y el micro-resumen son texto influido por el atacante</b> → "
    "se tratan como <b>no confiables</b> (mitiga LLM08 y la inyección recursiva).",
    "El <b>umbral</b> del motor de decisión es configurable → controla el balance "
    "seguridad ↔ utilidad (como en RAD).",
    "La <b>verificación de salida</b> atrapa ataques que pasaron las capas previas "
    "(~60% de los que penetran, según la literatura).",
])

story.append(PageBreak())

# ============================================================================
# 5. DIFERENCIADORES
# ============================================================================
h1("5. Diferenciadores clave")
p("Los tres se conectan: <b>B</b> es el mecanismo, <b>A</b> es la métrica que lo prueba "
  "a lo largo del tiempo, y <b>C</b> es el escenario grave que lo hace impactante.")

h2("A. Métrica: Área Bajo la Curva (AUC) de degradación multi-turno")
p("Se grafica el <b>score de vulnerabilidad (eje Y)</b> contra los <b>turnos de la "
  "conversación (eje X)</b> y se integra con la regla del trapecio para obtener un "
  "<b>número único</b>. AUC bajo = la defensa contuvo el ataque a lo largo del tiempo; "
  "AUC alto = el guardrail tradicional colapsó en turnos avanzados.")
p("<b>Blindajes metodológicos (imprescindibles):</b>")
bullets([
    "<b>Sin circularidad:</b> el eje Y debe venir de <b>ground truth</b> (¿el sistema "
    "protegido realmente filtró el canario o ejecutó la acción prohibida?), NO del score "
    "que RAGE se asigna a sí mismo.",
    "<b>Normalizar</b> el AUC (dividir entre el área máxima = score_máx × nº turnos) para "
    "comparar conversaciones de distinta longitud.",
    "Graficar <b>dos curvas</b> en el mismo ataque (sin defensa vs RAGE) y reportar el "
    "<b>turno de compromiso</b> (cuándo cruza el umbral por primera vez).",
])

h2("B. Filtro semántico dinámico (contextual, con estado)")
p("En vez de buscar solo palabras prohibidas, evalúa el <b>cambio de intención respecto "
  "al turno anterior</b> mediante un micro-resumen de la conversación: ¿el usuario cambia "
  "radicalmente de tema o intenta que el agente ignore sus reglas corporativas? Esto "
  "convierte la defensa en una <b>barrera contextual, no solo semántica</b> — justo el "
  "hueco donde fallan los guardrails de un solo turno.")
bullets([
    "<b>Costo:</b> primero detectar drift por embeddings (barato) y solo disparar el "
    "resumen/clasificador LLM cuando hay sospecha (encaja en la cascada).",
    "El micro-resumen es <b>no confiable</b> (texto del atacante) → debe aislarse.",
])

h2("C. Agentes empresariales conectados (caso grave)")
p("La mayoría de benchmarks prueban chats puros. RAGE defiende un <b>agente con "
  "herramientas conectadas a API/DB</b>. Demo: una inyección que intenta ejecutar "
  "<b>DROP TABLE</b> o exfiltrar datos sobre una <b>base de ventas falsa (SQLite en "
  "memoria)</b>. Mapea a OWASP <b>LLM06 (Excessive Agency)</b> y <b>LLM05</b>.")
bullets([
    "<b>Defensa en capas a nivel de acción:</b> aunque la inyección llegue al agente, el "
    "gateway gatea la tool-call (allowlist, solo <font face='Courier'>SELECT</font> "
    "parametrizado; bloquea <font face='Courier'>DROP/DELETE/UPDATE</font>).",
    "Aquí el <b>canario es una acción</b> (“¿se ejecutó DROP TABLE?”), lo que alimenta "
    "directo el eje Y de ground truth de la métrica (A).",
])

story.append(PageBreak())

# ============================================================================
# 6. OWASP
# ============================================================================
h1("6. Mapeo a OWASP Top 10 para LLM 2025")
table([
    ["Riesgo OWASP 2025", "¿RAGE lo aborda?", "Cómo"],
    ["LLM01 Prompt Injection", "Sí, hoy (núcleo)", "Cascada de detección + decisión bloquea inyección directa, indirecta, payload splitting, ofuscación"],
    ["LLM07 System Prompt Leakage", "Sí, hoy", "Detecta intentos de filtrar instrucciones/secretos (lo mide el harness con canarios)"],
    ["LLM02 Sensitive Info Disclosure", "Con cambios", "Filtro de salida que redacta/bloquea fugas (PII, secretos)"],
    ["LLM05 Improper Output Handling", "Con cambios", "Capa de validación/sanitización de salida"],
    ["LLM06 Excessive Agency", "Con cambios", "Motor de decisión sobre tool-calls (block / human-in-the-loop)"],
    ["LLM09 Misinformation", "Con cambios", "Verificación de groundedness (RAG Triad)"],
    ["LLM08 Vector & Embedding Weaknesses", "Riesgo que RAGE introduce", "RAGE usa vector store → proteger integridad y acceso del KB"],
    ["LLM03 / LLM04 / LLM10", "Fuera de alcance", "Cadena de suministro, envenenamiento de entrenamiento, consumo (parcial: rate-limit)"],
], col_widths=[5.2 * cm, 3.6 * cm, 8.0 * cm])

# ============================================================================
# 7. ESTADO DEL ARTE
# ============================================================================
h1("7. Estado del arte y aporte honesto de RAGE")
table([
    ["Familia de defensa", "Ejemplos", "Adaptable sin reentrenar", "Explicable"],
    ["Prompting / system prompt", "Instruction hierarchy, spotlighting", "n/a", "No"],
    ["Fine-tuning", "StruQ (~45% ASR), SecAlign (~8%)", "No (reentrenar)", "No"],
    ["Clasificadores ML", "Prompt Guard, Llama Guard, Vigil", "No (reentrenar)", "Limitada"],
    ["Servicio gestionado", "Lakera Guard (&lt;50ms)", "Parcial", "Dashboard"],
    ["Frameworks", "NeMo Guardrails, Guardrails AI, LLM Guard, Rebuff", "Parcial", "Parcial"],
    ["Arquitectónicos", "CaMeL, dual-LLM, structured queries", "n/a", "Parcial"],
    ["<b>RAG-based (familia de RAGE)</b>", "<b>RAD, RePD, Vigil</b>", "<b>Sí (al KB)</b>", "<b>Sí</b>"],
], col_widths=[4.4 * cm, 6.2 * cm, 3.4 * cm, 2.8 * cm])
p("<b>Prior art:</b> el concepto de RAGE ya existe (p. ej. <b>RAD</b>, arXiv 2508.16406: "
  "RAG + umbral ajustable + KB sin reentrenar). <b>RAGE no inventa el mecanismo;</b> su "
  "valor es volverlo una capa de gobernanza explicable, medible (incl. AUC multi-turno), "
  "mapeada a OWASP y aplicada a agentes conectados.", SMALL)

story.append(PageBreak())

# ============================================================================
# 8. PREGUNTA DE INVESTIGACIÓN
# ============================================================================
h1("8. Pregunta de investigación e hipótesis")
p("<b>Pregunta principal:</b> ¿En qué medida una capa de gobernanza basada en RAG "
  "(intención + recuperación de amenazas + decisión) reduce la tasa de éxito de prompt "
  "injection (OWASP LLM01) en agentes basados en LLM, y a qué costo de latencia/cómputo "
  "y de falsos positivos, comparada con las defensas actuales?")
bullets([
    "<b>H1 (efectividad):</b> RAGE reduce significativamente el ASR vs el baseline de solo system prompt.",
    "<b>H2 (costo):</b> lo logra con sobrecosto bajo (~+1–15%) y latencia tolerable.",
    "<b>H3 (utilidad):</b> mantiene baja la tasa de falsos positivos (no rompe tráfico legítimo).",
    "<b>H4 (adaptabilidad):</b> agregar un ataque nuevo al KB mejora la detección de su "
    "familia <b>sin reentrenar</b> — lo que un clasificador fine-tuneado no puede.",
    "<b>H5 (robustez temporal):</b> el <b>AUC de degradación</b> de RAGE se mantiene bajo "
    "a lo largo de los turnos, mientras el de un guardrail tradicional crece.",
])

# ============================================================================
# 9. COSTO/BENEFICIO
# ============================================================================
h1("9. Costo / beneficio (modelo base = 100%)")
table([
    ["Escenario", "Costo total con RAGE", "Latencia extra"],
    ["Modelo base caro + RAGE eficiente", "~100.5% – 110%", "+50–600 ms"],
    ["Solo embeddings + reglas (sin LLM extra)", "~101% – 105%", "+50–150 ms"],
    ["Modelo base barato + clasificador chico", "~112% – 130%", "+200–500 ms"],
    ["Peor caso (guard con LLM tan caro como el principal)", "~150% – 200%", "+0.5–1 s"],
], col_widths=[7.6 * cm, 4.6 * cm, 4.6 * cm])
p("Además, RAGE <b>bloquea ataques antes</b> de llamar al LLM caro → ahorra esas llamadas, "
  "compensando parte del overhead. El costo real crítico no es cómputo, sino "
  "<b>latencia y falsos positivos</b> (el “trilema”).", SMALL)

# ============================================================================
# 10. MÉTRICAS
# ============================================================================
h1("10. Métricas de evaluación")
bullets([
    "<b>ASR</b> (Attack Success Rate) global y por categoría OWASP.",
    "<b>Score de severidad</b> 0–100 con bandas (NONE / LOW / ELEVATED / CRITICAL).",
    "<b>AUC de degradación</b> multi-turno (normalizado).",
    "<b>Tasa de falsos positivos</b> sobre tráfico legítimo (utilidad).",
    "<b>Latencia y sobrecosto</b> (% sobre el costo del LLM base).",
])

# ============================================================================
# 11. PLAN
# ============================================================================
h1("11. Plan de trabajo (hackathon)")
table([
    ["Día", "Foco", "Entregables"],
    ["Sábado", "Construir el núcleo (tracks en paralelo)",
     "Track A: motor de decisión + gateway · Track B: RAG de amenazas (KB) · "
     "Track C: filtro de intención (dinámico). Cierre: integrar tras un LLM real."],
    ["Domingo", "Demo + evidencia + pulido",
     "Escenario grave (agente + DB falsa, DROP TABLE) · curvas de AUC antes/después · "
     "dashboard del ASR cayendo · ensayo del pitch."],
], col_widths=[2.4 * cm, 5.0 * cm, 9.4 * cm])
p("Cada track es una rama y un agente de Cursor en paralelo; el <b>harness</b> existente "
  "es el test de regresión (mide ASR + falsos positivos en cada cambio).", SMALL)

# ============================================================================
# 12. LIMITACIONES
# ============================================================================
h1("12. Limitaciones y riesgos honestos")
bullets([
    "<b>Ataques adaptativos:</b> ninguna defensa (RAGE incluido) resiste a un atacante "
    "que optimiza contra ella. RAGE reduce el riesgo, no lo elimina.",
    "<b>Gap semántico:</b> el RAG puede fallar ante ataques 0-day que no se parecen a "
    "nada del KB.",
    "<b>LLM08:</b> RAGE hereda el riesgo de su propio vector store (envenenamiento del KB).",
    "<b>Trilema:</b> subir la seguridad puede subir los falsos positivos — hay que medirlo.",
])

# ============================================================================
# 13. REFERENCIAS
# ============================================================================
h1("13. Referencias")
bullets([
    "OWASP Top 10 for LLM Applications 2025 — genai.owasp.org/llm-top-10/",
    "RAD: Retrieval-Augmented Defense — arXiv 2508.16406",
    "Securing AI Agents Against Prompt Injection (framework multicapa RAG) — arXiv 2511.15759",
    "StruQ (USENIX Security 25) y SecAlign — arXiv 2410.05451",
    "The Attacker Moves Second (Nasr et al., 2025).",
    "Documentos del repo: REPORT.md, docs/owasp-y-estado-del-arte.md, docs/estado-del-arte-deep-research.md",
], style=SMALL)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.1 * cm, "RAGE — Retrieval-Augmented Governance Engine · v2")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


def main() -> None:
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title="RAGE — Arquitectura del sistema v2", author="Equipo RAGE",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDF generado: {OUT}")


if __name__ == "__main__":
    main()
