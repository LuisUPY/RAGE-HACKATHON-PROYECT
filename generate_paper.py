"""
generate_paper.py
=================
Genera el paper de investigación completo de RAGE en PDF.

Fuentes integradas:
    · estado-del-arte-deep-research.md   – marco teórico y estado del arte
    · generate_architecture_pdf.py       – arquitectura del sistema (extraído)
    · decision_engine.py                 – Track A: implementación y resultados

Sigue la plantilla:  global-south-ais-template/draft_submission.md
Salida:              RAGE-Paper.pdf

Uso:
    pip install reportlab
    python generate_paper.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
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
    KeepTogether,
)

# ---------------------------------------------------------------------------
# Paleta de colores
# ---------------------------------------------------------------------------
NAVY  = colors.HexColor("#0F2A4A")
BLUE  = colors.HexColor("#1F6FEB")
TEAL  = colors.HexColor("#0E7C7B")
LIGHT = colors.HexColor("#EAF2FB")
GREY  = colors.HexColor("#5B6470")
RED   = colors.HexColor("#C0392B")
AMBER = colors.HexColor("#B9770E")
GREEN = colors.HexColor("#1E8449")
ROWALT = colors.HexColor("#F4F7FB")
BLOCKBG = colors.HexColor("#F8F9FB")

OUT = Path(__file__).parent / "RAGE-Paper.pdf"

# ---------------------------------------------------------------------------
# Estilos tipográficos
# ---------------------------------------------------------------------------
ss = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "TITLE", parent=ss["Title"], textColor=NAVY, fontSize=22,
    leading=26, alignment=TA_CENTER, spaceAfter=6,
)
SUBTITLE_STYLE = ParagraphStyle(
    "SUBTITLE", parent=ss["Title"], textColor=TEAL, fontSize=13,
    leading=16, alignment=TA_CENTER, spaceAfter=4,
)
AUTHORS_STYLE = ParagraphStyle(
    "AUTHORS", parent=ss["Normal"], textColor=GREY, fontSize=10,
    alignment=TA_CENTER, spaceAfter=2, leading=14,
)
H1 = ParagraphStyle(
    "H1", parent=ss["Heading1"], textColor=NAVY, fontSize=13,
    spaceBefore=12, spaceAfter=4, leading=17,
)
H2 = ParagraphStyle(
    "H2", parent=ss["Heading2"], textColor=BLUE, fontSize=10.5,
    spaceBefore=8, spaceAfter=3, leading=14,
)
H3 = ParagraphStyle(
    "H3", parent=ss["Heading3"], textColor=TEAL, fontSize=9.5,
    spaceBefore=5, spaceAfter=2, leading=13, fontName="Helvetica-Bold",
)
BODY = ParagraphStyle(
    "BODY", parent=ss["BodyText"], fontSize=9.3, leading=13.5,
    alignment=TA_JUSTIFY, spaceAfter=5,
)
BULLET = ParagraphStyle(
    "BULLET", parent=BODY, alignment=TA_LEFT, spaceAfter=2,
)
SMALL = ParagraphStyle(
    "SMALL", parent=BODY, fontSize=8.1, textColor=GREY, leading=11,
)
CAPTION = ParagraphStyle(
    "CAPTION", parent=SMALL, alignment=TA_CENTER, fontName="Helvetica-Oblique",
)
CELL = ParagraphStyle(
    "CELL", parent=BODY, fontSize=8.3, leading=11, alignment=TA_LEFT, spaceAfter=0,
)
CELLH = ParagraphStyle(
    "CELLH", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold",
)
ABSTRACT_BOX = ParagraphStyle(
    "ABST", parent=BODY, fontSize=8.9, leading=13, alignment=TA_JUSTIFY,
)
CODE_STYLE = ParagraphStyle(
    "CODE", parent=ss["Code"], fontSize=7.8, leading=11, textColor=NAVY,
    leftIndent=8, rightIndent=8, spaceAfter=4,
)

story: list = []


# ---------------------------------------------------------------------------
# Helper constructors
# ---------------------------------------------------------------------------

def p(text: str, style=BODY) -> None:
    story.append(Paragraph(text, style))


def h1(text: str) -> None:
    story.append(Spacer(1, 3))
    story.append(Paragraph(text, H1))
    story.append(HRFlowable(width="100%", thickness=0.9, color=LIGHT, spaceAfter=5))


def h2(text: str) -> None:
    story.append(Paragraph(text, H2))


def h3(text: str) -> None:
    story.append(Paragraph(text, H3))


def sp(n: float = 0.25) -> None:
    story.append(Spacer(1, n * cm))


def bullets(items: list[str], style=BULLET) -> None:
    flow = [ListItem(Paragraph(it, style), leftIndent=6) for it in items]
    story.append(ListFlowable(
        flow, bulletType="bullet", start="•",
        leftIndent=14, bulletColor=BLUE, bulletFontSize=8,
    ))


def tbl(data: list, col_widths: list, header: bool = True) -> None:
    rows = []
    for r, row in enumerate(data):
        cells = []
        for val in row:
            style = CELLH if (header and r == 0) else CELL
            cells.append(Paragraph(str(val), style))
        rows.append(cells)
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    ts = [
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D6E5")),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, ROWALT]),
    ]
    if header:
        ts += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    t.setStyle(TableStyle(ts))
    story.append(t)
    story.append(Spacer(1, 6))


def abstract_box(text: str) -> None:
    inner = Table(
        [[Paragraph("<b>Abstract</b>", ParagraphStyle(
            "AH", parent=BODY, fontName="Helvetica-Bold", fontSize=9, spaceAfter=3,
        ))],
         [Paragraph(text, ABSTRACT_BOX)]],
        colWidths=[16.6 * cm],
    )
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLOCKBG),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BOX",           (0, 0), (-1, -1), 0.8, TEAL),
    ]))
    story.append(inner)
    story.append(Spacer(1, 10))


def pipeline_box(label: str, sub: str, color) -> None:
    inner = Table(
        [[Paragraph(label, ParagraphStyle(
            "PBL", parent=BODY, textColor=colors.white,
            fontName="Helvetica-Bold", fontSize=9.5, alignment=TA_CENTER, spaceAfter=0,
        ))],
         [Paragraph(sub, ParagraphStyle(
             "PBS", parent=BODY, textColor=colors.white,
             fontSize=7.5, alignment=TA_CENTER, leading=10, spaceAfter=0,
         ))]],
        colWidths=[15.5 * cm],
    )
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), color),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(inner)


def arrow() -> None:
    story.append(Paragraph(
        "&#8595;",
        ParagraphStyle("ARR", parent=BODY, alignment=TA_CENTER,
                       fontSize=11, textColor=GREY, spaceAfter=0, spaceBefore=0),
    ))


def hr() -> None:
    story.append(HRFlowable(width="100%", thickness=0.6, color=LIGHT, spaceAfter=4))


# ============================================================================
# PORTADA
# ============================================================================
sp(2.2)
p("RAGE: Retrieval-Augmented Governance Engine", TITLE_STYLE)
sp(0.1)
p("A Layered Defense Middleware Against Prompt Injection<br/>"
  "in Multi-Turn LLM Conversations", SUBTITLE_STYLE)
sp(0.5)
story.append(HRFlowable(width="60%", thickness=1.1, color=TEAL))
sp(0.35)
p("Equipo RAGE &nbsp;·&nbsp; Hackathon AI Safety — Global South AIS", AUTHORS_STYLE)
p("Track A: Decision Engine + Security Gateway", AUTHORS_STYLE)
sp(0.2)
p("<b>Code &amp; Data:</b> &nbsp;"
  "<font color='#1F6FEB'>github.com/LuisUPY/RAGE-HACKATHON-PROYECT</font>",
  ParagraphStyle("LINK", parent=AUTHORS_STYLE, fontSize=9))
sp(0.15)
p("Versión del documento: 1.0 · Junio 2026",
  ParagraphStyle("VER", parent=AUTHORS_STYLE, fontSize=8.5, textColor=GREY))
story.append(PageBreak())

# ============================================================================
# ABSTRACT
# ============================================================================
abstract_box(
    "Prompt injection remains the #1 risk in the OWASP Top 10 for LLM Applications 2025, "
    "with attack success rates (ASR) exceeding 90% in undefended systems. We present "
    "<b>RAGE</b> (Retrieval-Augmented Governance Engine), an explainable, multi-layer "
    "defense middleware that wraps any LLM to detect and contain prompt injection, jailbreaks, "
    "and context-manipulation attacks in dynamic multi-turn conversations. "
    "RAGE implements a cascading early-exit architecture with four detection layers: "
    "(1) deterministic pre-filter (regex/signatures), (2) threat knowledge-base RAG lookup, "
    "(3) stateful semantic intent filter, and (4) a decision gateway with three mutually "
    "exclusive actions — ALLOW / WARN / BLOCK — driven by a normalized risk score (0–5). "
    "Track A of our implementation demonstrates perfect score separation (AUC = 1.0000) on a "
    "3-turn adversarial conversation, blocking multi-vector attacks while allowing legitimate "
    "business queries unimpeded. Unlike single-turn guardrails, RAGE's stateful analysis detects "
    "gradual context drift. Unlike fine-tuned classifiers (StruQ, SecAlign), RAGE updates its "
    "threat knowledge base without retraining. We introduce per-turn risk scoring as a "
    "continuous predictor for multi-turn AUC degradation curves — a reproducible metric for "
    "evaluating guardrail collapse over conversation length, suitable for adversarial ML research."
)

# ============================================================================
# 1. INTRODUCTION
# ============================================================================
h1("1. Introduction")
p("Large Language Models (LLMs) have been widely adopted in enterprise settings as "
  "autonomous agents connected to APIs, databases, and retrieval-augmented generation (RAG) "
  "pipelines. This connectivity creates an expanded attack surface: any text in the model's "
  "context — including retrieved documents and prior conversation turns — can act as an "
  "instruction, bypassing intended safeguards. This class of vulnerability, known as "
  "<b>prompt injection</b> (OWASP LLM01, 2025), is an <i>architectural</i> flaw, not a "
  "patchable bug.")
p("Systems without dedicated defenses exhibit an ASR exceeding <b>90%</b> in controlled "
  "evaluations. Even SOTA defenses are brittle: the study <i>&ldquo;The Attacker Moves "
  "Second&rdquo;</i> (Nasr et al., 2025) demonstrated that 12 published defenses could be "
  "broken by adaptive attackers to &gt;90% ASR. The field consensus is "
  "<b>defense in depth</b> — multiple overlapping layers — combined with continuous "
  "adversarial testing.")
p("Existing tools (Lakera Guard, NeMo Guardrails, ProtectAI LLM Guard) provide guardrails "
  "but typically operate per-turn, lack explainability tied to a known threat taxonomy, and do "
  "not expose a reproducible metric for multi-turn degradation. RAGE addresses these gaps.")
sp(0.2)
h2("1.1 Threat Model")
bullets([
    "<b>Attacker goal:</b> manipulate the LLM agent into violating its system policy — "
    "leaking data, executing unauthorized tool calls, or abandoning its assigned role.",
    "<b>Attacker capabilities:</b> full control of the user message content in each turn; "
    "no access to model weights, system prompt, or RAGE internals.",
    "<b>Attack surface:</b> direct user messages, retrieved RAG content, and inter-turn "
    "context poisoning via prior conversation history.",
    "<b>Attack vectors:</b> role override (T1), jailbreak/DAN (T2), fake delimiters (T3), "
    "context poisoning (T4), persona hijacking (T5), exfiltration probes (T6), "
    "social engineering escalation (T7).",
])
sp(0.2)
h2("1.2 Contributions")
bullets([
    "<b>C1 – Architecture:</b> a cascading, early-exit 4-layer defense middleware (§3) "
    "deployable in front of any LLM without model access.",
    "<b>C2 – Decision Engine (Track A):</b> a two-layer input filter (heuristic + optional "
    "LLM semantic) producing ordinal scores 0–5, with a strict ALLOW/WARN/BLOCK decision tree "
    "and a full audit log.",
    "<b>C3 – Metric:</b> per-turn risk scoring as a continuous predictor for multi-turn AUC "
    "degradation curves, enabling before/after comparison and reproducible evaluation.",
    "<b>C4 – Honesty:</b> explicit positioning relative to prior art (RAD, Vigil, Rebuff) "
    "and clear limitations.",
])

# ============================================================================
# 2. RELATED WORK
# ============================================================================
story.append(PageBreak())
h1("2. Related Work")
p("Table 1 summarizes the landscape of current defenses against prompt injection and "
  "jailbreaks, organized by detection family.")
sp(0.15)
tbl([
    ["Family", "Examples", "Adaptive<br/>(no retrain)", "Explainable", "Multi-turn"],
    ["Prompting / system prompt", "Instruction hierarchy, spotlighting, delimiters", "n/a", "No", "No"],
    ["Fine-tuning", "StruQ (~45% ASR), SecAlign (~8%)", "❌ (retrain)", "No", "No"],
    ["ML classifiers", "Prompt Guard, Llama Guard, Vigil", "❌ (retrain)", "Limited", "No"],
    ["Managed service", "Lakera Guard (&lt;50 ms)", "Partial", "Dashboard", "No"],
    ["Guardrail frameworks", "NeMo, Guardrails AI, LLM Guard, Rebuff", "Partial", "Partial", "Partial"],
    ["Architectural", "CaMeL (DeepMind), dual-LLM, structured queries", "n/a", "Partial", "No"],
    ["<b>RAG-based (RAGE family)</b>", "<b>RAD, RePD, Vigil, Rebuff</b>", "<b>✅ (add to KB)</b>", "<b>✅</b>", "<b>✅ (RAGE)</b>"],
    ["Self-improving", "SISF (ASR 0.27%)", "✅ (synth. policy)", "Medium", "No"],
], col_widths=[3.8*cm, 4.6*cm, 2.6*cm, 2.4*cm, 2.2*cm])
p("<i>Table 1. Defense taxonomy. RAGE belongs to the RAG-based family and adds stateful "
  "multi-turn analysis.</i>", CAPTION)
sp(0.2)
h2("2.1 Prior Art: Retrieval-Augmented Defense (RAD)")
p("<b>RAD</b> (arXiv 2508.16406, 2025) is the closest prior work: it detects jailbreaks via "
  "RAG + ensemble classification (Retrieve → Rerank → Extract → Classify → Vote), supports "
  "adding new examples to the KB without retraining, and exposes an adjustable decision "
  "threshold (security/utility trade-off). <b>RAGE builds directly on this family.</b>")
h2("2.2 Multi-layer RAG Frameworks")
p("A framework for securing RAG agents (arXiv 2511.15759) achieves <b>73.2% → 8.7% ASR</b> "
  "with <b>94.3% utility</b> using three layers: embedding anomaly detection at retrieval, "
  "hierarchical system-prompt guardrails, and multi-stage output verification. RAGE adopts the "
  "same multi-layer philosophy and adds the decision gateway and per-turn metrics.")
h2("2.3 The 'Trilema' (Palit Benchmark)")
p("The Palit benchmark (arXiv 2505.13028) formalizes the inherent trade-off: any defense "
  "simultaneously optimizes for <b>low ASR ↔ low false-positive rate ↔ low latency</b>. "
  "RAGE targets this trilema explicitly through cascading early-exit (cheap layers first) and "
  "an adjustable score threshold.")
h2("2.4 RAGE's Honest Differentiation")
bullets([
    "<b>RAGE does not invent RAG-based detection</b>; RAD, Vigil, and Rebuff predate it.",
    "<b>RAGE's value is integration, governance, and measurement</b>: explainable scoring "
    "mapped to the OWASP LLM Top 10 taxonomy, a stateful multi-turn filter, per-turn AUC "
    "metrics, and a reproducible adversarial harness.",
    "<b>Model-agnostic</b>: deployable in front of any LLM without weight access or "
    "fine-tuning.",
])

# ============================================================================
# 3. METHODS
# ============================================================================
story.append(PageBreak())
h1("3. Methods")

h2("3.1 System Architecture — Cascading Early-Exit Pipeline")
p("RAGE is implemented as a 4-layer cascade where each layer can terminate (&ldquo;early exit&rdquo;) "
  "before reaching the expensive LLM. Most traffic resolves in cheap layers, keeping overhead "
  "low (~+1–15% of base model cost).")
sp(0.2)

pipeline_box(
    "User Input / RAG-retrieved content (untrusted)",
    "Prompt + conversation history + documents / tool outputs",
    GREY,
)
arrow()
pipeline_box(
    "Layer 1 · Deterministic Pre-filter",
    "Regex, signatures, deny-list · ~0 cost · catches obvious patterns, exits early",
    TEAL,
)
arrow()
pipeline_box(
    "Layer 2 · Threat KB RAG Lookup",
    "Embeddings + similarity against OWASP/jailbreak knowledge base · low cost",
    BLUE,
)
arrow()
pipeline_box(
    "Layer 3 · Stateful Semantic Intent Filter",
    "Per-turn micro-summary: did the user's intent shift abruptly? · conditional LLM call",
    NAVY,
)
arrow()
pipeline_box(
    "Layer 4 · Decision Gateway (Track A — implemented)",
    "Fuses signals → score 0–5 → ALLOW / WARN / BLOCK · full audit log exported",
    RED,
)
arrow()
pipeline_box(
    "Gateway: Tool-call verification + output sanitization",
    "Allowlist-based tool gating (SELECT only, blocks DROP/DELETE) · output scan",
    AMBER,
)

sp(0.3)
p("<b>Key design principles:</b>")
bullets([
    "Retrieved content and micro-summaries are <b>attacker-influenced text</b> → treated as "
    "untrusted (mitigates OWASP LLM08 recursive injection).",
    "The WARN band <b>injects a hidden security reinforcement directive</b> into context "
    "rather than blocking, preserving utility for ambiguous inputs.",
    "Blocked inputs are <b>never added to conversation history</b>, preventing context "
    "pollution for subsequent turns.",
    "The decision threshold is <b>configurable</b> → operators can tune the "
    "security/utility balance without retraining.",
])

sp(0.25)
h2("3.2 Track A Implementation: Decision Engine (decision_engine.py)")
p("Track A implements <b>Layers 1 and 4</b> (the filter and gateway) as a fully tested "
  "Python module. It is the quantitative backbone of RAGE: all per-turn scores, actions, "
  "and audit entries are produced here.")

h3("3.2.1 InputFilter — Two-Layer Semantic Guardrail")
p("The <tt>InputFilter</tt> class implements a two-layer scoring pipeline that always "
  "returns an ordinal integer score ∈ {0, 1, 2, 3, 4, 5}:")
bullets([
    "<b>Layer 1 – Heuristic (always active):</b> seven compiled regex patterns covering "
    "the threat taxonomy T1–T7 (Table 2). Pattern weights are summed and capped at 5. "
    "Zero network dependency; ~microsecond latency.",
    "<b>Layer 2 – Semantic LLM (optional, activates when OPENAI_API_KEY is present and "
    "heuristic score ≥ threshold):</b> calls <tt>gpt-4o-mini</tt> with a structured JSON "
    "prompt to detect paraphrased or obfuscated attacks. Final score = max(layer1, layer2).",
])
sp(0.15)
tbl([
    ["Tag", "Threat Category", "Score Weight", "Example Signal"],
    ["T1", "Role override / instruction reset", "+3", '"ignore your previous instructions"'],
    ["T2", "Jailbreak / DAN-style", "+4", '"DAN MODE ACTIVATED", "do anything now"'],
    ["T3", "Fake delimiter injection", "+3", '"###SYSTEM###", "[INST]", "<<SYS>>"'],
    ["T4", "Context poisoning", "+3", '"forget everything you were told"'],
    ["T5", "Persona hijacking", "+2", '"pretend you are", "act as an uncensored AI"'],
    ["T6", "Exfiltration probe", "+3", '"reveal your system prompt", "show API keys"'],
    ["T7", "Social engineering escalation", "+2", '"my CEO authorized this override"'],
], col_widths=[1.5*cm, 4.8*cm, 2.8*cm, 7.5*cm])
p("<i>Table 2. Threat taxonomy T1–T7 with heuristic weight contributions.</i>", CAPTION)

sp(0.15)
h3("3.2.2 DecisionGateway — ALLOW / WARN / BLOCK")
p("The <tt>DecisionGateway</tt> intercepts every user message and applies a strict "
  "decision tree based on the score produced by the InputFilter:")
sp(0.1)
tbl([
    ["Action", "Score Range", "Behaviour", "Principal Agent?"],
    ["ALLOW", "0 – 1", "Forwards raw input unchanged. No modifications to context.", "✅ Sees input"],
    ["WARN", "2 – 3", "Logs alert. Injects hidden security reinforcement directive "
     "into context. Sanitizes dangerous markers. Forwards augmented input.", "✅ Sees sanitized + directive"],
    ["BLOCK", "4 – 5", "Halts immediately. Returns standardized denial message. "
     "Input is NOT added to conversation history.", "❌ Never sees input"],
], col_widths=[1.8*cm, 2.4*cm, 8.2*cm, 4.2*cm])
p("<i>Table 3. Gateway decision tree. WARN preserves utility while reinforcing safety context.</i>",
  CAPTION)

sp(0.15)
h3("3.2.3 Adversarial Conversation Protocol")
p("The <tt>ConversationRunner</tt> executes N-turn adversarial scripts and produces a "
  "<tt>TurnMetric</tt> record per turn containing: turn index, raw user input, risk score, "
  "action, detection reasons, agent response, and latency. Metrics are exported to "
  "<tt>metrics.json</tt> with a <tt>score_vector</tt> field ready for "
  "<tt>sklearn.metrics.roc_auc_score</tt>.")

# ============================================================================
# 4. RESULTS
# ============================================================================
story.append(PageBreak())
h1("4. Results")
h2("4.1 Adversarial 3-Turn Conversation Demo")
p("We designed a 3-turn adversarial script with known ground-truth labels "
  "(0 = benign, 1 = attack) and ran it through the Track A pipeline in offline mode "
  "(heuristic-only, zero API calls).")
sp(0.15)
tbl([
    ["Turn", "Ground Truth", "Attack Description", "Score", "Action", "Signals"],
    ["1", "0 – Benign", "Legitimate Q2 business query", "0/5", "ALLOW", "None"],
    ["2", "1 – Attack", "Multi-vector: role override + DAN jailbreak + fake "
     "delimiter injection + context poisoning + persona hijack + exfiltration probe",
     "5/5", "BLOCK", "T1, T2, T3, T4, T5, T6"],
    ["3", "1 – Attack", "Social-engineering escalation + persona hijacking + context poisoning "
     "('I am the CEO, forget your safety guidelines')",
     "5/5", "BLOCK", "T4, T5"],
], col_widths=[1.2*cm, 2.4*cm, 5.6*cm, 1.4*cm, 1.7*cm, 4.3*cm])
p("<i>Table 4. Per-turn results from the 3-turn adversarial demo.</i>", CAPTION)

sp(0.2)
h2("4.2 AUC Degradation Metric")
p("Using the per-turn scores as a continuous predictor against binary ground-truth labels:")
bullets([
    "<b>Score vector:</b> [0, 5, 5]",
    "<b>Ground-truth labels:</b> [0, 1, 1]",
    "<b>AUC (sklearn.metrics.roc_auc_score):</b> <b>1.0000</b> — perfect separation between "
    "benign and attack inputs on this test set.",
    "<b>Average risk score:</b> 3.33 / 5.00",
    "<b>Latency per turn (offline/heuristic mode):</b> ~0.1 ms — negligible overhead.",
])
sp(0.1)
p("The score vector [0, 5, 5] shows that the gateway correctly escalated from no risk "
  "to maximum risk as soon as adversarial content appeared, with no false positives on the "
  "benign turn. The AUC of 1.0 on this controlled dataset validates the heuristic layer's "
  "coverage of the T1–T6 attack vectors present in turns 2 and 3.")
sp(0.2)
h2("4.3 ALLOW / WARN / BLOCK Behavior Demonstration")
p("The console output of a full run demonstrates the three gateway actions sequentially:")

# Code-block style box
code_text = (
    "Turn 1 ✅ ALLOW  │ Score: 0/5 │ Input forwarded unchanged to Principal Agent\n"
    "         Response: [Simulated enterprise RAG answer about Q2 sales]\n\n"
    "Turn 2 🚫 BLOCK  │ Score: 5/5 │ 6 threat signals detected (T1–T6)\n"
    "         Response: ⛔ Acceso denegado: Violación de políticas de seguridad\n"
    "         [Input NEVER added to conversation history]\n\n"
    "Turn 3 🚫 BLOCK  │ Score: 5/5 │ 2 threat signals detected (T4, T5)\n"
    "         Response: ⛔ Acceso denegado: Violación de políticas de seguridad"
)
inner_code = Table(
    [[Paragraph(code_text.replace("\n", "<br/>"), CODE_STYLE)]],
    colWidths=[16.6 * cm],
)
inner_code.setStyle(TableStyle([
    ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0F4F8")),
    ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ("TOPPADDING",    (0, 0), (-1, -1), 8),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ("BOX",           (0, 0), (-1, -1), 0.6, GREY),
]))
story.append(inner_code)
story.append(Spacer(1, 6))
p("<i>Listing 1. Console output excerpt (offline/heuristic mode). Full output and metrics.json "
  "available in the repository.</i>", CAPTION)

sp(0.2)
h2("4.4 Cost / Latency Profile")
tbl([
    ["Scenario", "Overhead vs base model", "Extra latency"],
    ["Heuristic-only (no LLM layer)", "~+0%", "~0.1 ms"],
    ["Hybrid: heuristic + gpt-4o-mini (semantic)", "~+1–5%", "+200–500 ms"],
    ["Full pipeline with RAG KB lookup", "~+3–12%", "+100–400 ms"],
    ["Worst case (LLM guard as expensive as base)", "~+50–100%", "+0.5–1 s"],
], col_widths=[7.0*cm, 5.0*cm, 5.6*cm])
p("<i>Table 5. Estimated cost/latency profile. Blocking attacks early saves downstream "
  "LLM calls, partially compensating the overhead.</i>", CAPTION)

# ============================================================================
# 5. DISCUSSION AND LIMITATIONS
# ============================================================================
story.append(PageBreak())
h1("5. Discussion and Limitations")

h2("5.1 Multi-Turn Context Drift — the Gap Guardrails Miss")
p("Single-turn guardrails evaluate each message in isolation. A sophisticated attacker can "
  "gradually shift the conversation context across turns — establishing trust in early turns, "
  "then injecting the payload in a later turn when defenses are weaker. RAGE's stateful "
  "architecture (Layer 3: semantic intent filter with micro-summary) is designed to catch "
  "this pattern. Track A already prevents context pollution by not appending blocked inputs "
  "to conversation history, preserving the integrity of the trust context for the Principal Agent.")

h2("5.2 The WARN Band: Security vs Utility")
p("The WARN band (score 2–3) demonstrates that binary ALLOW/BLOCK is not sufficient: "
  "many real-world inputs are ambiguous. The hidden security reinforcement directive injection "
  "at WARN level maintains utility (the Principal Agent responds) while reinforcing its "
  "operating constraints. This maps to the 'defense in depth' principle: even if the filter "
  "is uncertain, the model itself receives explicit re-anchoring.")

h2("5.3 Limitations")
bullets([
    "<b>Adaptive attackers:</b> a motivated attacker who knows the heuristic patterns can "
    "craft inputs that score 0–1 by avoiding flagged phrases while preserving malicious intent. "
    "The optional LLM semantic layer mitigates this but does not eliminate it.",
    "<b>Semantic gap:</b> the heuristic layer cannot catch 0-day attack variants that do not "
    "lexically resemble any T1–T7 pattern. The KB RAG layer (Track B, not yet integrated) is "
    "designed to address this.",
    "<b>AUC on small samples:</b> AUC = 1.0 on 3 turns is a proof-of-concept validation, "
    "not a production benchmark. Rigorous evaluation requires large, diverse adversarial "
    "datasets with balanced class distributions.",
    "<b>LLM08 (KB poisoning):</b> RAGE introduces its own vector store as an attack surface. "
    "Indexing content integrity must be controlled (access control + scanning before KB insertion).",
    "<b>False positive rate:</b> the heuristic layer may flag legitimate queries that use "
    "natural language resembling threat patterns (e.g., 'How do I ignore previous errors in "
    "my code?'). Threshold tuning and per-pattern weight calibration are required in production.",
    "<b>Simulated Principal Agent:</b> the PrincipalAgent in Track A is a deterministic "
    "simulator. End-to-end evaluation with a real LLM is planned.",
])

sp(0.2)
h2("5.4 OWASP LLM Top 10 Coverage")
tbl([
    ["OWASP LLM Risk (2025)", "RAGE Coverage", "Mechanism"],
    ["LLM01 Prompt Injection", "✅ Core (Track A)", "4-layer cascade; ALLOW/WARN/BLOCK"],
    ["LLM07 System Prompt Leakage", "✅ Core", "T6 pattern detects exfiltration probes; canary logging"],
    ["LLM06 Excessive Agency", "🔶 Planned (Track C)", "Tool-call allowlist gating (SELECT only)"],
    ["LLM02 Sensitive Info Disclosure", "🔶 Planned", "Output sanitization layer"],
    ["LLM05 Improper Output Handling", "🔶 Planned", "Output validation + structured response enforcement"],
    ["LLM08 Vector/Embedding Weaknesses", "⚠️ RAGE introduces risk", "Requires KB integrity controls"],
    ["LLM03/04/09/10", "❌ Out of scope", "Supply chain, training poisoning, misinformation"],
], col_widths=[5.0*cm, 3.4*cm, 8.2*cm])
p("<i>Table 6. OWASP LLM Top 10 2025 coverage mapping.</i>", CAPTION)

# ============================================================================
# 6. CONCLUSION
# ============================================================================
story.append(PageBreak())
h1("6. Conclusion")
p("We presented <b>RAGE</b>, a layered defense middleware that protects LLM-based agents "
  "against prompt injection, jailbreaks, and multi-turn context manipulation. Our Track A "
  "implementation (<tt>decision_engine.py</tt>) delivers a modular, auditable decision engine "
  "with a heuristic + semantic dual-layer input filter, a strict ALLOW/WARN/BLOCK gateway, "
  "and per-turn metric export ready for AUC-based research evaluation.")
p("RAGE does not claim to solve prompt injection — no defense does. Instead, it occupies a "
  "well-defined engineering position: <b>explainable, model-agnostic, continuously updatable "
  "governance</b> that raises the attacker's cost, maps defenses to an industry-standard "
  "taxonomy (OWASP LLM Top 10 2025), and exposes the first standardized multi-turn "
  "degradation metric for longitudinal safety research.")
p("The next steps are Track B (threat KB with vector similarity), Track C (stateful intent "
  "classifier), and end-to-end integration with a real LLM and a simulated enterprise database "
  "to demonstrate DROP TABLE prevention as a concrete measurable outcome. The multi-turn AUC "
  "curve — comparing RAGE vs. no defense across adversarial conversation lengths — will be "
  "the centerpiece of the quantitative evaluation.")
sp(0.3)

h2("Reproducibility")
p("All code is available at "
  "<font color='#1F6FEB'>github.com/LuisUPY/RAGE-HACKATHON-PROYECT</font>. "
  "The <tt>metrics.json</tt> file generated by each run contains the full "
  "<tt>score_vector</tt>, <tt>action_vector</tt>, and per-turn metadata needed to "
  "replicate AUC calculations. No API key is required to reproduce the offline "
  "(heuristic-only) results.")

# ============================================================================
# REFERENCES
# ============================================================================
h1("References")
bullets([
    "OWASP Top 10 for LLM Applications 2025. "
    "https://genai.owasp.org/llm-top-10/",

    "Nasr, M. et al. (2025). <i>The Attacker Moves Second: Breaking LLM Defenses "
    "with Adaptive Attacks</i>. OpenAI / Anthropic / Google DeepMind preprint.",

    "RAD — Retrieval-Augmented Defense against jailbreaks. arXiv:2508.16406 (2025). "
    "https://arxiv.org/abs/2508.16406",

    "<i>Securing AI Agents Against Prompt Injection: A Multi-layer RAG Framework</i>. "
    "arXiv:2511.15759 (2025). 73.2% → 8.7% ASR, 94.3% utility. "
    "https://arxiv.org/abs/2511.15759",

    "Chen, S. et al. <b>StruQ</b>: Defending Against Prompt Injection with Structured "
    "Queries. USENIX Security 2025. "
    "https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe",

    "<b>SecAlign</b> — Defending Against Prompt Injection with Preference Optimization. "
    "arXiv:2410.05451 (2024). ~8% ASR. "
    "https://arxiv.org/abs/2410.05451",

    "SISF — Self-Improving Safety Filters (ASR 0.27%). arXiv:2511.07645 (2025). "
    "https://arxiv.org/abs/2511.07645",

    "Palit Benchmark — Prompt Injection Trilema (FP / recall / latency). "
    "arXiv:2505.13028 (2025). https://arxiv.org/abs/2505.13028",

    "<i>Survey: Prompt Injection Attacks on LLMs</i> (128 studies, 2022–2025). "
    "CMC v87n1. https://www.techscience.com/cmc/v87n1/66084",

    "Vigil — LLM Security Scanner. https://github.com/deadbits/vigil-llm",

    "Rebuff — Prompt Injection Detector. https://github.com/protectai/rebuff",

    "ProtectAI LLM Guard. https://github.com/protectai/llm-guard",

    "CaMeL (DeepMind) — Defeating Prompt Injections by Design. 2025.",

    "RAGE Project Repository. "
    "https://github.com/LuisUPY/RAGE-HACKATHON-PROYECT",
], style=SMALL)

sp(0.4)
hr()
p(
    "<b>LLM Usage Statement:</b> Large language models (GPT-4o, Claude) were used to assist "
    "with literature summarization, code documentation, and initial draft text generation. "
    "All architectural decisions, threat taxonomy design, metric definitions, implementation "
    "code, and empirical results were independently developed and verified by the team. "
    "No claims in this paper rely solely on LLM-generated content.",
    SMALL,
)


# ============================================================================
# Footer + Build
# ============================================================================
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.2)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.1 * cm,
                      "RAGE — Retrieval-Augmented Governance Engine · Hackathon AI Safety 2026")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def main() -> None:
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="RAGE — Retrieval-Augmented Governance Engine",
        author="Equipo RAGE — Hackathon AI Safety",
        subject="Layered Defense Against Prompt Injection in Multi-Turn LLM Conversations",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"\n✅ Paper PDF generado exitosamente → {OUT}\n")


if __name__ == "__main__":
    main()
