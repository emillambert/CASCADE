#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MANUSCRIPT_DIR="$ROOT/papers/02_arxiv/manuscript"
TEX="cascade_arxiv.tex"

cd "$MANUSCRIPT_DIR"

if command -v latexmk >/dev/null 2>&1; then
  latexmk -pdf -interaction=nonstopmode -halt-on-error "$TEX"
else
  pdflatex -interaction=nonstopmode -halt-on-error "$TEX"
  bibtex cascade_arxiv
  pdflatex -interaction=nonstopmode -halt-on-error "$TEX"
  pdflatex -interaction=nonstopmode -halt-on-error "$TEX"
fi
