#!/usr/bin/env bash
# Validación completa antes de enviar hackathon / release.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  RAGE — validación final                                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

bash scripts/check_setup.sh
./scripts/run-tests.sh -q
./scripts/run-bench-generalization.sh
./scripts/run-ablation.sh
./scripts/generate_submission_pdf.sh

echo ""
echo "✓ Validación completa."
echo "  Paper PDF: Documentation/GlobalSouth-RAGE-Submission.pdf"
echo "  Editar autores: draft_submission.md"
