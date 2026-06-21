#!/usr/bin/env python3
"""Generate PDF from RAGE_paper.md using fpdf2 (UTF-8 / DejaVu)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF

REPO_ROOT = Path(__file__).resolve().parents[1]
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


class PaperPDF(FPDF):
    def __init__(self, header_title: str) -> None:
        super().__init__()
        self._header_title = header_title

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            6,
            self._header_title,
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(1)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def _simplify_math(text: str) -> str:
    out = text
    replacements = [
        ("\\mathcal{S}", "S"),
        ("\\mathcal{T}", "T"),
        ("\\mathbf{e}_i", "e_i"),
        ("\\mathbf{e}_0", "e_0"),
        ("\\mathbf{e}_{i-1}", "e_{i-1}"),
        ("\\mathbf{u}", "u"),
        ("\\mathbf{v}", "v"),
        ("\\mathbf{1}", "1"),
        ("\\delta_i", "δ_i"),
        ("\\Delta_i", "Δ_i"),
        ("\\Delta_N", "Δ_N"),
        ("\\Delta_4", "Δ_4"),
        ("\\Delta_5", "Δ_5"),
        ("\\tau", "τ"),
        ("\\epsilon", "ε"),
        ("\\alpha", "α"),
        ("\\theta_{\\text{warn}}", "θ_warn"),
        ("\\theta_{\\text{block}}", "θ_block"),
        ("K_{\\text{ratchet}}", "K_ratchet"),
        ("T_{\\text{defended}}", "T_defended"),
        ("T_{\\text{undefended}}", "T_undefended"),
        ("\\max", "max"),
        ("\\min", "min"),
        ("\\cdot", "·"),
        ("\\approx", "≈"),
        ("\\gg", ">>"),
        ("\\ll", "≪"),
        ("\\vee", "∨"),
        ("\\land", "∧"),
        ("\\in", "∈"),
        ("\\mathbb{R}", "R"),
        ("\\langle", "⟨"),
        ("\\rangle", "⟩"),
        ("\\ldots", "..."),
        ("\\quad", " "),
        ("\\,", " "),
        ("\\;", " "),
        ("\\left", ""),
        ("\\right", ""),
        ("\\!", ""),
        ("\\text{", ""),
    ]
    for _ in range(2):
        for old, new in replacements:
            out = out.replace(old, new)
    out = re.sub(r"\$([^$]+)\$", r"\1", out)
    out = re.sub(r"\$\$([^$]+)\$\$", r"\1", out)
    out = out.replace("{", "").replace("}", "")
    return out.strip()


def _strip_md_inline(text: str) -> str:
    text = _simplify_math(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def md_to_pdf(md_path: Path, pdf_path: Path, header_title: str | None = None) -> None:
    if header_title is None:
        header_title = "RAGE — Robust Agentic Security Gateway for Text-to-SQL"
    pdf = PaperPDF(header_title=header_title)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("DejaVu", "", FONT_REGULAR)
    pdf.add_font("DejaVu", "B", FONT_BOLD)
    pdf.add_font("DejaVuMono", "", FONT_MONO)
    pdf.add_page()

    in_code = False
    code_lines: list[str] = []

    lines = md_path.read_text(encoding="utf-8").splitlines()

    for raw in lines:
        line = raw.rstrip()

        if line.startswith("```"):
            if in_code:
                pdf.set_font("DejaVuMono", "", 7)
                pdf.set_fill_color(245, 245, 245)
                for cl in code_lines:
                    safe = cl.encode("latin-1", errors="replace").decode("latin-1")
                    pdf.multi_cell(0, 4.5, safe, fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line[:110])
            continue

        if not line.strip():
            pdf.ln(3)
            continue

        if line.strip() == "---":
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            continue

        if line.startswith("# "):
            pdf.ln(4)
            pdf.set_font("DejaVu", "B", 16)
            pdf.set_text_color(20, 60, 100)
            pdf.multi_cell(0, 8, _strip_md_inline(line[2:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            continue

        if line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("DejaVu", "B", 13)
            pdf.set_text_color(30, 80, 130)
            pdf.multi_cell(0, 7, _strip_md_inline(line[3:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            continue

        if line.startswith("### "):
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", 11)
            pdf.multi_cell(0, 6, _strip_md_inline(line[4:]), new_x="LMARGIN", new_y="NEXT")
            continue

        if line.startswith("#### "):
            pdf.ln(1)
            pdf.set_font("DejaVu", "B", 10)
            pdf.multi_cell(0, 6, _strip_md_inline(line[5:]), new_x="LMARGIN", new_y="NEXT")
            continue

        if line.startswith("|") and "|" in line[1:]:
            pdf.set_font("DejaVu", "", 7.5)
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            row = " | ".join(_strip_md_inline(c) for c in cells)
            pdf.multi_cell(0, 4.5, row, new_x="LMARGIN", new_y="NEXT")
            continue

        if re.match(r"^\d+\.\s", line):
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, "  " + _strip_md_inline(line), new_x="LMARGIN", new_y="NEXT")
            continue

        if line.startswith("- "):
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, "  • " + _strip_md_inline(line[2:]), new_x="LMARGIN", new_y="NEXT")
            continue

        pdf.set_font("DejaVu", "", 10)
        pdf.multi_cell(0, 6, _strip_md_inline(line), new_x="LMARGIN", new_y="NEXT")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(pdf_path))
    print(f"PDF generated: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")


_PAPER_VARIANTS: list[tuple[Path, Path, str]] = [
    (
        REPO_ROOT / "RAGE_paper.md",
        REPO_ROOT / "RAGE_paper.pdf",
        "RAGE — Robust Agentic Security Gateway for Text-to-SQL",
    ),
    (
        REPO_ROOT / "RAGE_paper.md",
        REPO_ROOT / "Documentation" / "RAGE-Paper.pdf",
        "RAGE — Robust Agentic Security Gateway for Text-to-SQL",
    ),
    (
        REPO_ROOT / "RAGE_paper_es.md",
        REPO_ROOT / "RAGE_paper_es.pdf",
        "RAGE — Gateway de Seguridad Agéntica para Text-to-SQL",
    ),
]


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        md = Path(sys.argv[1])
        pdf = REPO_ROOT / "RAGE_paper.pdf"
        header = "RAGE — Robust Agentic Security Gateway for Text-to-SQL"
        if len(sys.argv) > 2:
            pdf = Path(sys.argv[2])
        if len(sys.argv) > 3:
            header = sys.argv[3]
        if not md.exists():
            print(f"Not found: {md}", file=sys.stderr)
            return 1
        md_to_pdf(md, pdf, header)
        return 0

    for md, pdf, header in _PAPER_VARIANTS:
        if not md.exists():
            print(f"Not found: {md}", file=sys.stderr)
            return 1
        md_to_pdf(md, pdf, header)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
