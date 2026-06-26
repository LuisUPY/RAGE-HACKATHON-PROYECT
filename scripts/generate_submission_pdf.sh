#!/usr/bin/env bash
# Genera PDF de envío Global South (máx. 8 páginas).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
uv pip install fpdf2 -q

cp draft_submission.md submission/GlobalSouth_RAGE_Submission.md

uv run python scripts/generate_submission_figures.py

MD="${1:-draft_submission.md}"
PDF="${2:-Documentation/GlobalSouth-RAGE-Submission.pdf}"

uv run python scripts/generate_paper_pdf.py "$MD" "$PDF"

PAGES=$(python3 -c "
import re, sys
data = open(sys.argv[1], 'rb').read()
print(len(re.findall(rb'/Type\s*/Page[^s]', data)))
" "$PDF")

echo ""
echo "Páginas: $PAGES (límite hackathon: 8)"
if [[ "$PAGES" -gt 8 ]]; then
  echo "ERROR: el PDF supera 8 páginas. Recorta draft_submission.md" >&2
  exit 1
fi
echo "OK → $PDF"
