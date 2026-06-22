#!/usr/bin/env python3
"""Generate PDF from markdown with proper tables and figures (fpdf2)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import TableCellFillMode, TableBordersLayout, VAlign
from fpdf.fonts import FontFace

REPO_ROOT = Path(__file__).resolve().parents[1]
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


class PaperPDF(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 6,
            "RAGE — Multi-Turn Defense for Text-to-SQL Agents",
            align="C", new_x="LMARGIN", new_y="NEXT",
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
        ("\\delta_i", "δ_i"), ("\\Delta_i", "Δ_i"), ("\\Delta_N", "Δ_N"),
        ("\\tau", "τ"), ("\\epsilon", "ε"), ("\\max", "max"), ("\\min", "min"),
        ("\\cdot", "·"), ("\\approx", "≈"), ("\\gg", ">>"), ("\\ll", "≪"),
        ("\\in", "∈"), ("\\mathbf{e}_i", "e_i"), ("\\mathbf{e}_0", "e_0"),
        ("\\mathbf{e}_{i-1}", "e_{i-1}"),
    ]
    for old, new in replacements:
        out = out.replace(old, new)
    out = re.sub(r"\$([^$]+)\$", r"\1", out)
    out = out.replace("{", "").replace("}", "")
    return out.strip()


def _strip_md_inline(text: str) -> str:
    text = _simplify_math(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _is_table_sep(line: str) -> bool:
    cells = [c.strip() for c in line.strip("|").split("|")]
    return bool(cells) and all(set(c) <= set("-: ") for c in cells)


def _parse_table_row(line: str) -> list[str]:
    return [_strip_md_inline(c.strip()) for c in line.strip("|").split("|")]


def _image_size(path: Path, max_w_mm: float) -> tuple[float, float]:
    try:
        from PIL import Image

        with Image.open(path) as im:
            w_px, h_px = im.size
        aspect = h_px / w_px
        w_mm = max_w_mm
        h_mm = w_mm * aspect
        max_h = 110.0
        if h_mm > max_h:
            h_mm = max_h
            w_mm = h_mm / aspect
        return w_mm, h_mm
    except Exception:
        return max_w_mm, max_w_mm * 0.45


def _ensure_space(pdf: PaperPDF, needed_mm: float) -> None:
    if pdf.get_y() + needed_mm > pdf.page_break_trigger - 5:
        pdf.add_page()


def _render_table(pdf: PaperPDF, rows: list[list[str]], *, caption: str = "") -> None:
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    # Weight wider columns for description / function text
    if ncols == 3:
        col_widths = (usable * 0.22, usable * 0.48, usable * 0.30)
    elif ncols == 4:
        col_widths = tuple(usable / ncols for _ in range(ncols))
    elif ncols == 5:
        col_widths = (usable * 0.10, usable * 0.28, usable * 0.14, usable * 0.10, usable * 0.38)
    elif ncols == 6:
        col_widths = (usable * 0.08, usable * 0.22, usable * 0.12, usable * 0.08, usable * 0.08, usable * 0.42)
    else:
        col_widths = tuple(usable / ncols for _ in range(ncols))

    est_h = 8 * (len(rows) + 1)
    _ensure_space(pdf, est_h + (8 if caption else 0))

    if caption:
        pdf.set_font("DejaVu", "B", 9)
        pdf.multi_cell(0, 5, caption, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    headings = FontFace(family="DejaVu", emphasis="BOLD", size_pt=8)
    body = FontFace(family="DejaVu", size_pt=8)
    with pdf.table(
        width=usable,
        col_widths=col_widths,
        borders_layout=TableBordersLayout.ALL,
        cell_fill_color=(245, 248, 252),
        cell_fill_mode=TableCellFillMode.ROWS,
        line_height=5,
        text_align="LEFT",
        v_align=VAlign.M,
        first_row_as_headings=True,
        headings_style=headings,
    ) as table:
        for i, row in enumerate(rows):
            style = headings if i == 0 else body
            table.row(row, style=style)
    pdf.ln(4)


def _render_image(pdf: PaperPDF, path: Path, caption: str = "") -> None:
    if not path.exists():
        pdf.set_font("DejaVu", "", 9)
        pdf.multi_cell(0, 6, f"[Missing figure: {path}]", new_x="LMARGIN", new_y="NEXT")
        return

    usable = pdf.w - pdf.l_margin - pdf.r_margin
    w_mm, h_mm = _image_size(path, usable)
    _ensure_space(pdf, h_mm + 12)

    x = pdf.l_margin + (usable - w_mm) / 2
    pdf.image(str(path), x=x, y=pdf.get_y(), w=w_mm, h=h_mm)
    pdf.set_y(pdf.get_y() + h_mm + 2)

    if caption:
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 4.5, caption, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    pdf = PaperPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font("DejaVu", "", FONT_REGULAR)
    pdf.add_font("DejaVu", "B", FONT_BOLD)
    pdf.add_font("DejaVuMono", "", FONT_MONO)
    pdf.add_page()

    lines = md_path.read_text(encoding="utf-8").splitlines()
    i = 0
    pending_table_caption = ""
    in_code = False
    code_lines: list[str] = []

    while i < len(lines):
        line = lines[i].rstrip()

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
            i += 1
            continue

        if in_code:
            code_lines.append(line[:110])
            i += 1
            continue

        if not line.strip():
            pdf.ln(2)
            i += 1
            continue

        if line.strip() == "---":
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue

        # Markdown table block
        if line.startswith("|") and "|" in line[1:]:
            if re.match(r"^\*\*Table", line) or re.match(r"^\*\*Tabla", line):
                pending_table_caption = _strip_md_inline(line.strip("*"))
                i += 1
                if i >= len(lines):
                    break
                line = lines[i].rstrip()

            table_rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_line = lines[i].rstrip()
                if not _is_table_sep(row_line):
                    table_rows.append(_parse_table_row(row_line))
                i += 1
            _render_table(pdf, table_rows, caption=pending_table_caption)
            pending_table_caption = ""
            continue

        if line.startswith("**Table") or line.startswith("**Tabla"):
            pending_table_caption = _strip_md_inline(line.strip("*"))
            i += 1
            continue

        img_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
        if img_match:
            caption, rel_path = img_match.group(1), img_match.group(2)
            img_path = (md_path.parent / rel_path).resolve()
            if not img_path.exists():
                img_path = (REPO_ROOT / rel_path).resolve()
            _render_image(pdf, img_path, caption=caption)
            i += 1
            continue

        if line.startswith("# "):
            pdf.ln(3)
            pdf.set_font("DejaVu", "B", 15)
            pdf.set_text_color(20, 60, 100)
            pdf.multi_cell(0, 7, _strip_md_inline(line[2:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        if line.startswith("## "):
            pdf.ln(2)
            _ensure_space(pdf, 12)
            pdf.set_font("DejaVu", "B", 12)
            pdf.set_text_color(30, 80, 130)
            pdf.multi_cell(0, 6, _strip_md_inline(line[3:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        if line.startswith("### "):
            pdf.ln(1)
            pdf.set_font("DejaVu", "B", 10.5)
            pdf.multi_cell(0, 5.5, _strip_md_inline(line[4:]), new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        if re.match(r"^\d+\.\s", line):
            pdf.set_font("DejaVu", "", 9.5)
            pdf.multi_cell(0, 5.5, "  " + _strip_md_inline(line), new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        if line.startswith("- "):
            pdf.set_font("DejaVu", "", 9.5)
            pdf.multi_cell(0, 5.5, "  • " + _strip_md_inline(line[2:]), new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        pdf.set_font("DejaVu", "", 9.5)
        pdf.multi_cell(0, 5.5, _strip_md_inline(line), new_x="LMARGIN", new_y="NEXT")
        i += 1

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(pdf_path))
    print(f"PDF generated: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")


def main() -> int:
    md = REPO_ROOT / "draft_submission.md"
    pdf = REPO_ROOT / "Documentation" / "GlobalSouth-RAGE-Submission.pdf"
    if len(sys.argv) > 1:
        md = Path(sys.argv[1])
    if len(sys.argv) > 2:
        pdf = Path(sys.argv[2])
    if not md.exists():
        print(f"Not found: {md}", file=sys.stderr)
        return 1
    md_to_pdf(md, pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
