#!/usr/bin/env python3
"""Generate PDF from Manuales/*.md using fpdf2 (UTF-8 / DejaVu)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF

REPO_ROOT = Path(__file__).resolve().parents[1]
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


class ManualPDF(FPDF):
    def header(self) -> None:
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "RAGE Training-Center — Manual v3", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Página {self.page_no()}", align="C")


def _strip_md_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    pdf = ManualPDF()
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
                pdf.set_font("DejaVuMono", "", 8)
                pdf.set_fill_color(245, 245, 245)
                for cl in code_lines:
                    pdf.multi_cell(0, 5, cl, fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
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
            pdf.set_font("DejaVu", "B", 18)
            pdf.set_text_color(20, 60, 100)
            pdf.multi_cell(0, 9, _strip_md_inline(line[2:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            continue

        if line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("DejaVu", "B", 14)
            pdf.set_text_color(30, 80, 130)
            pdf.multi_cell(0, 8, _strip_md_inline(line[3:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            continue

        if line.startswith("### "):
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", 11)
            pdf.multi_cell(0, 7, _strip_md_inline(line[4:]), new_x="LMARGIN", new_y="NEXT")
            continue

        if line.startswith("|") and "|" in line[1:]:
            pdf.set_font("DejaVu", "", 8)
            cells = [c.strip() for c in line.strip("|").split("|")]
            row = "  |  ".join(_strip_md_inline(c) for c in cells)
            if all(set(c) <= set("-: ") for c in cells):
                continue
            pdf.multi_cell(0, 5, row, new_x="LMARGIN", new_y="NEXT")
            continue

        if line.startswith("- "):
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, "  • " + _strip_md_inline(line[2:]), new_x="LMARGIN", new_y="NEXT")
            continue

        if line.startswith("*") and line.endswith("*") and not line.startswith("**"):
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 6, _strip_md_inline(line.strip("*")), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            continue

        pdf.set_font("DejaVu", "", 10)
        pdf.multi_cell(0, 6, _strip_md_inline(line), new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(pdf_path))
    print(f"PDF generado: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")


def main() -> int:
    md = REPO_ROOT / "Manuales" / "training-center-manual.md"
    pdf = REPO_ROOT / "Manuales" / "training-center-manual.pdf"
    if not md.exists():
        print(f"No encontrado: {md}", file=sys.stderr)
        return 1
    md_to_pdf(md, pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
